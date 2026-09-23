import os
import tweepy
import requests
from atproto import Client

# ----------------------------
# 1. Configurações e Credenciais
# ----------------------------
X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET")

THREADS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")

BSKY_HANDLE = os.getenv("BSKY_HANDLE")
BSKY_PASSWORD = os.getenv("BSKY_APP_PASSWORD")

# ----------------------------
# 2. Funções de Publicação
# ----------------------------

def postar_x(texto):
    try:
        client = tweepy.Client(
            consumer_key=X_API_KEY,
            consumer_secret=X_API_SECRET,
            access_token=X_ACCESS_TOKEN,
            access_token_secret=X_ACCESS_TOKEN_SECRET
        )
        response = client.create_tweet(text=texto)
        print(f"[X] Post publicado com sucesso! ID: {response.data['id']}")
    except Exception as e:
        print(f"[X] Erro ao postar: {e}")

def postar_threads(texto):
    try:
        # Obter o User ID da conta conectada
        me_url = f"https://graph.threads.net/v1.0/me?access_token={THREADS_TOKEN}"
        user_res = requests.get(me_url).json()
        threads_user_id = user_res.get("id")
        
        if not threads_user_id:
            print(f"[Threads] Erro ao obter User ID: {user_res}")
            return

        # 1º Passo: Criar contêiner de postagem de texto
        create_url = f"https://graph.threads.net/v1.0/{threads_user_id}/threads"
        payload = {
            "media_type": "TEXT",
            "text": texto,
            "access_token": THREADS_TOKEN
        }
        res_create = requests.post(create_url, data=payload).json()
        creation_id = res_create.get("id")

        if not creation_id:
            print(f"[Threads] Falha ao criar contêiner: {res_create}")
            return

        # 2º Passo: Publicar o contêiner
        publish_url = f"https://graph.threads.net/v1.0/{threads_user_id}/threads_publish"
        pub_payload = {
            "creation_id": creation_id,
            "access_token": THREADS_TOKEN
        }
        res_pub = requests.post(publish_url, data=pub_payload).json()
        print(f"[Threads] Post publicado com sucesso! ID: {res_pub.get('id')}")
    except Exception as e:
        print(f"[Threads] Erro ao postar: {e}")

def postar_bluesky(texto):
    try:
        client = Client()
        client.login(BSKY_HANDLE, BSKY_PASSWORD)
        post = client.send_post(text=texto)
        print(f"[Bluesky] Post publicado com sucesso! URI: {post.uri}")
    except Exception as e:
        print(f"[Bluesky] Erro ao postar: {e}")

# ----------------------------
# 3. Execução de Teste
# ----------------------------
if __name__ == "__main__":
    mensagem_teste = "Teste de integração automática: Cadê a reforma de São Januário? Acompanhe as novidades em cadeareforma.info"
    
    print("Iniciando publicações...")
    postar_x(mensagem_teste)
    postar_threads(mensagem_teste)
    postar_bluesky(mensagem_teste)