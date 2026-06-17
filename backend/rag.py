import os

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import FAISS

from utils.config import *

embeddings = AzureOpenAIEmbeddings(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_API_VERSION,
    azure_deployment=EMBEDDING_DEPLOYMENT
)

db = FAISS.load_local(
    "faiss_index",
    embeddings,
    allow_dangerous_deserialization=True
)

def retrieve(query, chat_history=None, k=4):
    """
    Args:
        query        : latest user message
        chat_history : optional list of {role, content} dicts (currently
                        unused for retrieval itself, accepted so callers
                        like faq_agent.py can pass it for future use)
        k            : number of chunks to retrieve

    Returns:
        context     : str, concatenated chunk text for the LLM prompt
        scored_docs : list[dict], retrieved chunks + metadata + score,
                      for display in the UI sidebar
    """
    results = db.similarity_search_with_score(query, k=k)

    context = "\n\n".join(doc.page_content for doc, _score in results)

    scored_docs = [
        {
            "content": doc.page_content,
            "metadata": doc.metadata,
            "score": float(score),
        }
        for doc, score in results
    ]

    return context, scored_docs