import os
import sys
import json
import urllib.parse
from datetime import datetime, timezone, timedelta
import requests
import tweepy
from atproto import Client, models
from bs4 import BeautifulSoup

# -------------------------------------------------------------
# 1. Configurações e Credenciais (obtidas dos GitHub Secrets)
# -------------------------------------------------------------
X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET")

THREADS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")

BSKY_HANDLE = os.getenv("BSKY_HANDLE")
BSKY_PASSWORD = os.getenv("BSKY_APP_PASSWORD")

ARQUIVO_NOTICIAS = "noticias.json"
ARQUIVO_ESTADO = "estado_redes.json"

HEADERS_REQUESTS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

# -------------------------------------------------------------
# 2. Utilitários de Estado e Datas
# -------------------------------------------------------------
def get_hoje_brasilia():
    """Retorna o datetime atual no fuso horário de Brasília (UTC-3)."""
    return datetime.now(timezone(timedelta(hours=-3)))

def parse_data_br(str_data):
    """Converte string no formato DD/MM/AAAA para objeto datetime."""
    try:
        partes = str_data.strip().split("/")
        return datetime(int(partes[2]), int(partes[1]), int(partes[0]))
    except Exception:
        return datetime(1970, 1, 1)

def carregar_estado():
    """Carrega o registro de postagens para evitar duplicações."""
    if os.path.exists(ARQUIVO_ESTADO):
        try:
            with open(ARQUIVO_ESTADO, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Aviso ao ler {ARQUIVO_ESTADO}: {e}")
    return {"links_postados": [], "ultimo_post_diario": ""}

def salvar_estado(estado):
    """Salva o estado atualizado no disco."""
    try:
        with open(ARQUIVO_ESTADO, "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erro ao salvar {ARQUIVO_ESTADO}: {e}")

# -------------------------------------------------------------
# 3. Formatação dos Textos das Mensagens
# -------------------------------------------------------------
def formatar_mensagem_noticia(veiculo, titulo, link):
    """
    Formulação solicitada:
    'Temos notícias sobre a reforma de São Januário! Nome do veículo - Título da matéria - Link da matéria'
    Ajusta tamanho do título para caber confortavelmente no limite do X (280 caracteres).
    """
    prefixo = "Temos notícias sobre a reforma de São Januário!"
    corpo = f"{veiculo} - {titulo}"
    
    # Limite seguro para corpo + link caber no Twitter/X
    if len(corpo) > 195:
        corpo = corpo[:192].rstrip() + "..."
        
    return f"{prefixo} {corpo} - {link}"

def formatar_mensagem_contador(dias):
    """
    Regras de contagem de ausência de notícias:
    - 1 dia: 'Ontem tivemos notícias sobre a reforma de São Januário.'
    - 2 dias: 'Não temos notícias sobre a reforma de São Januário há dois dias.'
    - 3 dias: 'Não temos notícias sobre a reforma de São Januário há três dias.'
    - 4+ dias: 'Não temos notícias sobre a reforma de São Januário há {dias} dias.'
    """
    if dias <= 0:
        return None
    elif dias == 1:
        return "Ontem tivemos notícias sobre a reforma de São Januário."
    elif dias == 2:
        return "Não temos notícias sobre a reforma de São Januário há dois dias."
    elif dias == 3:
        return "Não temos notícias sobre a reforma de São Januário há três dias."
    else:
        return f"Não temos notícias sobre a reforma de São Januário há {dias} dias."

# -------------------------------------------------------------
# 4. Geração de Link Cards (Open Graph para Bluesky)
# -------------------------------------------------------------
def criar_embed_bluesky(client, url, titulo_padrao="", veiculo_padrao=""):
    """
    Extrai metadados Open Graph da página da matéria e anexa como card no Bluesky (atproto).
    """
    try:
        resp = requests.get(url, headers=HEADERS_REQUESTS, timeout=12, allow_redirects=True)
        final_url = resp.url if resp.url else url
        
        soup = BeautifulSoup(resp.content, "html.parser")
        
        # Título da matéria
        og_title = None
        t_tag = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "twitter:title"})
        if t_tag and t_tag.get("content"):
            og_title = t_tag["content"].strip()
        if not og_title:
            og_title = f"{veiculo_padrao}: {titulo_padrao}".strip(" :")
            
        # Descrição
        og_desc = ""
        d_tag = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "twitter:description"})
        if d_tag and d_tag.get("content"):
            og_desc = d_tag["content"].strip()
            
        # Imagem de capa (thumbnail)
        thumb_blob = None
        i_tag = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
        if i_tag and i_tag.get("content"):
            img_url = i_tag["content"].strip()
            img_url = urllib.parse.urljoin(final_url, img_url)
            try:
                img_res = requests.get(img_url, headers=HEADERS_REQUESTS, timeout=10)
                if img_res.status_code == 200 and len(img_res.content) < 1_000_000:
                    thumb_blob = client.upload_blob(img_res.content).blob
            except Exception as e_img:
                print(f"[Bluesky] Não foi possível anexar thumbnail da imagem: {e_img}")

        external = models.AppBskyEmbedExternal.External(
            uri=final_url,
            title=og_title,
            description=og_desc,
            thumb=thumb_blob
        )
        return models.AppBskyEmbedExternal.Main(external=external)
    except Exception as e:
        print(f"[Bluesky] Aviso ao processar card de metadados: {e}")
        return None

# -------------------------------------------------------------
# 5. Funções de Publicação por Rede
# -------------------------------------------------------------
def postar_x(texto):
    """Publica no X (Twitter) usando a API v2."""
    if not (X_API_KEY and X_API_SECRET and X_ACCESS_TOKEN and X_ACCESS_TOKEN_SECRET):
        print("[X] Credenciais ausentes. Pulando publicação no X.")
        return False
    try:
        client = tweepy.Client(
            consumer_key=X_API_KEY,
            consumer_secret=X_API_SECRET,
            access_token=X_ACCESS_TOKEN,
            access_token_secret=X_ACCESS_TOKEN_SECRET
        )
        response = client.create_tweet(text=texto)
        print(f"[X] Post publicado com sucesso! ID: {response.data['id']}")
        return True
    except Exception as e:
        print(f"[X] Erro ao postar: {e}")
        return False

def postar_threads(texto):
    """Publica no Threads usando a Threads Graph API."""
    if not THREADS_TOKEN:
        print("[Threads] THREADS_ACCESS_TOKEN ausente. Pulando publicação no Threads.")
        return False
    try:
        me_url = f"https://graph.threads.net/v1.0/me?access_token={THREADS_TOKEN}"
        user_res = requests.get(me_url, timeout=15).json()
        threads_user_id = user_res.get("id")
        
        if not threads_user_id:
            print(f"[Threads] Erro ao obter User ID: {user_res}")
            return False

        # 1º Passo: Criar contêiner de postagem
        create_url = f"https://graph.threads.net/v1.0/{threads_user_id}/threads"
        payload = {
            "media_type": "TEXT",
            "text": texto,
            "access_token": THREADS_TOKEN
        }
        res_create = requests.post(create_url, data=payload, timeout=15).json()
        creation_id = res_create.get("id")

        if not creation_id:
            print(f"[Threads] Falha ao criar contêiner: {res_create}")
            return False

        # 2º Passo: Publicar o contêiner
        publish_url = f"https://graph.threads.net/v1.0/{threads_user_id}/threads_publish"
        pub_payload = {
            "creation_id": creation_id,
            "access_token": THREADS_TOKEN
        }
        res_pub = requests.post(publish_url, data=pub_payload, timeout=15).json()
        print(f"[Threads] Post publicado com sucesso! ID: {res_pub.get('id')}")
        return True
    except Exception as e:
        print(f"[Threads] Erro ao postar: {e}")
        return False

def postar_bluesky(texto, item_noticia=None):
    """Publica no Bluesky com suporte a Rich Card Embed para notícias."""
    if not (BSKY_HANDLE and BSKY_PASSWORD):
        print("[Bluesky] Credenciais ausentes. Pulando publicação no Bluesky.")
        return False
    try:
        client = Client()
        client.login(BSKY_HANDLE, BSKY_PASSWORD)
        
        embed = None
        if item_noticia and "link" in item_noticia:
            embed = criar_embed_bluesky(
                client, 
                item_noticia["link"], 
                item_noticia.get("titulo", ""), 
                item_noticia.get("veiculo", "")
            )

        if embed:
            post = client.send_post(text=texto, embed=embed)
        else:
            post = client.send_post(text=texto)
            
        print(f"[Bluesky] Post publicado com sucesso! URI: {post.uri}")
        return True
    except Exception as e:
        print(f"[Bluesky] Erro ao postar: {e}")
        return False

def publicar_em_todas(texto, item_noticia=None):
    """Dispara a postagem para as 3 redes simultaneamente."""
    print(f"\n📢 DISPARANDO POST: \"{texto}\"")
    r_x = postar_x(texto)
    r_threads = postar_threads(texto)
    r_bsky = postar_bluesky(texto, item_noticia)
    return r_x or r_threads or r_bsky

# -------------------------------------------------------------
# 6. Modos de Execução
# -------------------------------------------------------------
def modo_noticias():
    """Verifica se há matérias novas no noticias.json que ainda não foram postadas."""
    print("Modo: Verificando novas notícias para publicação...")
    if not os.path.exists(ARQUIVO_NOTICIAS):
        print(f"Arquivo {ARQUIVO_NOTICIAS} não encontrado.")
        return

    with open(ARQUIVO_NOTICIAS, "r", encoding="utf-8") as f:
        noticias = json.load(f)

    if not isinstance(noticias, list) or len(noticias) == 0:
        print("Nenhuma notícia encontrada no JSON.")
        return

    estado = carregar_estado()
    links_ja_postados = set(estado.get("links_postados", []))

    # Identifica matérias que ainda não foram enviadas às redes
    nao_postadas = [n for n in noticias if n.get("link") and n.get("link") not in links_ja_postados]

    if not nao_postadas:
        print("Nenhuma notícia nova para postar nas redes sociais.")
        return

    print(f"{len(nao_postadas)} notícia(s) nova(s) encontrada(s)!")
    
    # Processa da mais antiga para a mais nova entre as novidades
    for item in reversed(nao_postadas):
        msg = formatar_mensagem_noticia(item.get("veiculo", "Imprensa"), item.get("titulo", ""), item.get("link", ""))
        sucesso = publicar_em_todas(msg, item)
        if sucesso:
            links_ja_postados.add(item["link"])

    estado["links_postados"] = list(links_ja_postados)
    salvar_estado(estado)
    print("Estado atualizado com sucesso.")

def modo_diario():
    """Executado às 20h: Se hoje não houve notícia, publica a mensagem do contador."""
    print("Modo: Post diário das 20h (Contador de dias sem notícias)...")
    if not os.path.exists(ARQUIVO_NOTICIAS):
        print(f"Arquivo {ARQUIVO_NOTICIAS} não encontrado.")
        return

    with open(ARQUIVO_NOTICIAS, "r", encoding="utf-8") as f:
        noticias = json.load(f)

    if not isinstance(noticias, list) or len(noticias) == 0:
        print("Nenhuma notícia registrada no JSON.")
        return

    hoje_bsb = get_hoje_brasilia()
    hoje_str = hoje_bsb.strftime("%d/%m/%Y")

    estado = carregar_estado()
    if estado.get("ultimo_post_diario") == hoje_str:
        print(f"Post diário já foi realizado hoje ({hoje_str}). Encerrando.")
        return

    # Notícia mais recente (topo da lista ordenada)
    ultima_noticia = noticias[0]
    data_ultima_dt = parse_data_br(ultima_noticia.get("data", ""))

    diff_dias = (hoje_bsb.date() - data_ultima_dt.date()).days

    # Se saiu notícia hoje, NÃO fazemos o post de ausência
    if diff_dias <= 0:
        print("Hoje tivemos notícias sobre a reforma de São Januário! O post de ausência não será enviado.")
        estado["ultimo_post_diario"] = hoje_str
        salvar_estado(estado)
        return

    msg = formatar_mensagem_contador(diff_dias)
    if msg:
        sucesso = publicar_em_todas(msg)
        if sucesso:
            estado["ultimo_post_diario"] = hoje_str
            salvar_estado(estado)
            print("Post diário das 20h concluído e estado registrado.")
    else:
        print("Nenhuma mensagem formatada para publicação.")

# -------------------------------------------------------------
# 7. Ponto de Entrada Principal
# -------------------------------------------------------------
if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "--modo-noticias"

    if "--modo" in modo:
        if "diario" in modo:
            modo_diario()
        else:
            modo_noticias()
    elif modo == "--teste":
        print("Executando teste com mensagem genérica...")
        msg_teste = "Teste de integração automática: Cadê a reforma de São Januário? Acompanhe as novidades."
        publicar_em_todas(msg_teste)
    else:
        modo_noticias()