# MAROON ECOSYSTEM — MASTER MAP
**Read this file first. Then read GROUND_TRUTH.md. Then go to the repo you're working on.**

Audited by: Claude Sonnet 4.6, 2026-06-21
For: Claude Opus 4.8 (extended thinking) — production build pass
Founder: non-engineer, vision/product owner. Defer to their intent, not their literal phrasing.

---

## What this system is, in one paragraph

Maroon OS is a massively distributed **38-repository** agentic platform. At its core, it ingests public/government data, runs it through entity-resolution and clustering algorithms, and routes intelligence via a sovereign privacy layer. Surrounding this core is a vast network of **Industry Verticals** (e.g., Farming, Medical, Logistics, Real Estate) and **Economic Hubs** (Marketplaces, Financials) that will eventually consume the core intelligence and act as edge-nodes for data collection and specialized agentic tasks. 

## The 38 Repositories

The ecosystem is divided into functional layers. Note that while the Core OS has structural code, many of the Industry Verticals are currently in a foundational bootstrap state (containing boilerplate `agent-contract.yaml`, `audit.yml`, `config.yaml`, `main.py`, and `terraform/` configurations) and await wiring to the main data pipelines.

### Layer 1: Core OS & Kernel
The foundational infrastructure and raw compute logic.
* `maroon-os-core`
* `maroon-kernel`
* `Maroon-Ecosystem-Root`
* `maroon-terminal`

### Layer 2: Agents & Orchestration
The brains of the operation. Contains the dispatcher (Kiro) and the worker nodes (Master Agent).
* `maroon-os-agents`
* `maroon-kiro`
* `project-kiro-orchestrator`
* `master-agent-repo`
* `maroon-assistant`

### Layer 3: Data, Privacy & Security
The ingestion pipelines, data sanitization, OSINT gathering, and the cryptographic privacy layer (Shibboleth protocol).
* `maroon-os-data`
* `maroon-os-sovereignty`
* `maroon-os-cyber-intel`
* `maroon-osint`
* `maroon-clean-up`
* `marooncleanup`
* `maroon-safespace`
* `maroon-safespace-core`

### Layer 4: Infrastructure & Skills
The Terraform IaC definitions and the mathematical clustering algorithms.
* `maroon-os-infrastructure`
* `maroon-os-skills`
* `maroon-terraform-live`
* `maroon-infrastructure`

### Layer 5: Marketplaces & Economy
The financial and transactional hubs.
* `Maroon-Market`
* `maroon-market-fork`
* `Onitas-market-`
* `maroon-financials`
* `maroon-equity`

### Layer 6: Industry Verticals
The specialized consumer and edge-node products.
* `maroon-farming`
* `maroon-logistics`
* `maroon-medical`
* `maroon-media`
* `maroon-netflix`
* `maroon-gaming`
* `maroon-estate`
* `maroon-staffing`
* `maroon-pac`
* `maroon-patreon`

### Layer 7: Web/Frontend
User-facing portals.
* `coloredinnovator-project`
* `maroon-website`

## The Honest Dependency Graph
```
INTENDED FUTURE STATE:
  [Industry Verticals] <---> [Marketplaces]
           ^                       ^
           |                       |
           v                       v
      [Sovereignty & Privacy Layer (Shibboleth)]
           ^                       ^
           |                       |
           v                       v
      [OS Agents] <---> [Core Data & Skills Pipeline]
```

## Standing Rules for Every Repo
- **IaC only.** Any cloud resource = Terraform.
- **No claim survives without an artifact.** Every claim of "tested" must link to a committed test file.
- **GAPS.md is append-only.** Mark resolved, never delete.
