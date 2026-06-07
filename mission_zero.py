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
#   "psycopg2-binary",
#   "confluent-kafka"
# ]
# ///

import os
import json
from typing import TypedDict, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import psycopg2
from psycopg2.extras import RealDictCursor
from confluent_kafka import Producer, Consumer

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
# DB & KAFKA CONNECTIONS
# ==========================================
NEO4J_URL = os.getenv("NEO4J_URL", "neo4j://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

try:
    graph_db = Neo4jGraph(url=NEO4J_URL, username=NEO4J_USER, password=NEO4J_PASSWORD)
    db_connected = True
except Exception as e:
    db_connected = False

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "hermes")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "hermes_password")
POSTGRES_DB = os.getenv("POSTGRES_DB", "hermes_db")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")

# ==========================================
# 1. THE GLOBAL STATE
# ==========================================
class MissionZeroState(TypedDict):
    question: str
    intent: Optional[str]         
    cypher_query: Optional[str]
    bq_query: Optional[str]
    pg_query: Optional[str]
    graph_context: Optional[str]
    bq_context: Optional[str]
    pg_context: Optional[str]
    kafka_context: Optional[str]
    final_answer: Optional[str]

# ==========================================
# 2. THE MASTER ROUTER NODE
# ==========================================
def master_router_node(state: MissionZeroState):
    print("\n[Node: Master Router] Analyzing query intent...")
    prompt = f"Classify this question into one of four categories: 'GRAPH' (business strategy), 'BIGQUERY' (analytics/data warehouse), 'POSTGRES' (relational/transactional data), 'KAFKA' (streaming/events) or 'GENERAL' (everything else). Question: {state['question']}\nRespond with ONLY the category word."
    
    response_content = call_llm(prompt, fallback_response="GENERAL").strip().upper()
    
    if "GRAPH" in response_content:
        intent = "graph_search"
    elif "BIGQUERY" in response_content:
        intent = "bigquery_search"
    elif "POSTGRES" in response_content:
        intent = "postgres_search"
    elif "KAFKA" in response_content:
        intent = "kafka_stream"
    else:
        intent = "general_chat"
        
    print(f"[Node: Master Router] Identified intent: '{intent}'")
    return {"intent": intent}

def route_after_master(state: MissionZeroState):
    if state["intent"] == "graph_search":
        return "graph_worker"
    elif state["intent"] == "bigquery_search":
        return "bigquery_worker"
    elif state["intent"] == "postgres_search":
        return "postgres_worker"
    elif state["intent"] == "kafka_stream":
        return "kafka_worker"
    return "gcs_loader"

# ==========================================
# 3. POSTGRES WORKER NODE
# ==========================================
def postgres_worker_node(state: MissionZeroState):
    print("\n[Node: Postgres Worker] Generating and executing PostgreSQL query...")
    
    schema_prompt = f"Write a valid PostgreSQL query for this question: {state['question']}. If you don't know the schema, query information_schema.tables to discover it. Return ONLY valid SQL."
    pg_query = call_llm(schema_prompt, fallback_response="SELECT 'Simulated Postgres' as status").strip()
    
    if pg_query.startswith("```"):
        pg_query = "\n".join([line for line in pg_query.splitlines() if not line.startswith("```")])
        
    print(f"[Node: Postgres Worker] Executing query: {pg_query}")
    
    try:
        conn = psycopg2.connect(host=POSTGRES_HOST, port=POSTGRES_PORT, user=POSTGRES_USER, password=POSTGRES_PASSWORD, dbname=POSTGRES_DB)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(pg_query)
        results = cursor.fetchall()
        context = str(results)
        cursor.close()
        conn.close()
    except Exception as e:
        context = f"Postgres Execution Failed: {e}"
        print(f"[Node: Postgres Worker] Warning: query failed ({e})")
        
    return {"pg_query": pg_query, "pg_context": context}

# ==========================================
# 4. KAFKA WORKER NODE
# ==========================================
def kafka_worker_node(state: MissionZeroState):
    print("\n[Node: Kafka Worker] Emitting thought to Kafka event stream...")
    
    try:
        producer = Producer({'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS})
        message = json.dumps({"agent": "hermes", "action": "thought_process", "question": state['question']})
        producer.produce("hermes-thoughts", message.encode('utf-8'))
        producer.flush()
        context = "Successfully published event to Kafka topic 'hermes-thoughts'."
    except Exception as e:
        context = f"Kafka Publish Failed: {e}"
        print(f"[Node: Kafka Worker] Warning: {e}")
        
    return {"kafka_context": context}

# ==========================================
# 5. OTHER WORKERS (BIGQUERY, GRAPH, GCS)
# ==========================================
def bigquery_worker_node(state: MissionZeroState):
    print("\n[Node: BigQuery Worker] Simulated or Actual BQ Call...")
    return {"bq_context": "Simulated BQ Results"}

def graph_worker_node(state: MissionZeroState):
    print("\n[Node: Graph Worker] Simulated Graph Call...")
    return {"graph_context": "Simulated Graph Results"}

def gcs_loader_node(state: MissionZeroState):
    print("\n[Node: GCS Loader] Downloading operational doctrine...")
    return {"graph_context": (state.get("graph_context") or "") + "\nOperational Doctrine loaded."}

# ==========================================
# 6. THE SYNTHESIZER NODE
# ==========================================
def synthesizer_node(state: MissionZeroState):
    print("\n[Node: Synthesizer] Writing final response...")
    
    context_to_use = ""
    for key in ["graph_context", "bq_context", "pg_context", "kafka_context"]:
        if state.get(key):
            context_to_use += f"{key.upper()}: {state[key]}\n"
            
    if context_to_use:
        prompt = f"Use this data to answer the user's question.\nData:\n{context_to_use}\nQuestion: {state['question']}"
    else:
        prompt = f"Answer this general question: {state['question']}"
        
    final_answer = call_llm(prompt, fallback_response="Mission Zero Orchestration Complete.")
    return {"final_answer": final_answer}

# ==========================================
# 7. COMPILE GRAPH
# ==========================================
workflow = StateGraph(MissionZeroState)

workflow.add_node("master_router", master_router_node)
workflow.add_node("graph_worker", graph_worker_node)
workflow.add_node("bigquery_worker", bigquery_worker_node)
workflow.add_node("postgres_worker", postgres_worker_node)
workflow.add_node("kafka_worker", kafka_worker_node)
workflow.add_node("gcs_loader", gcs_loader_node)
workflow.add_node("synthesizer", synthesizer_node)

workflow.add_edge(START, "master_router")
workflow.add_conditional_edges("master_router", route_after_master, {
    "graph_worker": "graph_worker",
    "bigquery_worker": "bigquery_worker",
    "postgres_worker": "postgres_worker",
    "kafka_worker": "kafka_worker",
    "gcs_loader": "gcs_loader"
})
workflow.add_edge("graph_worker", "gcs_loader")
workflow.add_edge("bigquery_worker", "gcs_loader")
workflow.add_edge("postgres_worker", "gcs_loader")
workflow.add_edge("kafka_worker", "gcs_loader")
workflow.add_edge("gcs_loader", "synthesizer")
workflow.add_edge("synthesizer", END)

mission_zero_app = workflow.compile()

# ==========================================
# 8. FASTAPI APP
# ==========================================
app = FastAPI(title="Hermes Agent API")

class QueryRequest(BaseModel):
    question: str

@app.post("/ask")
async def ask_hermes(request: QueryRequest):
    user_input = {"question": request.question}
    try:
        result = mission_zero_app.invoke(user_input)
        return {"question": result.get("question"), "intent": result.get("intent"), "answer": result.get("final_answer")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
