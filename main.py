import streamlit as st
import requests
import pprint
from langgraph.graph import END, StateGraph
from utils import retrieve, grade_documents, generate, transform_query, web_search, decide_to_generate ,GraphState
local_llm="mistral:instruct"
run_local="Yes"

workflow = StateGraph(GraphState)

# Define the nodes
workflow.add_node("retrieve", retrieve)  # retrieve
workflow.add_node("grade_documents", grade_documents)  # grade documents
workflow.add_node("generate", generate)  # generatae
workflow.add_node("transform_query", transform_query)  # transform_query
workflow.add_node("web_search", web_search)  # web search

# Build graph
workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "grade_documents")
workflow.add_conditional_edges(
    "grade_documents",
    decide_to_generate,
    {
        "transform_query": "transform_query",
        "generate": "generate",
    },
)
workflow.add_edge("transform_query", "web_search")
workflow.add_edge("web_search", "generate")
workflow.add_edge("generate", END)

# Compile
app = workflow.compile()



def generate_answer(question, run_local):
    inputs = {
        "keys": {
            "question": question,
            "local": run_local,
        }
    }
    response = []
    for output in app.stream(inputs):
        for key, value in output.items():
            if "generation" in value["keys"]:
                response.append(value["keys"]["generation"])
    return response

def main():

  
    st.title("LLM Chat")

    # Input for user question
    question = st.text_input("Enter your question:")
    
    # Button to generate answer
    if st.button("Generate Answer"):
        if question:
            run_local = "Yes"  # Change this according to your requirement
            answer = generate_answer(question, run_local)
            st.write("Answer:")
            for gen in answer:
                st.write(gen)
        else:
            st.warning("Please enter a question.")

if __name__ == "__main__":
    main()
