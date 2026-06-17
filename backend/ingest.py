from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import FAISS

from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

from utils.config import *

import os

docs = []

for file in os.listdir("mock_data/faq_docs"):

    if file.endswith(".md"):

        loader = TextLoader(
            os.path.join("mock_data/faq_docs", file),
            encoding="utf-8"
        )

        docs.extend(loader.load())

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50
)

chunks = splitter.split_documents(docs)

embeddings = AzureOpenAIEmbeddings(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_API_VERSION,
    azure_deployment=EMBEDDING_DEPLOYMENT
)

vectorstore = FAISS.from_documents(
    chunks,
    embeddings
)

vectorstore.save_local("faiss_index")

print("FAISS Index Created")