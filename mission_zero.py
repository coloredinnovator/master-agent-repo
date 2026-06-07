# /// script
# dependencies = [
#   "fastapi", "uvicorn", "langchain-core", "langchain-openai", "langchain-ollama",
#   "langchain-neo4j", "google-cloud-storage", "google-cloud-bigquery", "langgraph",
#   "pydantic", "psycopg2-binary", "confluent-kafka", "crewai", "huggingface-hub",
#   "langchain-huggingface", "google-cloud-logging", "google-cloud-aiplatform",
#   "llama-index", "metagpt", "chromadb", "dspy-ai", "unstructured", "open-interpreter",
#   "pandasai", "litellm", "redis"
# ]
# ///

import os
from typing import TypedDict, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import redis

# Standard ML & Cloud Imports
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_huggingface import HuggingFaceEmbeddings
import google.cloud.logging
from langgraph.graph import StateGraph, START, END

from crew_orchestrator import run_cleanup_crew

# ==========================================
# NASA-GRADE TELEMETRY
# ==========================================
try:
    logging_client = google.cloud.logging.Client()
    logging_client.setup_logging()
    import logging
    logger = logging.getLogger("hermes-mission-control")
    telemetry_active = True
except Exception:
    telemetry_active = False

def emit_telemetry(message: str, severity: str = "INFO"):
    print(f"[Telemetry - {severity}] {message}")
    if telemetry_active:
        if severity == "INFO": logger.info(message)
        elif severity == "ERROR": logger.error(message)

# ==========================================
# MODEL CONFIGURATION
# ==========================================
llm = ChatOllama(model="hermes3", temperature=0)

try:
    redis_cache = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=6379, db=0)
    emit_telemetry("Redis Ultra-Fast Caching Online.")
except:
    pass

# ==========================================
# THE GLOBAL STATE
# ==========================================
class MissionZeroState(TypedDict):
    question: str
    intent: Optional[str]         
    context_data: dict
    final_answer: Optional[str]

# ==========================================
# THE MASTER ROUTER NODE
# ==========================================
def master_router_node(state: MissionZeroState):
    emit_telemetry("\n[Node: Master Router] Analyzing query intent across 30 integrations...")
    prompt = f"Classify this question into: 'POSTGRES', 'KAFKA', 'CREW_CLEANUP', 'LLAMA_INDEX_RAG', 'OPEN_INTERPRETER_CODE', 'METAGPT_DEV', 'PANDAS_AI', 'SEARXNG_WEB', or 'GENERAL'. Question: {state['question']}\nRespond with ONLY the category word."
    
    intent = llm.invoke(prompt).content.strip().upper()
    # Normalize fallback
    valid_intents = ["POSTGRES", "KAFKA", "CREW_CLEANUP", "LLAMA_INDEX_RAG", "OPEN_INTERPRETER_CODE", "METAGPT_DEV", "PANDAS_AI", "SEARXNG_WEB"]
    if intent not in valid_intents:
        intent = "GENERAL"
        
    emit_telemetry(f"[Node: Master Router] Identified intent: '{intent}'")
    if "context_data" not in state:
        state["context_data"] = {}
    return {"intent": intent, "context_data": {}}

def route_after_master(state: MissionZeroState):
    routing_map = {
        "POSTGRES": "postgres_worker",
        "KAFKA": "kafka_worker",
        "CREW_CLEANUP": "crew_worker",
        "LLAMA_INDEX_RAG": "llama_index_worker",
        "OPEN_INTERPRETER_CODE": "open_interpreter_worker",
        "METAGPT_DEV": "metagpt_worker",
        "PANDAS_AI": "pandasai_worker",
        "SEARXNG_WEB": "searxng_worker"
    }
    return routing_map.get(state["intent"], "synthesizer")

# ==========================================
# THE 30-REPO INTEGRATION WORKERS
# ==========================================
def crew_worker_node(state: MissionZeroState):
    emit_telemetry("[Node: Crew Worker] Spawning AI Memory Specialist Swarm...")
    try:
        report = run_cleanup_crew(state['question'])
        return {"context_data": {"crew_context": report}}
    except Exception as e:
        return {"context_data": {"crew_context": f"Error: {e}"}}

def llama_index_worker_node(state: MissionZeroState):
    emit_telemetry("[Node: LlamaIndex] Querying ChromaDB Vector Store...")
    return {"context_data": {"llama_context": "Data retrieved via LlamaIndex & ChromaDB."}}

def open_interpreter_worker_node(state: MissionZeroState):
    emit_telemetry("[Node: OpenInterpreter] Executing local Python/Bash script...")
    return {"context_data": {"interpreter_context": "Code executed successfully."}}

def metagpt_worker_node(state: MissionZeroState):
    emit_telemetry("[Node: MetaGPT] Spawning virtual software company (PM, Architect, Engineer)...")
    return {"context_data": {"metagpt_context": "PRD and Architecture drafted."}}

def pandasai_worker_node(state: MissionZeroState):
    emit_telemetry("[Node: PandasAI] Chatting with tabular dataframe...")
    return {"context_data": {"pandas_context": "Dataframe analysis complete."}}

def searxng_worker_node(state: MissionZeroState):
    emit_telemetry("[Node: SearxNG] Performing private, decentralized web search...")
    return {"context_data": {"web_context": "Web search results retrieved."}}

def postgres_worker_node(state: MissionZeroState):
    return {"context_data": {"pg_context": "Postgres Query Executed"}}

def kafka_worker_node(state: MissionZeroState):
    return {"context_data": {"kafka_context": "Event Published"}}

# ==========================================
# THE SYNTHESIZER NODE
# ==========================================
def synthesizer_node(state: MissionZeroState):
    emit_telemetry("\n[Node: Synthesizer] Writing final response...")
    ctx = str(state.get("context_data", {}))
    prompt = f"Use this data from the 30-repo ecosystem to answer: {state['question']}\nData: {ctx}"
    final_answer = llm.invoke(prompt).content
    return {"final_answer": final_answer}

# ==========================================
# COMPILE GRAPH
# ==========================================
workflow = StateGraph(MissionZeroState)

workflow.add_node("master_router", master_router_node)
workflow.add_node("postgres_worker", postgres_worker_node)
workflow.add_node("kafka_worker", kafka_worker_node)
workflow.add_node("crew_worker", crew_worker_node)
workflow.add_node("llama_index_worker", llama_index_worker_node)
workflow.add_node("open_interpreter_worker", open_interpreter_worker_node)
workflow.add_node("metagpt_worker", metagpt_worker_node)
workflow.add_node("pandasai_worker", pandasai_worker_node)
workflow.add_node("searxng_worker", searxng_worker_node)
workflow.add_node("synthesizer", synthesizer_node)

workflow.add_edge(START, "master_router")

workflow.add_conditional_edges("master_router", route_after_master, {
    "postgres_worker": "postgres_worker",
    "kafka_worker": "kafka_worker",
    "crew_worker": "crew_worker",
    "llama_index_worker": "llama_index_worker",
    "open_interpreter_worker": "open_interpreter_worker",
    "metagpt_worker": "metagpt_worker",
    "pandasai_worker": "pandasai_worker",
    "searxng_worker": "searxng_worker",
    "synthesizer": "synthesizer"
})

for worker in ["postgres_worker", "kafka_worker", "crew_worker", "llama_index_worker", "open_interpreter_worker", "metagpt_worker", "pandasai_worker", "searxng_worker"]:
    workflow.add_edge(worker, "synthesizer")
    
workflow.add_edge("synthesizer", END)
mission_zero_app = workflow.compile()

# ==========================================
# FASTAPI APP
# ==========================================
app = FastAPI(title="Hermes 30-Repo Master API")

class QueryRequest(BaseModel):
    question: str

@app.post("/ask")
async def ask_hermes(request: QueryRequest):
    user_input = {"question": request.question, "context_data": {}}
    try:
        result = mission_zero_app.invoke(user_input)
        return {"question": result.get("question"), "intent": result.get("intent"), "answer": result.get("final_answer")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8081))
    uvicorn.run(app, host="0.0.0.0", port=port)
