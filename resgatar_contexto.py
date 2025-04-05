import os
import openai
from pinecone import Pinecone
from dotenv import load_dotenv
import tiktoken

# === Carrega variáveis de ambiente ===
load_dotenv()

# === Configura API Keys ===
openai.api_key = os.getenv("OPENAI_API_KEY")
pinecone_api_key = os.getenv("PINECONE_API_KEY")
pinecone_index_name = os.getenv("PINECONE_INDEX_NAME")

# === Inicializa Pinecone (SDK 3.x) ===
pc = Pinecone(api_key=pinecone_api_key)
index = pc.Index(pinecone_index_name)

# === Tokenizer ===
encoding = tiktoken.encoding_for_model("text-embedding-ada-002")

# === Função para gerar embedding ===
def gerar_embedding(texto):
    response = openai.Embedding.create(
        input=texto,
        model="text-embedding-ada-002"
    )
    return response['data'][0]['embedding']

# === Função para buscar contexto relevante ===
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