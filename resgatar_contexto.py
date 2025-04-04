import os
import openai
import pinecone
from dotenv import load_dotenv
import tiktoken

load_dotenv()

# Configuração das APIs
openai.api_key = os.getenv("OPENAI_API_KEY")
pinecone_api_key = os.getenv("PINECONE_API_KEY")
pinecone_env = os.getenv("PINECONE_ENV")  # Ex: "us-east-1"
pinecone_index_name = os.getenv("PINECONE_INDEX_NAME")

# Inicializa o Pinecone (versão antiga usa init)
pinecone.init(api_key=pinecone_api_key, environment=pinecone_env)
index = pinecone.Index(pinecone_index_name)

# Tokenizer
encoding = tiktoken.encoding_for_model("text-embedding-ada-002")

def gerar_embedding(texto):
    response = openai.Embedding.create(
        input=texto,
        model="text-embedding-ada-002"
    )
    return response['data'][0]['embedding']

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