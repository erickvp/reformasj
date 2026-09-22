import os
import json
import feedparser
import urllib.parse
from datetime import datetime, timezone, timedelta

ARQUIVO_JSON = "noticias.json"

TERMOS_BANIDOS = ["netvasco", "supervasco"]

def eh_veiculo_banido(veiculo, titulo, link):
    texto_analise = f"{veiculo} {titulo} {link}".lower()
    return any(b in texto_analise for b in TERMOS_BANIDOS)

# 1. Bloqueia direto na query do Google News
termo_busca = '"reforma" "são januário" -site:netvasco.com.br -site:supervasco.com'
termo_codificado = urllib.parse.quote(termo_busca)
rss_url = f"https://news.google.com/rss/search?q={termo_codificado}&hl=pt-BR&gl=BR&ceid=BR:pt-419"

feed = feedparser.parse(rss_url)

# 2. Carrega notícias existentes e LIMPA os banidos que já estavam salvos
noticias = []
if os.path.exists(ARQUIVO_JSON):
    with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
        try:
            dados_antigos = json.load(f)
            # Remove qualquer NetVasco ou SuperVasco pré-existente
            noticias = [
                item for item in dados_antigos
                if not eh_veiculo_banido(
                    item.get("veiculo", ""),
                    item.get("titulo", ""),
                    item.get("link", "")
                )
            ]
        except json.JSONDecodeError:
            noticias = []

titulos_existentes = {item.get("titulo", "").strip().lower() for item in noticias}
links_existentes = {item.get("link") for item in noticias}

novas = []

for entry in feed.entries:
    titulo_completo = entry.title
    link = entry.link

    # Identifica o veículo da matéria
    if " - " in titulo_completo:
        partes = titulo_completo.rsplit(" - ", 1)
        titulo = partes[0].strip()
        veiculo = partes[1].strip()
    else:
        titulo = titulo_completo.strip()
        veiculo = entry.get("source", {}).get("title", "Imprensa")

    # Descarta imediatamente agregadores
    if eh_veiculo_banido(veiculo, titulo, link):
        continue

    # Extrai a data ou usa a de Brasília
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6])
        data_formatada = dt.strftime("%d/%m/%Y")
    else:
        data_formatada = datetime.now(timezone(timedelta(hours=-3))).strftime("%d/%m/%Y")

    # Filtro temático
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

# Junta as novas no topo e salva o arquivo limpo
noticias = novas + noticias

with open(ARQUIVO_JSON, "w", encoding="utf-8") as f:
    json.dump(noticias, f, ensure_ascii=False, indent=2)

print(f"Execução concluída. Total no JSON: {len(noticias)} notícias ({len(novas)} novas adicionadas).")
