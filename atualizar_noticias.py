import os
import json
import urllib.parse
from datetime import datetime, timezone, timedelta
import feedparser
import requests

ARQUIVO_JSON = "noticias.json"

# Domínios, redes sociais e agregadores/canais proibidos
BLOQUEADOS = [
    "netvasco",
    "supervasco",
    "vasconoticias",
    "paponacolina",
    "newscolina",
    "canaldovasco",
    "youtube",
    "youtu.be",
    "instagram",
    "facebook",
    "fb.com",
    "fb.watch",
    "threads.net",
    "twitter.com",
    "x.com",
    "tiktok"
]

# Consultas específicas para abranger todas as frentes da reforma
TERMOS_BUSCA = [
    'reforma "são januário"',
    '"obras" "são januário"',
    '"potencial construtivo" "são januário"',
    '"novo são januário"'
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

def eh_proibido(veiculo, titulo, link):
    """Verifica se a notícia é de rede social ou agregador proibido."""
    texto = f"{veiculo} {titulo} {link}".lower()
    return any(b in texto for b in BLOQUEADOS)

def parse_data(str_data):
    """Converte string no formato DD/MM/AAAA para objeto datetime."""
    try:
        partes = str_data.strip().split("/")
        return datetime(int(partes[2]), int(partes[1]), int(partes[0]))
    except Exception:
        return datetime(1970, 1, 1)

def eh_reforma_sao_januario(titulo):
    """Valida se o conteúdo do título realmente trata da reforma/modernização do estádio."""
    t = titulo.lower()
    
    # 1. Deve citar São Januário ou a Colina Histórica
    tem_sj = any(s in t for s in ["januário", "januario", "colina histórica", "colina historica"])
    if not tem_sj:
        return False
        
    # 2. Deve conter termos explícitos de obra/reforma (NÃO inclui 'estádio' sozinho para evitar notícias de jogos)
    palavras_reforma = [
        "reforma", "reformas", "obra", "obras", "potencial construtivo", 
        "ampliação", "ampliacao", "modernização", "modernizacao", 
        "novo são januário", "novo sao januario", "projeto de lei", 
        "venda do potencial", "demolição", "demolicao", "remodelação", 
        "remodelacao", "retrofit", "maquete"
    ]
    tem_reforma = any(p in t for p in palavras_reforma)
    if not tem_reforma:
        return False

    # 3. Evita falsos positivos de pré-jogo, escalação ou transmissão esportiva
    termos_ignorar = [
        "escalação", "escalacao", "onde assistir", "transmissão", 
        "transmissao", "palpites", "arbitragem", "árbitro", "ingressos"
    ]
    if any(i in t for i in termos_ignorar) and not any(p in t for p in ["reforma", "obras", "potencial construtivo"]):
        return False

    return True

# 1. Carrega notícias existentes e expurga itens que venham a infringir os bloqueios
noticias_atuais = []
if os.path.exists(ARQUIVO_JSON):
    try:
        with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
            dados = json.load(f)
            if isinstance(dados, list):
                noticias_atuais = [
                    n for n in dados
                    if isinstance(n, dict) 
                    and not eh_proibido(n.get("veiculo", ""), n.get("titulo", ""), n.get("link", ""))
                    and eh_reforma_sao_januario(n.get("titulo", ""))
                ]
    except Exception as e:
        print(f"Aviso ao ler JSON existente: {e}")

titulos_salvos = {item.get("titulo", "").strip().lower() for item in noticias_atuais}
links_salvos = {item.get("link", "").strip() for item in noticias_atuais}

novas = []

# 2. Executa as buscas no Google News RSS
for termo in TERMOS_BUSCA:
    url_rss = f"https://news.google.com/rss/search?q={urllib.parse.quote(termo)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    try:
        resp = requests.get(url_rss, headers=HEADERS, timeout=15)
        feed = feedparser.parse(resp.content)
    except Exception as req_err:
        print(f"Falha na requisição com requests ({req_err}). Tentando feedparser direto...")
        feed = feedparser.parse(url_rss)

    for entry in getattr(feed, "entries", []):
        titulo_bruto = getattr(entry, "title", "").strip()
        link = getattr(entry, "link", "").strip()

        if not titulo_bruto or not link:
            continue

        # Separa título e veículo de imprensa
        if " - " in titulo_bruto:
            partes = titulo_bruto.rsplit(" - ", 1)
            titulo = partes[0].strip()
            veiculo = partes[1].strip()
        else:
            titulo = titulo_bruto
            veiculo = getattr(entry, "source", {}).get("title", "Imprensa")

        # Filtro de veículos e agregadores banidos
        if eh_proibido(veiculo, titulo, link):
            continue

        # Filtro de pertinência temática
        if not eh_reforma_sao_januario(titulo):
            continue

        # Extrai data da publicação convertida para horário de Brasília (UTC-3)
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                dt_utc = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                dt_bsb = dt_utc.astimezone(timezone(timedelta(hours=-3)))
                data_str = dt_bsb.strftime("%d/%m/%Y")
            except Exception:
                data_str = datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y")
        else:
            data_str = datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y")

        titulo_chave = titulo.strip().lower()
        if titulo_chave not in titulos_salvos and link not in links_salvos:
            novas.append({
                "data": data_str,
                "veiculo": veiculo,
                "titulo": titulo,
                "link": link
            })
            titulos_salvos.add(titulo_chave)
            links_salvos.add(link)

# 3. Consolidação e ordenação cronológica decrescente (mais recente para a mais antiga)
total_noticias = novas + noticias_atuais
total_noticias.sort(key=lambda n: parse_data(n.get("data", "")), reverse=True)

# 4. Trava de segurança: só substitui se houver notícias para evitar esvaziamento acidental
if total_noticias:
    with open(ARQUIVO_JSON, "w", encoding="utf-8") as f:
        json.dump(total_noticias, f, ensure_ascii=False, indent=2)
    print(f"Sucesso: {len(novas)} novas notícias adicionadas. Total no arquivo: {len(total_noticias)}")
else:
    print("Nenhuma notícia encontrada. Arquivo preservado.")
