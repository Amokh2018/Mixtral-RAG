from typing import Annotated, Dict, TypedDict
from langchain_core.messages import BaseMessage
import json 
import operator
from typing import Annotated, Sequence, TypedDict
from langchain import hub 
from langchain_core.output_parsers import JsonOutputParser 
from langchain.prompts import PromptTemplate 
from langchain.schema import Document 
from langchain_community.chat_models import ChatOllama 
from langchain_community.tools. tavily_search import TavilySearchResults 
from langchain_community.vectorstores import Chroma 
from langchain_core.output_parsers import StrOutputParser 
from langchain_core. runnables import RunnablePassthrough 
from langchain_mistralai.chat_models import ChatMistralAI
from dotenv import load_dotenv

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import WebBaseLoader
from langchain_community.vectorstores import Chroma
from langchain_mistralai import MistralAIEmbeddings
from langchain_community.embeddings import GPT4AllEmbeddings
from langchain_community.embeddings import LlamaCppEmbeddings
import os

# Load environment variables from .env file
load_dotenv()

# Get the API key
LANGCHAIN_KEY = os.getenv("LANGCHAIN_KEY")
tavily_api_key = os.getenv("TAVILY_API_KEY")
LANGCHAIN_TRACING_V2= True
LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"
LANGCHAIN_PROJECT="C-RAG-Mistral"


local_llm="mistral:instruct"
run_local="Yes"
# Load
#url = "https://lilianweng.github.io/posts/2023-06-23-agent/"
url = "https://en.wikipedia.org/wiki/Michel_Foucault"
 
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
  



class GraphState(TypedDict):
    """
    Represent the state of our graph.
    Attribute :
        keys (Dict[str, any]): A dictionnary where each key is a string.
    """
    keys: Dict[str, any]


## Nodes:
def retrieve(state):
    """
    Retrieve documents

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): New key added to state, documents, that contains retrieved documents
    """
    print("---RETRIEVE---")
    state_dict = state["keys"]
    question = state_dict["question"]
    local=state_dict["local"]
    documents = retriever.get_relevant_documents(question)
    return {"keys": {"documents": documents, "local":local, "question":question}}

def generate(state):
    """
    Generate answer

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): New key added to state, answer, that contains generated answer
    """
    print("---GENERATE---")
    state_dict = state["keys"]
    documents = state_dict["documents"]
    local=state_dict["local"]
    question = state_dict["question"]
    
    # Prompt
    prompt = hub.pull("rlm/rag-prompt")

    # LLM
    if local == "Yes":
        llm = ChatOllama(model=local_llm, temperature = 0)
    else:
        llm = ChatMistralAI(
            model = "mistral-medium", temperature=0, mistral_api_key=MISTRAL_API_KEY
        )

    # Post-processing
    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    # Chain
    rag_chain = prompt | llm | StrOutputParser()

    # Run
    generation = rag_chain.invoke({"context": documents, "question": question})

    return {"keys": {"generation": generation, "documents":documents, "question":question}}    
def grade_documents(state):
    """
    Determines whether the retrieved documents are relevant to the question.

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): Updates documents key with relevant documents
    """
    print("---CHECK RELEVANCE---")
    state_dict = state["keys"]
    question = state_dict["question"]
    documents = state_dict["documents"]
    local = state_dict["local"]

    # LLM
    if local == "Yes":
        llm = ChatOllama(model=local_llm, format="json", temperature=0)
    else:
        llm = ChatMistralAI(
            mistral_api_key=mistral_api_key, temperature=0, model="mistral-medium"
        )
    prompt = PromptTemplate(
        template="""You are a grader assessing relevance of a retrieved document to a user question. \n 
        Here is the retrieved document: \n\n {context} \n\n
        Here is the user question: {question} \n
        If the document contains keywords related to the user question, grade it as relevant. \n
        It does not need to be a stringent test. The goal is to filter out erroneous retrievals. \n
        Give a binary score 'yes' or 'no' score to indicate whether the document is relevant to the question. \n
        Provide the binary score as a JSON with a single key 'score' and no premable or explaination.""",
        input_variables=["question", "context"],
    )

    chain = prompt | llm | JsonOutputParser()
    # Score
    filtered_docs = []
    search = "No"  # Default do not opt for web search to supplement retrieval
    for d in documents:
        score = chain.invoke(
            {
                "question": question,
                "context": d.page_content,
            }
        )
        grade = score["score"]
        if grade == "yes":
            print("---GRADE: DOCUMENT RELEVANT---")
            filtered_docs.append(d)
        else:
            print("---GRADE: DOCUMENT NOT RELEVANT---")
            search = "Yes"  # Perform web search
            continue

    return {
        "keys": {
            "documents": filtered_docs,
            "question": question,
            "local": local,
            "run_web_search": search,
        }
    }

def transform_query(state):
    """
    Transform the query to produce a better question.

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): Updates question key with a re-phrased question
    """

    print("---TRANSFORM QUERY---")
    state_dict = state["keys"]
    question = state_dict["question"]
    documents = state_dict["documents"]
    local = state_dict["local"]

    # Create a prompt template with format instructions and the query
    prompt = PromptTemplate(
        template="""You are generating questions that is well optimized for retrieval. \n 
        Look at the input and try to reason about the underlying sematic intent / meaning. \n 
        Here is the initial question:
        \n ------- \n
        {question} 
        \n ------- \n
        Provide an improved question without any premable, only respond with the updated question: """,
        input_variables=["question"],
    )

    # Grader
    # LLM
    if local == "Yes":
        llm = ChatOllama(model=local_llm, temperature=0)
    else:
        llm = ChatMistralAI(
            mistral_api_key=mistral_api_key, temperature=0, model="mistral-medium"
        )

    # Prompt
    chain = prompt | llm | StrOutputParser()
    better_question = chain.invoke({"question": question})

    return {
        "keys": {"documents": documents, "question": better_question, "local": local}
    }    

def web_search(state):
    """
    Web search based on the re-phrased question using Tavily API.

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): Web results appended to documents.
    """

    print("---WEB SEARCH---")
    state_dict = state["keys"]
    question = state_dict["question"]
    documents = state_dict["documents"]
    local = state_dict["local"]

    tool = TavilySearchResults()
    docs = tool.invoke({"query": question})
    web_results = "\n".join([d["content"] for d in docs])
    web_results = Document(page_content=web_results)
    documents.append(web_results)

    return {"keys": {"documents": documents, "local": local, "question": question}}

## Edges


def decide_to_generate(state):
    """
    Determines whether to generate an answer or re-generate a question for web search.

    Args:
        state (dict): The current state of the agent, including all keys.

    Returns:
        str: Next node to call
    """

    print("---DECIDE TO GENERATE---")
    state_dict = state["keys"]
    question = state_dict["question"]
    filtered_documents = state_dict["documents"]
    search = state_dict["run_web_search"]

    if search == "Yes":
        # All documents have been filtered check_relevance
        # We will re-generate a new query
        print("---DECISION: TRANSFORM QUERY and RUN WEB SEARCH---")
        return "transform_query"
    else:
        # We have relevant documents, so generate answer
        print("---DECISION: GENERATE---")
        return "generate"