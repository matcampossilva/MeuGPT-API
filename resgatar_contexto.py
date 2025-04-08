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

def buscar_conhecimento_relevante(pergunta_usuario, categoria=None, top_k=3):
    try:
        embedding = gerar_embedding(pergunta_usuario)

        query_params = {
            "vector": embedding,
            "top_k": top_k,
            "include_metadata": True
        }

        if categoria:
            query_params["filter"] = {
                "categoria": {"$eq": categoria}
            }

        resultado = index.query(**query_params)

        textos = []
        for match in resultado.get('matches', []):
            texto = match['metadata'].get('text', '')
            if texto:
                textos.append(texto.strip())

        if not textos:
            return "Nenhum conhecimento relevante foi encontrado no momento."

        return "\n\n".join(textos)

    except Exception as e:
        print(f"[ERRO no Pinecone] {e}")
        return "Contexto não disponível agora. Siga com a resposta normalmente."