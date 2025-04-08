import os
from dotenv import load_dotenv
import openai
from pinecone import Pinecone
from uuid import uuid4
import tiktoken

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
pinecone_api_key = os.getenv("PINECONE_API_KEY")
pinecone_index_name = os.getenv("PINECONE_INDEX_NAME")

pc = Pinecone(api_key=pinecone_api_key)
index = pc.Index(pinecone_index_name)

knowledge_dir = "knowledge"
encoding = tiktoken.encoding_for_model("text-embedding-ada-002")

def read_files(path):
    contents = []
    for filename in os.listdir(path):
        if filename.endswith(".txt"):
            with open(os.path.join(path, filename), "r", encoding="utf-8") as file:
                text = file.read()
                contents.append((filename, text))
    return contents

def chunk_text_by_tokens(text, max_tokens=4000):
    tokens = encoding.encode(text)
    chunks = []
    for i in range(0, len(tokens), max_tokens):
        chunk = tokens[i:i + max_tokens]
        chunks.append(encoding.decode(chunk))
    return chunks

def embed_text(text):
    response = openai.Embedding.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response['data'][0]['embedding']

def infer_tag(filename):
    nome = filename.lower()
    if "espiritual" in nome:
        return "espiritualidade"
    elif "filosofia" in nome:
        return "filosofia"
    elif "cfp" in nome or "financas" in nome or "financeiro" in nome:
        return "financas"
    else:
        return "geral"

print("📚 Iniciando ingestão...")
files = read_files(knowledge_dir)
total_chunks = 0

for filename, text in files:
    chunks = chunk_text_by_tokens(text)
    vectors = []
    tag = infer_tag(filename)
    print(f"🗂️  Arquivo: {filename} | Categoria atribuída: {tag}")
    
    for chunk in chunks:
        embedding = embed_text(chunk)
        vector = {
            "id": str(uuid4()),
            "values": embedding,
            "metadata": {
                "source": filename,
                "text": chunk,
                "categoria": tag,
                "user_id": "sistema"
            }
        }
        vectors.append(vector)
    
    index.upsert(vectors=vectors)
    total_chunks += len(vectors)
    print(f"✅ {filename} -> {len(vectors)} pedaços enviados.")

print(f"\n🎉 Ingestão concluída com sucesso. Total de pedaços enviados: {total_chunks}")