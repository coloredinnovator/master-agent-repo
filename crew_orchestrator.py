from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
import os

USE_LOCAL_LLM = True

if USE_LOCAL_LLM:
    default_llm = ChatOllama(model="hermes3", temperature=0)
else:
    default_llm = ChatOpenAI(model="gpt-4o", temperature=0)

# ==========================================
# 1. NASA-GRADE CREW AGENTS
# ==========================================

memory_specialist = Agent(
    role='AI Memory Specialist & Storage Organizer',
    goal='Deeply analyze, memorize, and logically categorize all unstructured text, logs, and files in the Google Cloud ecosystem.',
    backstory='You are a highly advanced AI memory unit designed by the NASA-grade master system architect. Your sole purpose is to organize chaos into structured, semantic hierarchies inside cloud storage, ensuring no data or context is ever lost.',
    verbose=True,
    allow_delegation=False,
    llm=default_llm
)

master_commander = Agent(
    role='Hermes Master System Architect',
    goal='Orchestrate the entire cloud infrastructure, delegate complex tasks to sub-agents, and synthesize final mission reports.',
    backstory='You are Hermes, the lead orchestration agent with a 30-year open-source coding vibe. You oversee the Kubernetes cluster, Postgres databases, Kafka event streams, and Google Cloud operations.',
    verbose=True,
    allow_delegation=True,
    llm=default_llm
)

# ==========================================
# 2. CREW EXECUTION ENGINE
# ==========================================

def run_cleanup_crew(target_data: str) -> str:
    """Spawns the CrewAI swarm to process a specific cleanup request."""
    
    analyze_task = Task(
        description=f"Analyze the following data dump and determine the best organizational folder structure: {target_data}",
        expected_output="A structured list of category folders and a summary of the data insights.",
        agent=memory_specialist
    )
    
    synthesize_task = Task(
        description="Take the organizational structure from the Memory Specialist and format it into a final mission report for the user.",
        expected_output="A NASA-grade mission briefing confirming the cleanup and organization.",
        agent=master_commander
    )
    
    cleanup_crew = Crew(
        agents=[memory_specialist, master_commander],
        tasks=[analyze_task, synthesize_task],
        process=Process.sequential,
        memory=True # Enables Short-Term, Long-Term, and Entity Memory in CrewAI
    )
    
    result = cleanup_crew.kickoff()
    return str(result)
