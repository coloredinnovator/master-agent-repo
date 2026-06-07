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
#   "confluent-kafka",
#   "crewai",
#   "huggingface-hub",
#   "langchain-huggingface",
#   "google-cloud-logging",
#   "google-cloud-aiplatform"
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
from confluent_kafka import Producer

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_neo4j import Neo4jGraph
from langchain_huggingface import HuggingFaceEmbeddings
from google.cloud import storage, bigquery
import google.cloud.logging
from langgraph.graph import StateGraph, START, END

from crew_orchestrator import run_cleanup_crew

# ==========================================
# NASA-GRADE TELEMETRY (GCP CLOUD LOGGING)
# ==========================================
try:
    logging_client = google.cloud.logging.Client()
    logging_client.setup_logging()
    import logging
    logger = logging.getLogger("hermes-mission-control")
    logger.info("Hermes NASA-Grade Telemetry Online.")
    telemetry_active = True
except Exception as e:
    print(f"Warning: GCP Cloud Logging offline. {e}")
    telemetry_active = False

def emit_telemetry(message: str, severity: str = "INFO"):
    print(f"[Telemetry - {severity}] {message}")
    if telemetry_active:
        if severity == "INFO":
            logger.info(message)
        elif severity == "WARNING":
            logger.warning(message)
        elif severity == "ERROR":
            logger.error(message)

# ==========================================
# MODEL CONFIGURATION & HUGGINGFACE
# ==========================================
USE_LOCAL_LLM = True
LOCAL_LLM_MODEL = "hermes3"

if USE_LOCAL_LLM:
    emit_telemetry(f"Initializing Local LLM via Ollama: {LOCAL_LLM_MODEL}")
    llm = ChatOllama(model=LOCAL_LLM_MODEL, temperature=0)
else:
    emit_telemetry("Initializing Cloud LLM: gpt-4o")
    llm = ChatOpenAI(model="gpt-4o", temperature=0)

try:
    hf_embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    emit_telemetry("HuggingFace Embeddings Engine Online.")
except Exception as e:
    emit_telemetry(f"HuggingFace Initialization failed: {e}", "WARNING")

def call_llm(prompt_text: str, fallback_response: str) -> str:
    try:
        response = llm.invoke(prompt_text)
        return response.content
    except Exception as e:
        emit_telemetry(f"LLM Call Failed: {e}", "ERROR")
        return fallback_response

# ==========================================
# THE GLOBAL STATE
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
    crew_context: Optional[str]
    final_answer: Optional[str]

# ==========================================
# THE MASTER ROUTER NODE
# ==========================================
def master_router_node(state: MissionZeroState):
    emit_telemetry("\n[Node: Master Router] Analyzing query intent...")
    prompt = f"Classify this question into: 'GRAPH', 'BIGQUERY', 'POSTGRES', 'KAFKA', 'CREW_CLEANUP' (for organizing/analyzing files and memory), or 'GENERAL'. Question: {state['question']}\nRespond with ONLY the category word."
    
    response_content = call_llm(prompt, fallback_response="GENERAL").strip().upper()
    
    if "GRAPH" in response_content:
        intent = "graph_search"
    elif "BIGQUERY" in response_content:
        intent = "bigquery_search"
    elif "POSTGRES" in response_content:
        intent = "postgres_search"
    elif "KAFKA" in response_content:
        intent = "kafka_stream"
    elif "CREW" in response_content or "CLEANUP" in response_content:
        intent = "crew_orchestration"
    else:
        intent = "general_chat"
        
    emit_telemetry(f"[Node: Master Router] Identified intent: '{intent}'")
    return {"intent": intent}

def route_after_master(state: MissionZeroState):
    routing_map = {
        "graph_search": "graph_worker",
        "bigquery_search": "bigquery_worker",
        "postgres_search": "postgres_worker",
        "kafka_stream": "kafka_worker",
        "crew_orchestration": "crew_worker"
    }
    return routing_map.get(state["intent"], "synthesizer")

# ==========================================
# CREW AI WORKER NODE (THE MEMORY SPECIALIST)
# ==========================================
def crew_worker_node(state: MissionZeroState):
    emit_telemetry("[Node: Crew Worker] Spawning AI Memory Specialist and Swarm...")
    try:
        # Pass the task to the CrewAI orchestrator
        crew_report = run_cleanup_crew(state['question'])
        emit_telemetry("[Node: Crew Worker] Swarm execution complete.")
        return {"crew_context": crew_report}
    except Exception as e:
        emit_telemetry(f"[Node: Crew Worker] Swarm Failure: {e}", "ERROR")
        return {"crew_context": f"CrewAI Error: {e}"}

# ==========================================
# OTHER WORKERS (MOCKS FOR BREVITY)
# ==========================================
def bigquery_worker_node(state: MissionZeroState):
    return {"bq_context": "Simulated BQ Call"}
def graph_worker_node(state: MissionZeroState):
    return {"graph_context": "Simulated Graph Call"}
def postgres_worker_node(state: MissionZeroState):
    return {"pg_context": "Simulated Postgres Call"}
def kafka_worker_node(state: MissionZeroState):
    return {"kafka_context": "Simulated Kafka Publish"}

# ==========================================
# THE SYNTHESIZER NODE
# ==========================================
def synthesizer_node(state: MissionZeroState):
    emit_telemetry("\n[Node: Synthesizer] Writing final response...")
    
    context_to_use = ""
    for key in ["graph_context", "bq_context", "pg_context", "kafka_context", "crew_context"]:
        if state.get(key):
            context_to_use += f"{key.upper()}: {state[key]}\n"
            
    if context_to_use:
        prompt = f"Use this data to answer the user's question.\nData:\n{context_to_use}\nQuestion: {state['question']}"
    else:
        prompt = f"Answer this general question: {state['question']}"
        
    final_answer = call_llm(prompt, fallback_response="Mission Zero Orchestration Complete.")
    return {"final_answer": final_answer}

# ==========================================
# COMPILE GRAPH
# ==========================================
workflow = StateGraph(MissionZeroState)

workflow.add_node("master_router", master_router_node)
workflow.add_node("graph_worker", graph_worker_node)
workflow.add_node("bigquery_worker", bigquery_worker_node)
workflow.add_node("postgres_worker", postgres_worker_node)
workflow.add_node("kafka_worker", kafka_worker_node)
workflow.add_node("crew_worker", crew_worker_node)
workflow.add_node("synthesizer", synthesizer_node)

workflow.add_edge(START, "master_router")
workflow.add_conditional_edges("master_router", route_after_master, {
    "graph_worker": "graph_worker",
    "bigquery_worker": "bigquery_worker",
    "postgres_worker": "postgres_worker",
    "kafka_worker": "kafka_worker",
    "crew_worker": "crew_worker",
    "synthesizer": "synthesizer"
})

for worker in ["graph_worker", "bigquery_worker", "postgres_worker", "kafka_worker", "crew_worker"]:
    workflow.add_edge(worker, "synthesizer")
    
workflow.add_edge("synthesizer", END)

mission_zero_app = workflow.compile()
emit_telemetry("NASA-Grade LangGraph State Machine successfully compiled.")

# ==========================================
# FASTAPI APP
# ==========================================
app = FastAPI(title="Hermes NASA-Grade API")

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
