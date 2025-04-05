import os
import openai
from pinecone import Pinecone, Index
from dotenv import load_dotenv
import tiktoken

# === LOAD VARIÁVEIS DE AMBIENTE ===
load_dotenv(override=True)

# DEBUG OPCIONAL (desativa depois de funcionar)
print("🔍 PINECONE_API_KEY:", os.getenv("PINECONE_API_KEY")[:6], "...")
print("🌍 PINECONE_ENV:", os.getenv("PINECONE_ENV"))
print("📦 PINECONE_INDEX_NAME:", os.getenv("PINECONE_INDEX_NAME"))
print("🔗 PINECONE_HOST:", os.getenv("PINECONE_HOST"))

# === OPENAI SETUP ===
openai.api_key = os.getenv("OPENAI_API_KEY")

# === PINECONE SETUP ===
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = Index(
    name=os.getenv("PINECONE_INDEX_NAME"),
    host=os.getenv("PINECONE_HOST")
)

# === TOKENIZER ===
encoding = tiktoken.encoding_for_model("text-embedding-ada-002")

# === GERA EMBEDDING ===
def gerar_embedding(texto):
    response = openai.Embedding.create(
        input=texto,
        model="text-embedding-ada-002"
    )
    return response['data'][0]['embedding']

# === BUSCA NO PINECONE ===
def buscar_conhecimento_relevante(pergunta_usuario, top_k=3):
    embedding = gerar_embedding(pergunta_usuario)

    resultado = index.query(
        vector=embedding,
        top_k=top_k,
        include_metadata=True
    )

    textos = []
    for match in resultado['matches']:
        texto = match['metadata'].get('text', '')
        if texto:
            textos.append(texto.strip())

    return "\n\n".join(textos)