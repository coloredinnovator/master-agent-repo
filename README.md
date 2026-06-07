# Hermes — NASA-Grade Multi-Agent Cloud Orchestrator

A production-hardened, multi-cloud AI agent ecosystem built on **LangGraph**, **CrewAI**, and **HuggingFace**. Designed for a solo developer who needs zero-mistake, Cloud-Inspector-compliant infrastructure across GCP, AWS, and Azure.

## Architecture

```
User Request
    │
    ▼
┌──────────────┐
│ FastAPI /ask  │
└──────┬───────┘
       ▼
┌──────────────┐     ┌────────────────┐
│ Master Router│────▶│ Intent Classify │
└──────┬───────┘     └────────────────┘
       │
       ├──▶ Postgres Worker (psycopg2, real SQL)
       ├──▶ BigQuery Worker (google-cloud-bigquery)
       ├──▶ Kafka Worker (confluent-kafka, Redpanda)
       ├──▶ GCS Worker (google-cloud-storage)
       ├──▶ Crew Worker (CrewAI swarm + AI Memory Specialist)
       ├──▶ Web Worker (SearxNG)
       │
       ▼
┌──────────────┐
│  Synthesizer │ → Final Answer
└──────────────┘
```

## Quick Start

```bash
# 1. Copy environment template
cp .env.example .env
# Edit .env with your real credentials

# 2. Spin up infrastructure
docker compose up -d

# 3. Test health
curl http://localhost:8080/health

# 4. Ask a question
curl -X POST http://localhost:8080/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What tables exist in my Postgres database?"}'
```

## Multi-Cloud Terraform

Deploy to any cloud provider:

```bash
# GCP
cd terraform/gcp && terraform init && terraform plan

# AWS
cd terraform/aws && terraform init && terraform plan

# Azure
cd terraform/azure && terraform init && terraform plan
```

## Project Structure

```
├── mission_zero.py        # LangGraph orchestrator (FastAPI entry point)
├── crew_orchestrator.py   # CrewAI swarm (AI Memory Specialist)
├── drive_cleaner.py       # Google Drive → GCS migration tool
├── bq_exporter.py         # BigQuery backup to GCS
├── ai_studio_organizer.py # AI Studio content categorizer
├── Dockerfile             # Production container
├── docker-compose.yml     # Full local infrastructure stack
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variable template
├── k8s/                   # Kubernetes manifests
│   ├── secrets.yaml       # K8s Secret objects
│   ├── postgres-deployment.yaml
│   ├── kafka-deployment.yaml
│   └── hermes-deployment.yaml
├── terraform/             # Multi-cloud IaC
│   ├── gcp/main.tf
│   ├── aws/main.tf
│   └── azure/main.tf
├── OPERATIONAL_DOCTRINE.md
└── AGENT_CHARTER.md
```

## Security

- All secrets managed via `.env` files and K8s Secrets — **zero hardcoded credentials**
- S3/GCS buckets enforce **encryption at rest** and **block public access**
- IAM follows **least privilege** principle
- Docker images built with `.dockerignore` to exclude `.git` and secrets