import os
import pinecone
import openai
from dotenv import load_dotenv

load_dotenv()

# Inicializa OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Configurações do Pinecone
pinecone_api_key = os.getenv("PINECONE_API_KEY")
pinecone_env = os.getenv("PINECONE_ENV")
pinecone_index_name = os.getenv("PINECONE_INDEX_NAME")

# Inicializa Pinecone (versão antiga)
pinecone.init(api_key=pinecone_api_key, environment=pinecone_env)

# Verifica se o índice já existe, senão cria
if pinecone_index_name not in pinecone.list_indexes():
    pinecone.create_index(
        name=pinecone_index_name,
        dimension=1536,
        metric="cosine"
    )

print("✅ Pinecone configurado com sucesso.")