import os
import openai
from pinecone import Index
from dotenv import load_dotenv
from datetime import datetime
from uuid import uuid4
import tiktoken

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
index = Index(
    name=os.getenv("PINECONE_INDEX_NAME"),
    api_key=os.getenv("PINECONE_API_KEY"),
    host=os.getenv("PINECONE_HOST")
)

encoding = tiktoken.encoding_for_model("text-embedding-ada-002")

def gerar_embedding(texto):
    response = openai.Embedding.create(
        input=texto,
        model="text-embedding-ada-002"
    )
    return response['data'][0]['embedding']

def armazenar_mensagem(user_id, autor, mensagem, tags=None):
    try:
        texto = f"{autor}: {mensagem.strip()}"
        embedding = gerar_embedding(texto)
        data = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        index.upsert([
            {
                "id": str(uuid4()),
                "values": embedding,
                "metadata": {
                    "text": texto,
                    "user_id": user_id,
                    "autor": autor,
                    "data": data,
                    "tags": tags or []
                }
            }
        ])
        print(f"[MEMÓRIA] Armazenado com sucesso para {user_id}")
    except Exception as e:
        print(f"[ERRO MEMÓRIA] {e}")