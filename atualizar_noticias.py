import os
import json
import feedparser
import urllib.parse
from datetime import datetime, timezone, timedelta

ARQUIVO_JSON = "noticias.json"

# Busca matérias recentes sobre a reforma de São Januário no Google News Brasil
termo_busca = '"reforma" "são januário"'
termo_codificado = urllib.parse.quote(termo_busca)
rss_url = f"https://news.google.com/rss/search?q={termo_codificado}&hl=pt-BR&gl=BR&ceid=BR:pt-419"

feed = feedparser.parse(rss_url)

# Carrega notícias existentes
if os.path.exists(ARQUIVO_JSON):
    with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
        try:
            noticias = json.load(f)
        except json.JSONDecodeError:
            noticias = []
else:
    noticias = []

titulos_existentes = {item.get("titulo", "").strip().lower() for item in noticias}
links_existentes = {item.get("link") for item in noticias}

novas = []

for entry in feed.entries:
    titulo_completo = entry.title
    link = entry.link

    # Separa veículo e título real
    if " - " in titulo_completo:
        partes = titulo_completo.rsplit(" - ", 1)
        titulo = partes[0].strip()
        veiculo = partes[1].strip()
    else:
        titulo = titulo_completo.strip()
        veiculo = entry.get("source", {}).get("title", "Imprensa")

    # Extrai data de publicação real do feed (se existir) ou usa data de hoje
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6])
        data_formatada = dt.strftime("%d/%m/%Y")
    else:
        data_formatada = datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y")

    # Filtro de relevância
    t_lower = titulo.lower()
    tem_januario = "januário" in t_lower or "januario" in t_lower
    tem_reforma = any(w in t_lower for w in ["reforma", "obras", "potencial construtivo", "estádio", "ampliação"])

    if tem_januario and tem_reforma:
        if titulo.lower() not in titulos_existentes and link not in links_existentes:
            novas.append({
                "data": data_formatada,
                "veiculo": veiculo,
                "titulo": titulo,
                "link": link
            })
            titulos_existentes.add(titulo.lower())
            links_existentes.add(link)

if novas:
    print(f"Adicionando {len(novas)} notícia(s) ao feed...")
    # Coloca as novas notícias no topo
    noticias = novas + noticias
    with open(ARQUIVO_JSON, "w", encoding="utf-8") as f:
        json.dump(noticias, f, ensure_ascii=False, indent=2)
else:
    print("Nenhuma nova matéria encontrada.")
