import os
import openai
import pinecone
from dotenv import load_dotenv
from uuid import uuid4

# Carregar variáveis de ambiente
load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
pinecone_api_key = os.getenv("PINECONE_API_KEY")
pinecone_env = os.getenv("PINECONE_ENV")  # ex: "us-east-1"
pinecone_index_name = os.getenv("PINECONE_INDEX")  # ex: "meu-conselheiro"

# Inicializar Pinecone
pinecone.init(api_key=pinecone_api_key, environment=pinecone_env)

# Verifica se o índice existe
if pinecone_index_name not in pinecone.list_indexes():
    raise ValueError(f"Index '{pinecone_index_name}' não encontrado no Pinecone.")

index = pinecone.Index(pinecone_index_name)

# Função para dividir textos em chunks menores
def split_text(text, max_tokens=500):
    import tiktoken
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    chunks = []
    for i in range(0, len(tokens), max_tokens):
        chunk = tokens[i:i+max_tokens]
        chunk_text = encoding.decode(chunk)
        chunks.append(chunk_text)
    return chunks

# Caminho da pasta de conhecimento
knowledge_path = "knowledge"

all_chunks = []

# Percorrer os arquivos .txt da pasta knowledge
for filename in os.listdir(knowledge_path):
    if filename.endswith(".txt"):
        filepath = os.path.join(knowledge_path, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            chunks = split_text(content)
            all_chunks.extend(chunks)

print(f"🔍 Total de chunks para vetorização: {len(all_chunks)}")

# Gerar embeddings com OpenAI
batch_size = 50
vectors_to_upsert = []

for i in range(0, len(all_chunks), batch_size):
    batch = all_chunks[i:i + batch_size]
    response = openai.Embedding.create(
        input=batch,
        model="text-embedding-ada-002"
    )
    for j, embedding in enumerate(response["data"]):
        vectors_to_upsert.append((
            str(uuid4()),
            embedding["embedding"],
            {"text": batch[j]}
        ))

# Inserir os vetores no Pinecone
print("📡 Subindo vetores para o Pinecone...")
index.upsert(vectors=vectors_to_upsert)

print("✅ Vetorização concluída e indexado no Pinecone com sucesso.")
