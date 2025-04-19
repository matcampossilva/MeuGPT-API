import os
import openai
from pinecone import Index
from dotenv import load_dotenv
import tiktoken

load_dotenv(override=True)

openai.api_key = os.getenv("OPENAI_API_KEY")

index = Index(
    name=os.getenv("PINECONE_INDEX_NAME"),
    api_key=os.getenv("PINECONE_API_KEY"),
    host=os.getenv("PINECONE_HOST")
)

encoding = tiktoken.encoding_for_model("text-embedding-ada-002")

def gerar_embedding(texto):
    response = openai.Embedding.create(
        input=texto,
        model="text-embedding-ada-002"
    )
    return response['data'][0]['embedding']

def buscar_conhecimento_relevante(pergunta_usuario, categoria=None, top_k=4):
    try:
        embedding = gerar_embedding(pergunta_usuario)

        filtro = {"categoria": {"$eq": categoria}} if categoria else {}

        resultado = index.query(
            vector=embedding,
            top_k=top_k,
            include_metadata=True,
            filter=filtro
        )

        textos = [match['metadata']['text'].strip() for match in resultado['matches'] if 'text' in match['metadata']]

        return "\n\n".join(textos) if textos else ""

    except Exception as e:
        print(f"[ERRO Pinecone] {e}")
        return ""