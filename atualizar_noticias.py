import os
import json
import feedparser
import urllib.parse
from datetime import datetime, timezone, timedelta

ARQUIVO_JSON = "noticias.json"

TERMOS_BANIDOS = [
    "netvasco",
    "supervasco",
    "instagram",
    "facebook",
    "threads.net",
    "twitter.com",
    "x.com",
    "youtube",
    "youtube.com",
    "youtu.be"
]

def eh_bloqueado(veiculo, titulo, link):
    texto_analise = f"{veiculo} {titulo} {link}".lower()
    return any(b in texto_analise for b in TERMOS_BANIDOS)

def converter_para_data(data_str):
    try:
        partes = str(data_str).strip().split("/")
        if len(partes) == 3:
            return datetime(int(partes[2]), int(partes[1]), int(partes[0]))
    except Exception:
        pass
    return datetime(1970, 1, 1)

termo_busca = (
    '"reforma" "são januário" '
    '-site:netvasco.com.br -site:supervasco.com '
    '-site:instagram.com -site:facebook.com -site:youtube.com'
)
termo_codificado = urllib.parse.quote(termo_busca)
rss_url = f"https://news.google.com/rss/search?q={termo_codificado}&hl=pt-BR&gl=BR&ceid=BR:pt-419"

feed = feedparser.parse(rss_url)

noticias = []
if os.path.exists(ARQUIVO_JSON):
    try:
        with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
            dados = json.load(f)
            if isinstance(dados, list):
                noticias = [
                    n for n in dados
                    if isinstance(n, dict) and not eh_bloqueado(n.get("veiculo", ""), n.get("titulo", ""), n.get("link", ""))
                ]
    except Exception as e:
        print(f"Aviso ao ler noticias.json anterior: {e}")
        noticias = []

titulos_existentes = {item.get("titulo", "").strip().lower() for item in noticias}
links_existentes = {item.get("link") for item in noticias}

for entry in feed.entries:
    titulo_completo = getattr(entry, "title", "").strip()
    link = getattr(entry, "link", "").strip()

    if not titulo_completo or not link:
        continue

    if " - " in titulo_completo:
        partes = titulo_completo.rsplit(" - ", 1)
        titulo = partes[0].strip()
        veiculo = partes[1].strip()
    else:
        titulo = titulo_completo
        veiculo = getattr(entry, "source", {}).get("title", "Imprensa")

    if eh_bloqueado(veiculo, titulo, link):
        continue

    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6]) - timedelta(hours=3)
        data_str = dt.strftime("%d/%m/%Y")
    else:
        data_str = datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y")

    t_lower = titulo.lower()
    tem_januario = "januário" in t_lower or "januario" in t_lower
    tem_reforma = any(w in t_lower for w in ["reforma", "obras", "potencial construtivo", "estádio", "ampliação"])

    if tem_januario and tem_reforma:
        if titulo.lower() not in titulos_existentes and link not in links_existentes:
            noticias.append({
                "data": data_str,
                "veiculo": veiculo,
                "titulo": titulo,
                "link": link
            })
            titulos_existentes.add(titulo.lower())
            links_existentes.add(link)

# Garante ordenação decrescente segura
noticias.sort(key=lambda n: converter_para_data(n.get("data", "")), reverse=True)

# Só sobrescreve se houver dados válidos para não esvaziar o arquivo
if noticias:
    with open(ARQUIVO_JSON, "w", encoding="utf-8") as f:
        json.dump(noticias, f, ensure_ascii=False, indent=2)
    print(f"Sucesso. {len(noticias)} notícias salvas.")
else:
    print("Nenhuma alteração necessária.")
