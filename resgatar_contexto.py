import os
import openai
from pinecone import Index
from dotenv import load_dotenv
import tiktoken

# === VARIÁVEIS DE AMBIENTE ===
load_dotenv(override=True)

openai.api_key = os.getenv("OPENAI_API_KEY")

# === INDEX SERVERLESS COM HOST EXPLÍCITO ===
index = Index(
    name=os.getenv("PINECONE_INDEX_NAME"),
    api_key=os.getenv("PINECONE_API_KEY"),
    host=os.getenv("PINECONE_HOST")
)

# === TOKENIZER ===
encoding = tiktoken.encoding_for_model("text-embedding-ada-002")

# === EMBEDDING ===
def gerar_embedding(texto):
    response = openai.Embedding.create(
        input=texto,
        model="text-embedding-ada-002"
    )
    return response['data'][0]['embedding']

# === BUSCA ===
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