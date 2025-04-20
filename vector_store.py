import os
import pinecone
import openai
from dotenv import load_dotenv

load_dotenv()

# Inicializa OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Configurações do Pinecone
pinecone_api_key = os.getenv("PINECONE_API_KEY")
pinecone_index_name = os.getenv("PINECONE_INDEX_NAME")
pinecone_env = os.getenv("PINECONE_ENV")

# Inicializa Pinecone versão nova (6.x)
pc = pinecone.Pinecone(api_key=pinecone_api_key)

# Verifica se o índice existe, senão cria
existing_indexes = [index_info['name'] for index_info in pc.list_indexes()]
if pinecone_index_name not in existing_indexes:
    pc.create_index(
        name=pinecone_index_name,
        dimension=1536,
        metric="cosine",
        spec=pinecone.ServerlessSpec(cloud="aws", region=pinecone_env)
    )

print("✅ Pinecone configurado com sucesso.")