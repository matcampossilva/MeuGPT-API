import os
import openai
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv

load_dotenv()

# Inicializa o cliente OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Configurações do Pinecone
pinecone_api_key = os.getenv("PINECONE_API_KEY")
pinecone_env = os.getenv("PINECONE_ENV")  # Ex: "us-east-1"

# Cria instância do cliente Pinecone
pc = Pinecone(api_key=pinecone_api_key)

# Nome do index
index_name = "meu-conselheiro"

# Criação do índice (se ainda não existir)
if index_name not in pc.list_indexes().names():
    pc.create_index(
        name=index_name,
        dimension=1536,
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region=pinecone_env  # us-east-1, etc.
        )
    )

print("✅ Pinecone configurado com sucesso.")