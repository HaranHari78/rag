from langchain_community.vectorstores import FAISS
from langgraph.graph import StateGraph
from typing import TypedDict, List, Dict, Any
import json
from collections import defaultdict
from langchain_openai import AzureOpenAIEmbeddings, AzureChatOpenAI
from config import config
from util import batchify, parse_llm_json
import pandas as pd
from tqdm import tqdm
class GraphState(TypedDict, total=False):
    retrieved_documents: List[Dict[str, Any]]
    extracted_labs: List[Dict[str, Any]]
    validated_data: List[Dict[str, Any]]


embedding_model = AzureOpenAIEmbeddings(
    deployment=config["embedding_models"]["text_embedding_3_large"],
    model="text-embedding-3-large",
    openai_api_key=config["azure_openai"]["api_key"],
    azure_endpoint=config["azure_openai"]["endpoint"],
    openai_api_version=config["azure_openai_4O"]["api_version"],
)

faiss_index = FAISS.load_local("faiss_index", embedding_model, allow_dangerous_deserialization=True)

llm = AzureChatOpenAI(
    deployment_name=config["azure_openai_4O"]["deployment"],
    api_key=config["azure_openai"]["api_key"],
    api_version=config["azure_openai_4O"]["api_version"],
    azure_endpoint=config["azure_openai"]["endpoint"],
    temperature=0,
    model=config["azure_openai_4O"]["model"]
)


def get_flca_extraction_prompt(context: List[Dict[str, str]]) -> str:
    with open("prompts/flca_extraction.txt", "r", encoding="utf-8") as file:
        template = file.read()
    return template.format(context=json.dumps(context, indent=2))


def retrieve_docs_agent(state: GraphState) -> GraphState:
    print(f"[RetrieveDocs] Incoming state keys: {list(state.keys())}")
    queries = ["lambda", "klc", "flc", "free light chain"]
    all_results = []

    for query in queries:
        try:
            docs = faiss_index.similarity_search(query, k=1000)
            # Filter only relevant docs where query exists in content
            filtered_docs = [doc for doc in docs if query.lower() in doc.page_content.lower()]
            all_results.extend(filtered_docs)
        except Exception as e:
            print(f"[RetrieveDocs] Error retrieving for query '{query}': {e}")

    unique_documents = set()
    final_documents = []

    for doc in all_results:
        source = doc.metadata.get("source", "unknown_source")
        key = (source, doc.page_content.strip())
        if key not in unique_documents:
            unique_documents.add(key)
            final_documents.append({
                "title": source,
                "medical_notes": doc.page_content.strip()
            })

    print(f"[RetrieveDocs] Retrieved {len(final_documents)} unique documents.")
    new_state: GraphState = {
        **state,
        "retrieved_documents": final_documents
    }

    return new_state


def extract_lab_values_agent(state: GraphState) -> GraphState:
    print("[ExtractLabs] Function entered")
    retrieved_documents = state.get("retrieved_documents", [])
    extracted = []

    # Ensure batchify is available in util.py
    for batch in tqdm(batchify(retrieved_documents, 10)):
        try:
            prompt = get_flca_extraction_prompt(batch)
            result = llm.invoke(prompt)
            parsed = json.loads(parse_llm_json(result.content))
            if isinstance(parsed, list):
                extracted.extend(parsed)
            else:
                print(f"[ExtractLabs] Unexpected response format: {parsed}")
        except Exception as e:
            print(f"[ExtractLabs] Extraction failed for batch: {e}")

    updated_state: GraphState = {
        **state,
        "extracted_labs": extracted
    }

    print(f"[ExtractLabs] Returning {len(extracted)} extracted records.")
    return updated_state



def validate_extraction_agent(state: GraphState) -> GraphState:
    extracted_data = state.get("extracted_labs", [])
    batches = list(batchify(extracted_data, 10))
    validated = []

    for batch in batches:
        validation_prompt = f"""
        You are a clinical validation assistant.
        
        Given a list of extracted records, validate each one by checking if all fields —
        "kappa_flc", "lambda_flc", "kappa_lambda_ratio", and "date_of_lab" — are clearly and exactly supported
        by the provided 'evidence_sentences_for_lab_values' and 'evidence_sentences_for_lab_date'. If a field is not clearly present or verifiable, discard that record.
        
        Return ONLY the valid records in the following **strict JSON format**:
        
        [
          {{
            "title": "<EXACTLY MATCH THE TITLE FIELD FROM THE INPUT>",
            "kappa_flc": "...",
            "lambda_flc": "...",
            "kappa_lambda_ratio": "...",
            "date_of_lab": "...",
            "evidence_sentences_for_lab_values": ["..."],
            "evidence_sentences_for_lab_date": ["..."]
          }},
          ...
        ]
        
        Here is the data:
        {json.dumps(batch, indent=2)}
        """
        try:
            response = llm.invoke(validation_prompt)
            parsed = json.loads(parse_llm_json(response.content))
            if isinstance(parsed, list):
                validated.extend(parsed)
        except Exception as e:
            print(f"[Validate] Validation parsing error: {e}")

    return {**state, "validated_data": validated}


# Graph setup
builder = StateGraph(GraphState)
builder.add_node("RetrieveDocs", retrieve_docs_agent)
builder.add_node("ExtractLabs", extract_lab_values_agent)
builder.add_node("Validate", validate_extraction_agent)

builder.set_entry_point("RetrieveDocs")
builder.add_edge("RetrieveDocs", "ExtractLabs")
builder.add_edge("ExtractLabs", "Validate")
builder.set_finish_point("Validate")

graph = builder.compile()
print("[LangGraph] Graph compiled")

app = graph

if __name__ == "__main__":
    result = app.invoke({})
    print(json.dumps(result['validated_data'], indent=2))
    df = pd.DataFrame(result['validated_data'])

    # Display the DataFrame
    df.to_excel('flca.xlsx')
