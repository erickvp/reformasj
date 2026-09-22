import os
import json
import urllib.parse
from datetime import datetime, timezone, timedelta
import feedparser

ARQUIVO_JSON = "noticias.json"

# Domínios, redes sociais e agregadores proibidos
BLOQUEADOS = [
    "netvasco",
    "supervasco",
    "youtube",
    "youtu.be",
    "instagram",
    "facebook",
    "threads.net",
    "twitter.com",
    "x.com",
    "tiktok"
]

def eh_proibido(veiculo, titulo, link):
    texto = f"{veiculo} {titulo} {link}".lower()
    return any(b in texto for b in BLOQUEADOS)

def parse_data(str_data):
    try:
        partes = str_data.strip().split("/")
        return datetime(int(partes[2]), int(partes[1]), int(partes[0]))
    except Exception:
        return datetime(1970, 1, 1)

# 1. Carrega notícias existentes
noticias_atuais = []
if os.path.exists(ARQUIVO_JSON):
    try:
        with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
            dados = json.load(f)
            if isinstance(dados, list):
                # Limpa qualquer item banido do passado
                noticias_atuais = [
                    n for n in dados
                    if isinstance(n, dict) and not eh_proibido(n.get("veiculo", ""), n.get("titulo", ""), n.get("link", ""))
                ]
    except Exception as e:
        print(f"Erro ao ler JSON: {e}")

titulos_salvos = {item.get("titulo", "").strip().lower() for item in noticias_atuais}
links_salvos = {item.get("link", "").strip() for item in noticias_atuais}

# 2. Busca simples e segura no Google News RSS (sem operadores que causam bloqueio)
termo = 'reforma "são januário"'
url_rss = f"https://news.google.com/rss/search?q={urllib.parse.quote(termo)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"

feed = feedparser.parse(url_rss)

novas = []

for entry in getattr(feed, "entries", []):
    titulo_bruto = getattr(entry, "title", "").strip()
    link = getattr(entry, "link", "").strip()

    if not titulo_bruto or not link:
        continue

    # Separa veículo e título real
    if " - " in titulo_bruto:
        partes = titulo_bruto.rsplit(" - ", 1)
        titulo = partes[0].strip()
        veiculo = partes[1].strip()
    else:
        titulo = titulo_bruto
        veiculo = getattr(entry, "source", {}).get("title", "Imprensa")

    # Descarta canais do YouTube, agregadores e redes sociais
    if eh_proibido(veiculo, titulo, link):
        continue

    # Extrai data da publicação ou usa hoje no horário de Brasília
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6]) - timedelta(hours=3)
        data_str = dt.strftime("%d/%m/%Y")
    else:
        data_str = datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y")

    # Filtro de pertinência
    t_low = titulo.lower()
    tem_sj = "januário" in t_low or "januario" in t_low
    tem_ref = any(w in t_low for w in ["reforma", "obras", "potencial construtivo", "ampliação", "estádio"])

    if tem_sj and tem_ref:
        if titulo.lower() not in titulos_salvos and link not in links_salvos:
            novas.append({
                "data": data_str,
                "veiculo": veiculo,
                "titulo": titulo,
                "link": link
            })
            titulos_salvos.add(titulo.lower())
            links_salvos.add(link)

# Junta as novas com as antigas
total_noticias = novas + noticias_atuais

# Ordena rigorosamente da mais recente para a mais antiga
total_noticias.sort(key=lambda n: parse_data(n.get("data", "")), reverse=True)

# TRAVA DE SEGURANÇA: Só salva se a lista tiver notícias para evitar apagar o arquivo
if total_noticias:
    with open(ARQUIVO_JSON, "w", encoding="utf-8") as f:
        json.dump(total_noticias, f, ensure_ascii=False, indent=2)
    print(f"Sucesso: {len(novas)} novas notícias adicionadas. Total no arquivo: {len(total_noticias)}")
else:
    print("Nenhuma notícia para salvar. Arquivo preservado.")
