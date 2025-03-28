import os
from dotenv import load_dotenv
from chromadb import PersistentClient
from chromadb.config import Settings
from openai import OpenAI
import tiktoken
from tqdm import tqdm

load_dotenv()
client_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

embedding_model = "text-embedding-3-small"
knowledge_folder = "./knowledge"
index_path = "./chromadb"

def load_files_from_folder(folder_path):
    texts = []
    for filename in os.listdir(folder_path):
        if filename.endswith(".txt"):
            with open(os.path.join(folder_path, filename), "r", encoding="utf-8") as file:
                texts.append(file.read())
    return texts

def split_text(text, max_tokens=500):
    enc = tiktoken.encoding_for_model("gpt-4")
    sentences = text.split(". ")
    chunks = []
    current_chunk = ""
    for sentence in sentences:
        test_chunk = current_chunk + sentence + ". "
        if len(enc.encode(test_chunk)) > max_tokens:
            chunks.append(current_chunk.strip())
            current_chunk = sentence + ". "
        else:
            current_chunk = test_chunk
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

def embed_texts(text_chunks):
    vectors = []
    batch_size = 50
    for i in tqdm(range(0, len(text_chunks), batch_size)):
        batch = text_chunks[i:i+batch_size]
        response = client_openai.embeddings.create(
            model=embedding_model,
            input=batch
        )
        for res in response.data:
            vectors.append(res.embedding)
    return vectors

def create_vector_index():
    os.makedirs(index_path, exist_ok=True)
    chroma_client = PersistentClient(path=index_path, settings=Settings(allow_reset=True))
    if "conhecimento" in chroma_client.list_collections():
        chroma_client.delete_collection("conhecimento")
    collection = chroma_client.create_collection(name="conhecimento")

    texts = load_files_from_folder(knowledge_folder)
    chunks = []
    for text in texts:
        chunks.extend(split_text(text))

    embeddings = embed_texts(chunks)
    ids = [f"doc_{i}" for i in range(len(chunks))]

    collection.add(documents=chunks, embeddings=embeddings, ids=ids)
    print("📦 Vetorização concluída com sucesso usando ChromaDB.")

if __name__ == "__main__":
    create_vector_index()
