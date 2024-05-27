from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import WebBaseLoader
from langchain_community.vectorstores import Chroma
from langchain_mistralai import MistralAIEmbeddings
from langchain_community.embeddings import GPT4AllEmbeddings
from langchain_community.embeddings import LlamaCppEmbeddings
local_llm="mistral:instruct"
run_local="Yes"
# Load
url = "https://lilianweng.github.io/posts/2023-06-23-agent/"
loader = WebBaseLoader(url)
docs = loader.load()

# Split
text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=500, chunk_overlap=100
)
all_splits = text_splitter.split_documents(docs)

# Embed and index
if run_local == "Yes":
    # GPT4All
    embedding = GPT4AllEmbeddings()
    # Nomic v1 or v1.5
    # embd_model_path = "/Users/rlm/Desktop/Code/llama.cpp/models/nomic-embd/nomic-embed-text-v1.Q4_K_S.gguf"
    # embedding = LlamaCppEmbeddings(model_path=embd_model_path, n_batch=512)
else:
    embedding = MistralAIEmbeddings(mistral_api_key="mistral_api_key")

# Index
vectorstore = Chroma.from_documents(
    documents=all_splits,
    collection_name="rag-chroma",
    embedding=embedding,
)
retriever = vectorstore.as_retriever()