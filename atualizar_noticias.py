import os
import json
import feedparser
import urllib.parse  # <-- Nova biblioteca adicionada para corrigir a URL
from datetime import datetime, timezone, timedelta

ARQUIVO_JSON = "noticias.json"

# Busca no RSS do Google News filtrado pelas últimas 48h
termo_busca = "reforma são januário"
# Converte espaços e acentos para formato seguro de link (ex: espaço vira %20)
termo_codificado = urllib.parse.quote(termo_busca) 

rss_url = f"https://news.google.com/rss/search?q={termo_codificado}+when:48h&hl=pt-BR&gl=BR&ceid=BR:pt-419"

feed = feedparser.parse(rss_url)

# Carrega histórico existente
if os.path.exists(ARQUIVO_JSON):
    with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
        try:
            noticias = json.load(f)
        except json.JSONDecodeError:
            noticias = []
else:
    noticias = []

links_existentes = {item.get("link") for item in noticias}
titulos_existentes = {item.get("titulo", "").strip().lower() for item in noticias}

novas_adicionadas = 0
hoje_str = datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y")

for entry in feed.entries:
    titulo_bruto = entry.title
    link = entry.link

    # Extrai o nome do veículo
    if " - " in titulo_bruto:
        partes = titulo_bruto.rsplit(" - ", 1)
        titulo = partes[0].strip()
        veiculo = partes[1].strip()
    else:
        titulo = titulo_bruto.strip()
        veiculo = entry.get("source", {}).get("title", "Imprensa")

    # Filtro de relevância
    t_lower = titulo.lower()
    tem_januario = "januário" in t_lower or "januario" in t_lower
    tem_reforma = any(p in t_lower for p in ["reforma", "obras", "potencial construtivo", "ampliação", "estádio"])

    if tem_januario and tem_reforma:
        if link not in links_existentes and titulo.lower() not in titulos_existentes:
            noticias.insert(0, {
                "data": hoje_str,
                "veiculo": veiculo,
                "titulo": titulo,
                "link": link
            })
            links_existentes.add(link)
            titulos_existentes.add(titulo.lower())
            novas_adicionadas += 1

if novas_adicionadas > 0:
    print(f"Foram adicionadas {novas_adicionadas} nova(s) notícia(s).")
    with open(ARQUIVO_JSON, "w", encoding="utf-8") as f:
        json.dump(noticias, f, ensure_ascii=False, indent=2)
else:
    print("Nenhuma notícia nova encontrada hoje.")
