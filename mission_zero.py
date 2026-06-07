# /// script
# dependencies = [
#   "fastapi",
#   "uvicorn",
#   "langchain-core",
#   "langchain-openai",
#   "langchain-ollama",
#   "langchain-neo4j",
#   "google-cloud-storage",
#   "google-cloud-bigquery",
#   "langgraph",
#   "pydantic",
# ]
# ///

import os
from typing import TypedDict, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_neo4j import Neo4jGraph
from google.cloud import storage, bigquery
from langgraph.graph import StateGraph, START, END

# ==========================================
# MODEL CONFIGURATION
# ==========================================
USE_LOCAL_LLM = True
LOCAL_LLM_MODEL = "hermes3"

if USE_LOCAL_LLM:
    print(f"Initializing Local LLM via Ollama: {LOCAL_LLM_MODEL}")
    llm = ChatOllama(model=LOCAL_LLM_MODEL, temperature=0)
else:
    print("Initializing Cloud LLM: gpt-4o")
    llm = ChatOpenAI(model="gpt-4o", temperature=0)

def call_llm(prompt_text: str, fallback_response: str) -> str:
    try:
        response = llm.invoke(prompt_text)
        return response.content
    except Exception as e:
        return fallback_response

# ==========================================
# NEO4J DATABASE CONNECTION
# ==========================================
NEO4J_URL = os.getenv("NEO4J_URL", "neo4j://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

try:
    print(f"Connecting to Neo4j database at {NEO4J_URL}...")
    graph_db = Neo4jGraph(url=NEO4J_URL, username=NEO4J_USER, password=NEO4J_PASSWORD)
    db_connected = True
except Exception as e:
    print(f"Warning: Could not connect to Neo4j: {e}. Running in simulation/fallback mode.")
    db_connected = False

# ==========================================
# 1. THE GLOBAL STATE
# ==========================================
class MissionZeroState(TypedDict):
    question: str
    intent: Optional[str]         # 'graph_search', 'bigquery_search', or 'general_chat'
    cypher_query: Optional[str]
    bq_query: Optional[str]
    graph_context: Optional[str]
    bq_context: Optional[str]
    final_answer: Optional[str]

# ==========================================
# 2. THE MASTER ROUTER NODE
# ==========================================
def master_router_node(state: MissionZeroState):
    print("\n[Node: Master Router] Analyzing query intent...")
    prompt = f"Classify this question into one of three categories: 'GRAPH' (business strategy/knowledge graph), 'BIGQUERY' (tabular data, metrics, counts, data analysis), or 'GENERAL' (everything else). Question: {state['question']}\nRespond with ONLY the category word."
    
    response_content = call_llm(
        prompt,
        fallback_response="GENERAL"
    ).strip().upper()
    
    if "GRAPH" in response_content:
        intent = "graph_search"
    elif "BIGQUERY" in response_content:
        intent = "bigquery_search"
    else:
        intent = "general_chat"
        
    print(f"[Node: Master Router] Identified intent: '{intent}'")
    return {"intent": intent}

def route_after_master(state: MissionZeroState):
    if state["intent"] == "graph_search":
        return "graph_worker"
    elif state["intent"] == "bigquery_search":
        return "bigquery_worker"
    return "gcs_loader"

# ==========================================
# 3. BIGQUERY WORKER NODE
# ==========================================
def bigquery_worker_node(state: MissionZeroState):
    print("\n[Node: BigQuery Worker] Generating and executing BigQuery SQL...")
    
    mock_query = "SELECT 'Simulated BigQuery Result' as data"
    mock_context = "[{'data': 'Simulated BigQuery Result'}]"
    
    schema_prompt = f"Write a valid BigQuery Standard SQL query for this question: {state['question']}. If you don't know the exact schema, write a query that discovers dataset/table schemas in the current GCP project. Return ONLY the valid SQL code."
    
    bq_query = call_llm(schema_prompt, fallback_response=mock_query).strip()
    if bq_query.startswith("```"):
        bq_query = "\n".join([line for line in bq_query.splitlines() if not line.startswith("```")])
        
    print(f"[Node: BigQuery Worker] Executing query: {bq_query}")
    
    try:
        client = bigquery.Client()
        query_job = client.query(bq_query)
        results = query_job.result()
        context = str([dict(row) for row in results])
        print("[Node: BigQuery Worker] Successfully fetched BigQuery results.")
    except Exception as e:
        context = f"BigQuery Execution Failed or Not Configured: {e}"
        print(f"[Node: BigQuery Worker] Warning: query failed ({e}), using fallback dataset.")
        
    return {"bq_query": bq_query, "bq_context": context}

# ==========================================
# 4. THE AUTONOMOUS GRAPH WORKER NODE
# ==========================================
def graph_worker_node(state: MissionZeroState):
    print("\n[Node: Graph Worker] Generating Cypher query based on ontology...")
    
    mock_query = "MATCH (p:Project {name: 'Delta'})-[:EVOLVED_INTO]->(n) RETURN p, n;"
    mock_context = "[{'p.name': 'Project Delta', 'n.name': 'Project Mission Zero', 'evolution': 'LangGraph implementation'}]"
    
    if not db_connected:
        print("[Node: Graph Worker] Simulated database mode active.")
        return {"cypher_query": mock_query, "graph_context": mock_context}
        
    schema = graph_db.get_schema()
    query_prompt = f"Write a Neo4j Cypher query to answer the user's question based on this schema: {schema}\nQuestion: {state['question']}\nReturn ONLY the valid Cypher query code."
    
    cypher_query = call_llm(query_prompt, fallback_response=mock_query).strip()
    
    if cypher_query.startswith("```"):
        cypher_query = "\n".join([line for line in cypher_query.splitlines() if not line.startswith("```")])
        
    print(f"[Node: Graph Worker] Cypher query: {cypher_query}")
    
    try:
        raw_results = graph_db.query(cypher_query)
        context = str(raw_results)
    except Exception as e:
        context = mock_context
        print(f"[Node: Graph Worker] Warning: query failed ({e}), using fallback dataset.")
        
    return {"cypher_query": cypher_query, "graph_context": context}

# ==========================================
# 5. THE GOOGLE CLOUD STORAGE CONTEXT LOADER
# ==========================================
def gcs_loader_node(state: MissionZeroState):
    print("\n[Node: GCS Loader] Downloading operational doctrine from gs://marooncleanup...")
    try:
        client = storage.Client()
        bucket = client.bucket("marooncleanup")
        blob = bucket.blob("OPERATIONAL_DOCTRINE.md")
        if blob.exists():
            doctrine = blob.download_as_text()
            gcs_context = f"\n=== GCS Grounding Context (OPERATIONAL_DOCTRINE.md) ===\n{doctrine}"
        else:
            gcs_context = "\n[GCS Loader] Info: OPERATIONAL_DOCTRINE.md not found in bucket."
    except Exception as e:
        gcs_context = f"\n[GCS Loader] Warning: Failed to retrieve GCS context: {e}"

    existing = state.get("graph_context") or ""
    return {"graph_context": existing + gcs_context}

# ==========================================
# 6. THE SYNTHESIZER NODE (THE WRITER)
# ==========================================
def synthesizer_node(state: MissionZeroState):
    print("\n[Node: Synthesizer] Writing final response...")
    
    context_to_use = ""
    if state.get("graph_context"):
        context_to_use += f"Graph Data: {state['graph_context']}\n"
    if state.get("bq_context"):
        context_to_use += f"BigQuery Data: {state['bq_context']}\n"
        
    if context_to_use:
        prompt = f"Use this data to answer the user's question. If there are errors, explain them.\nData:\n{context_to_use}\nQuestion: {state['question']}"
    else:
        prompt = f"Answer this general business question: {state['question']}"
        
    fallback_text = "Mission Zero is a highly capable GCP orchestration agent."
    
    final_answer = call_llm(prompt, fallback_response=fallback_text)
    return {"final_answer": final_answer}

# ==========================================
# 7. COMPILING THE DIRECTED CYCLIC GRAPH
# ==========================================
workflow = StateGraph(MissionZeroState)

workflow.add_node("master_router", master_router_node)
workflow.add_node("graph_worker", graph_worker_node)
workflow.add_node("bigquery_worker", bigquery_worker_node)
workflow.add_node("gcs_loader", gcs_loader_node)
workflow.add_node("synthesizer", synthesizer_node)

workflow.add_edge(START, "master_router")

workflow.add_conditional_edges(
    "master_router",
    route_after_master,
    {
        "graph_worker": "graph_worker",
        "bigquery_worker": "bigquery_worker",
        "gcs_loader": "gcs_loader"
    }
)

workflow.add_edge("graph_worker", "gcs_loader")
workflow.add_edge("bigquery_worker", "gcs_loader")
workflow.add_edge("gcs_loader", "synthesizer")
workflow.add_edge("synthesizer", END)

mission_zero_app = workflow.compile()
print("LangGraph State Machine successfully compiled.")

# ==========================================
# 8. FASTAPI CLOUD RUN SERVER
# ==========================================
app = FastAPI(title="Hermes Agent API")

class QueryRequest(BaseModel):
    question: str

@app.post("/ask")
async def ask_hermes(request: QueryRequest):
    user_input = {"question": request.question}
    print(f"Received question: {user_input['question']}")
    
    try:
        result = mission_zero_app.invoke(user_input)
        return {
            "question": result.get("question"),
            "intent": result.get("intent"),
            "answer": result.get("final_answer")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok", "agent": "hermes"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting FastAPI server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
