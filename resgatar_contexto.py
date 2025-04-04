import os
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone
import tiktoken

load_dotenv()

# OpenAI
openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)

# Pinecone
pinecone_api_key = os.getenv("PINECONE_API_KEY")
pinecone_index_name = os.getenv("PINECONE_INDEX_NAME")
pc = Pinecone(api_key=pinecone_api_key)
index = pc.Index(pinecone_index_name)

# Tokenizer
encoding = tiktoken.encoding_for_model("text-embedding-ada-002")

def gerar_embedding(texto):
    response = client.embeddings.create(
        input=texto,
        model="text-embedding-ada-002"
    )
    return response.data[0].embedding

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