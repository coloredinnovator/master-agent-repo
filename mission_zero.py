# /// script
# dependencies = [
#   "langchain-core",
#   "langchain-openai",
#   "langchain-ollama",
#   "langchain-neo4j",
#   "google-cloud-storage",
#   "langgraph",
# ]
# ///

import os
from typing import TypedDict, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_neo4j import Neo4jGraph
from google.cloud import storage
from langgraph.graph import StateGraph, START, END

# ==========================================
# MODEL CONFIGURATION (CLOUD VS LOCAL OLLAMA)
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
    """Helper to invoke LLM with a robust fallback if local/cloud API is offline."""
    try:
        response = llm.invoke(prompt_text)
        return response.content
    except Exception as e:
        # Fallback response for offline simulation
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
# 1. THE GLOBAL STATE (BRAIN MEMORY)
# ==========================================
class MissionZeroState(TypedDict):
    question: str                 # The prompt you type
    intent: Optional[str]         # Master Agent classifies: 'graph_search' or 'chat'
    cypher_query: Optional[str]   # Worker writes the Neo4j search query
    graph_context: Optional[str]  # The raw data pulled from your records + GCS
    final_answer: Optional[str]   # The synthesizer's polished output

# ==========================================
# 2. THE MASTER ROUTER NODE
# ==========================================
def master_router_node(state: MissionZeroState):
    """Classifies the prompt to route to the correct worker."""
    print("\n[Node: Master Router] Analyzing query intent...")
    prompt = f"Does this question require searching our business strategy knowledge graph? Question: {state['question']}"
    
    response_content = call_llm(
        prompt + " Answer only YES or NO.",
        fallback_response="YES"  # Simulated fallback
    )
    
    intent = "graph_search" if "YES" in response_content.upper() else "general_chat"
    print(f"[Node: Master Router] Identified intent: '{intent}'")
    return {"intent": intent}

def route_after_master(state: MissionZeroState):
    """Conditional logic telling LangGraph where to route after the master router."""
    if state["intent"] == "graph_search":
        return "graph_worker"
    return "gcs_loader"

# ==========================================
# 3. THE AUTONOMOUS GRAPH WORKER NODE
# ==========================================
def graph_worker_node(state: MissionZeroState):
    """Autonomously translates the prompt to Cypher, runs it, and saves context."""
    print("\n[Node: Graph Worker] Generating Cypher query based on ontology...")
    
    mock_query = "MATCH (p:Project {name: 'Delta'})-[:EVOLVED_INTO]->(n) RETURN p, n;"
    mock_context = "[{'p.name': 'Project Delta', 'n.name': 'Project Mission Zero', 'evolution': 'LangGraph implementation'}]"
    
    if not db_connected:
        print("[Node: Graph Worker] Simulated database mode active.")
        return {"cypher_query": mock_query, "graph_context": mock_context}
        
    schema = graph_db.get_schema()
    query_prompt = f"Write a Neo4j Cypher query to answer the user's question based on this schema: {schema}\nQuestion: {state['question']}\nReturn ONLY the valid Cypher query code."
    
    cypher_query = call_llm(query_prompt, fallback_response=mock_query).strip()
    
    # Strip markdown wrappers if returned by model
    if cypher_query.startswith("```"):
        lines = cypher_query.splitlines()
        cypher_query = "\n".join([line for line in lines if not line.startswith("```")])
        
    print(f"[Node: Graph Worker] Cypher query: {cypher_query}")
    
    try:
        print("[Node: Graph Worker] Querying GraphRAG database...")
        raw_results = graph_db.query(cypher_query)
        context = str(raw_results)
    except Exception as e:
        context = mock_context
        print(f"[Node: Graph Worker] Warning: query failed ({e}), using fallback dataset.")
        
    return {"cypher_query": cypher_query, "graph_context": context}

# ==========================================
# 4. THE GOOGLE CLOUD STORAGE CONTEXT LOADER NODE
# ==========================================
def gcs_loader_node(state: MissionZeroState):
    """Autonomously fetches operational doctrine context from Google Cloud Storage to ground the synthesis."""
    print("\n[Node: GCS Loader] Downloading operational doctrine from gs://marooncleanup...")
    try:
        # Initializes GCS storage client using ambient credentials
        client = storage.Client()
        bucket = client.bucket("marooncleanup")
        blob = bucket.blob("OPERATIONAL_DOCTRINE.md")
        if blob.exists():
            doctrine = blob.download_as_text()
            print("[Node: GCS Loader] Successfully loaded OPERATIONAL_DOCTRINE.md from GCS.")
            gcs_context = f"\n=== GCS Grounding Context (OPERATIONAL_DOCTRINE.md) ===\n{doctrine}"
        else:
            gcs_context = "\n[GCS Loader] Info: OPERATIONAL_DOCTRINE.md not found in bucket."
            print("[Node: GCS Loader] OPERATIONAL_DOCTRINE.md not found in bucket.")
    except Exception as e:
        gcs_context = f"\n[GCS Loader] Warning: Failed to retrieve GCS context: {e}"
        print(f"[Node: GCS Loader] Warning: GCS credentials or access failed: {e}")

    existing = state.get("graph_context") or ""
    return {"graph_context": existing + gcs_context}

# ==========================================
# 5. THE SYNTHESIZER NODE (THE WRITER)
# ==========================================
def synthesizer_node(state: MissionZeroState):
    """Takes raw context or general input and generates a cohesive answer."""
    print("\n[Node: Synthesizer] Writing final response...")
    
    if state.get("graph_context"):
        prompt = f"Use this raw graph and storage data to answer the question: {state['graph_context']}\nQuestion: {state['question']}"
    else:
        prompt = f"Answer this general business question: {state['question']}"
        
    fallback_text = (
        "Project Delta was our legacy sandbox repository for experimental scripts. "
        "It evolved into 'Mission Zero'—a NASA-grade cleanup orchestrator. This new engine integrates LangGraph, "
        "LangChain, Google Cloud SDK, and Chroma vector database memory, directly syncing local resources with "
        "the GCS bucket gs://marooncleanup."
    )
    
    final_answer = call_llm(prompt, fallback_response=fallback_text)
    return {"final_answer": final_answer}

# ==========================================
# 6. COMPILING THE DIRECTED CYCLIC GRAPH
# ==========================================
workflow = StateGraph(MissionZeroState)

# Add nodes
workflow.add_node("master_router", master_router_node)
workflow.add_node("graph_worker", graph_worker_node)
workflow.add_node("gcs_loader", gcs_loader_node)
workflow.add_node("synthesizer", synthesizer_node)

# Define edges
workflow.add_edge(START, "master_router")

workflow.add_conditional_edges(
    "master_router",
    route_after_master,
    {
        "graph_worker": "graph_worker",
        "gcs_loader": "gcs_loader"
    }
)

# Flow graph results into GCS grounding context, then synthesize
workflow.add_edge("graph_worker", "gcs_loader")
workflow.add_edge("gcs_loader", "synthesizer")
workflow.add_edge("synthesizer", END)

# Compile
mission_zero_app = workflow.compile()
print("LangGraph State Machine successfully compiled.")

# ==========================================
# EXECUTION ENTRY POINT
# ==========================================
if __name__ == "__main__":
    user_input = {"question": "What tools did we map out for Project Delta, and did they evolve into anything new?"}
    print(f"Streaming LangGraph Execution for question: '{user_input['question']}'")
    
    final_state = None
    for event in mission_zero_app.stream(user_input):
        for node_name, node_state in event.items():
            print(f"--- Just finished executing: {node_name} ---")
            final_state = node_state
            
    print("\n====================")
    print("Final Answer:")
    print("====================")
    
    # Safely fetch result
    if final_state and "final_answer" in final_state:
        print(final_state["final_answer"])
    else:
        result = mission_zero_app.invoke(user_input)
        print(result["final_answer"])
