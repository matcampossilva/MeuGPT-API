import os
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone
from uuid import uuid4

load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")
pinecone_api_key = os.getenv("PINECONE_API_KEY")
pinecone_index_name = os.getenv("PINECONE_INDEX_NAME")

client = OpenAI(api_key=openai_api_key)
pc = Pinecone(api_key=pinecone_api_key)
index = pc.Index(pinecone_index_name)

knowledge_dir = "knowledge"

def read_files(path):
    contents = []
    for filename in os.listdir(path):
        if filename.endswith(".txt"):
            with open(os.path.join(path, filename), "r", encoding="utf-8") as file:
                text = file.read()
                contents.append((filename, text))
    return contents

# Ajuste importante: pedaços menores (500 caracteres por chunk)
def chunk_text(text, max_length=500):
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""
    for para in paragraphs:
        if len(current_chunk) + len(para) <= max_length:
            current_chunk += para + "\n\n"
        else:
            chunks.append(current_chunk.strip())
            current_chunk = para + "\n\n"
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    return chunks

def embed_text(text):
    response = client.embeddings.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response.data[0].embedding

print("📚 Iniciando ingestão...")
files = read_files(knowledge_dir)
total_chunks = 0

for filename, text in files:
    chunks = chunk_text(text)
    vectors = []
    for chunk in chunks:
        embedding = embed_text(chunk)
        vector = {
            "id": str(uuid4()),
            "values": embedding,
            "metadata": {
                "source": filename,
                "text": chunk
            }
        }
        vectors.append(vector)
    index.upsert(vectors=vectors)
    total_chunks += len(vectors)
    print(f"✅ {filename} -> {len(vectors)} pedaços enviados")

print(f"\n🎉 Ingestão concluída com sucesso. Total de pedaços enviados: {total_chunks}")
