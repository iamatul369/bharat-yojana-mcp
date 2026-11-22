# Bharat Central Schemes & Opportunities AI (Hybrid RAG + MCP Server)

An end-to-end, production-deployed AI assistant that helps Indian **Students**, **Startup Founders / MSMEs**, and **Citizens** discover Central Government welfare schemes, scholarships, seed grants, and subsidies—eliminating missed opportunities caused by scattered portals and dense official PDFs.

**Live Public App:** `https://bharat-yojana-mcp.onrender.com/`  

---

## 🎯 Why This Project Matters (Real-World Usefulness)

Every year, crores of rupees in Central Government scholarships, startup seed grants, and household subsidies go unutilized because:
1. **Fragmented Information:** Schemes are scattered across dozens of ministry portals (`scholarships.gov.in`, `startupindia.gov.in`, `myscheme.gov.in`, `pmsuryaghar.gov.in`).
2. **Hidden Eligibility Rules:** Crucial criteria (income ceilings, DPIIT recognition timelines, turnover caps, and subsidy slabs) are buried inside 50-page official ministry PDF guidelines.
3. **LLM Hallucination Risk:** General chatbots often mix up state vs. central rules or cite outdated benefit figures.

**How This Solution Solves It:**
* **Profile-Based Discovery (Structured SQL):** Users simply state who they are (*"1st-year engineering girl student with ₹5L family income"* or *"DPIIT startup incorporated 6 months ago"*), and the AI queries a structured Postgres database to match exact benefit amounts, income limits, and official application links.
* **Clause-Level Accuracy (Vector RAG):** For deep policy questions, the AI performs semantic vector search over chunked official ministry guideline PDFs (`pgvector`) before answering.
* **Universal Accessibility:** Works both as a **free public web chatbot** (zero login required for citizens) and as a **standard Model Context Protocol (MCP) server** that plugs directly into AI IDEs and desktop clients (Claude Desktop, Cursor, VS Code).

---

## 🏗️ End-to-End System Architecture

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                    AUTOMATED WEEKLY DATA PIPELINE                       │
│  GitHub Actions Cron (Every Sunday) ──▶ ingest.py                       │
│    ├── Fetches & parses official Ministry PDFs (pypdf)                  │
│    ├── Pulls structured scheme catalogs & data.gov.in Open APIs         │
│    └── Generates 768-dim embeddings (Gemini Embedding API)              │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │ Upserts SQL + Vectors
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                  CLOUD DATABASE (Supabase PostgreSQL)                   │
│    ├── central_schemes (Structured SQL table for fast profile filters)  │
│    └── central_scheme_docs (pgvector store for semantic PDF retrieval)  │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │ Queries via RPC & PostgREST
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│             HYBRID BACKEND SERVER (Render Docker Container)             │
│  FastAPI + FastMCP (main.py)                                            │
│    ├── GET  /           ──▶ Public Multi-Turn Web Chat UI (index.html)  │
│    ├── POST /chat       ──▶ Gemini Flash Agent + Automatic Tool Calling │
│    ├── ALL  /mcp        ──▶ Native MCP Endpoint (for Claude/VS Code)    │
│    └── GET  /api/*      ──▶ Bearer-Protected REST + OpenAPI Endpoints   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Complete Tech Stack

| Layer | Technology | Role in Project |
| :--- | :--- | :--- |
| **Backend & MCP Protocol** | **Python 3.11, FastAPI, FastMCP** | Dual-protocol server exposing native MCP (`/mcp`), REST APIs (`/api/*`), and the web UI (`/`) from a single container. |
| **LLM Reasoning (The Brain)** | **Google Gemini Flash (`google-genai`)** | Handles multi-turn conversation memory, intent detection, dynamic tool selection, and grounded response synthesis with automatic model fallback. |
| **RAG Embeddings** | **Gemini Embedding (`gemini-embedding-001`)** | Converts official ministry PDF chunks and user queries into 768-dimensional semantic vectors. |
| **Database & Vector Store** | **Supabase (PostgreSQL + `pgvector`)** | Stores structured scheme metadata alongside vector embeddings; executes cosine-similarity search via custom PL/pgSQL RPC functions (`match_central_docs`). |
| **Data Ingestion & ETL** | **GitHub Actions, `pypdf`, `requests`** | Serverless weekly cron pipeline that parses PDFs, syncs `data.gov.in` APIs, and refreshes Supabase automatically. |
| **Frontend UI** | **HTML5, Vanilla JS, CSS3, `marked.js`** | Lightweight, mobile-responsive chat interface with browser-side multi-turn history, Markdown rendering, and automatic cold-start retry handling. |
| **Deployment & Security** | **Docker, Render, IP Rate Limiter** | Containerized deployment with Bearer token authentication on API routes and 30 req/min per-IP rate limiting. |

---

## ⚙️ How RAG & MCP Work Together Here

1. **Tool Registration (`FastMCP` + Gemini Function Calling):**  
   Two core backend functions—`discover_central_schemes` (SQL filter) and `search_scheme_guidelines` (Vector RAG)—are exposed simultaneously as MCP tools and Gemini agent tools.
2. **Dynamic Execution Loop:**  
   When a user asks a question, the LLM inspects the tool schemas, decides whether it needs structured eligibility filtering, deep PDF clause lookup, or both, executes the database queries, and synthesizes a verified response with clickable official portal links.
3. **Zero-Maintenance Freshness:**  
   The `.github/workflows/weekly_sync.yml` pipeline runs automatically every Sunday, ensuring newly added schemes and updated PDF circulars are embedded and live without manual intervention.

---

## 🔌 Connecting to MCP Clients (Claude Desktop / VS Code / Cursor)

Developers and power users can connect this live server directly to any MCP-compatible host:

```json
{
  "mcpServers": {
    "bharat-central-schemes": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://onrender.commcp",
        "--header",
        "Authorization: Bearer token"
      ]
    }
  }
}
```
