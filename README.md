# Text to Query ⚡

> **Intelligent Conversational Data Agent & Polyglot Code Generator**  
> Converts natural language questions into safe, verified, and executable code and formulas across **SQL**, **NoSQL (MongoDB MQL)**, **Python (Pandas)**, **R**, and **Excel Formulas**.

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.14-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-6-646CFF?logo=vite&logoColor=white)](https://vitejs.dev)
[![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-v4-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com)

---

## 🌟 Overview

**Text to Query** is a polyglot AI chatbot that transforms how developers and analysts interact with data. Traditional "Text-to-SQL" tools are strictly limited to relational tables. **Text to Query** supports multiple heterogeneous data paradigms:

- 🗄️ **Relational Databases (SQL)**: Generates and executes SQLite ANSI queries with live schema introspection and foreign key awareness.
- 📦 **NoSQL Document Stores (MQL)**: Processes JSON, JSONL, and BSON document collections using in-memory MongoDB-compatible aggregation and filter pipelines.
- 🐼 **Python (Pandas)**: Generates vectorized DataFrame operations executed inside an AST-sandboxed runtime.
- 📊 **Excel Workbooks & Formulas**: Produces coordinate-aware modern Excel formulas (`=SUMIFS`, `=XLOOKUP`, `=FILTER`) and executes multi-sheet calculations.
- 📈 **R (Tidyverse)**: Generates production-ready R scripts for statistical analysis.
- 🔄 **Polyglot Cross-Converter**: Instantly converts generated queries between SQL, Pandas, R, MQL, and Excel formulas with a single click.

---

## 🚀 Key Features

- **Conversational Memory**: Remembers context across multi-turn chats and resolves pronouns (`"their sales"`, `"filter those"`).
- **Multi-Dialect Query Generation**: Converts plain English into SQL, NoSQL (MongoDB MQL), Python (Pandas), R, and Excel formulas.
- **One-Click Code Conversion**: Instantly converts queries and code blocks between all supported programming dialects.
- **Compound Query Splitter**: Automatically decomposes multi-part questions into tabbed sub-queries.
- **AST Security Guardrails**: Strictly enforces read-only execution and blocks dangerous mutations, unauthorized imports, or system calls.
- **Self-Healing Reflection**: Automatically catches execution/schema errors and repairs queries up to 3 times.
- **LLM-as-a-Judge**: Evaluates query results against user intent and provides a confidence score and summary.
- **Adaptive Data Visualizations**: Interactive data tables with CSV/JSON export, collapsible JSON tree viewer, and dynamic ER diagram canvas.

---

## 🏛️ System Architecture

```text
Text to Query
├── backend/
│   ├── config.py                      # Centralized configuration, filesystem paths & .env loader
│   ├── main.py                        # FastAPI application entry point, CORS & lifecycle
│   ├── data/                          # Data directory
│   │   ├── databases.json             # Master registry of active and uploaded datasets
│   │   ├── default/                   # Protected system default datasets
│   │   │   ├── db/                    # Chinook Music Store (chinook.db)
│   │   │   ├── json/                  # E-Commerce Store (ecommerce_store.json)
│   │   │   ├── csv/                   # Sales Performance (sales_performance.csv)
│   │   │   └── xlsx/                  # Financial Budget (financial_budget.xlsx)
│   │   ├── uploads/                   # User-uploaded datasets categorized by extension
│   │   └── chat-storage/              # Persistent chat session store (chat_history.json)
│   └── src/
│       ├── api/                       # Pure functional REST routers & Pydantic schemas
│       │   ├── chat_routes.py         # Chat sessions, streaming queries & polyglot conversion
│       │   ├── databases_routes.py    # Dataset upload, append, schema introspection
│       │   └── schemas.py             # Pydantic v2 request/response models
│       ├── core/                      # Core AI algorithms
│       │   ├── decomposition.py       # Multi-query intent splitter
│       │   ├── evaluator.py           # LLM-as-a-Judge semantic confidence scoring
│       │   ├── llm.py                 # OpenAI / Groq client singleton
│       │   ├── polyglot.py            # 8-language code converter & dialect badges
│       │   └── reflection.py          # 3-attempt self-healing reflection loop
│       ├── dialects/                  # Cohesive vertical domain engines & AST guardrails
│       │   ├── base.py                # Universal path resolvers & scalar JSON normalizer
│       │   ├── sql.py                 # sqlglot AST guardrail & SQLite query execution
│       │   ├── nosql.py               # MQL operator blockers & in-memory aggregation
│       │   └── tabular.py             # Python AST sandbox, spreadsheet loader & formula engine
│       ├── pipelines/                 # Orchestration & prompts
│       │   ├── prompts.py             # Prompt catalog, conversational window & pronoun resolution
│       │   └── router.py              # Master pipeline dispatcher & dialect router
│       └── storage/                   # Stateless persistence
│           ├── chat_store.py          # Session history CRUD & message appending
│           └── registry.py            # Dataset catalog CRUD, conflict checks & upload handlers
├── frontend/
│   ├── src/
│   │   ├── App.jsx                    # Root state coordinator & URL state synchronizer
│   │   ├── components/
│   │   │   ├── ChatInput.jsx          # Prompt input bar with dialect selector
│   │   │   ├── ChatMessage.jsx        # Message bubble dispatcher (DataTable vs JsonViewer)
│   │   │   ├── DataTable.jsx          # Tabular data grid with CSV/JSON export
│   │   │   ├── JsonDocumentViewer.jsx # Collapsible JSON document tree viewer
│   │   │   ├── QueryCodeCard.jsx      # Code card with dialect badge & inline converter
│   │   │   ├── SchemaMapModal.jsx     # Draggable visual ER diagram canvas
│   │   │   ├── DatasetSelectorPopover.jsx # Top navigation dataset selector & deletion
│   │   │   ├── UploadDatasetModal.jsx # Multi-modal dataset uploader
│   │   │   ├── TelemetryPopover.jsx   # Execution telemetry (confidence, latency, retries)
│   │   │   └── Sidebar.jsx            # Resizable sidebar with chat sessions & schema explorer
│   │   └── utils/
│   │       └── sampleQuerySuggestions.js # Dataset-aware query suggestion chip generator
│   └── package.json
└── requirements.txt                   # Unified requirements covering backend and frontend
```

---

## 🛠️ Quickstart Guide

### Prerequisites
- **Python**: 3.11+ (Anaconda / Miniconda recommended)
- **Node.js**: 18+ & **npm**

---

### 1. Backend Setup

```powershell
# Clone the repository
git clone https://github.com/your-username/text-to-query.git
cd text-to-query/backend

# Create or activate your Python environment
# e.g., using conda:
conda create -n text-to-query python=3.11 -y
conda activate text-to-query

# Install Python dependencies
pip install -r requirements.txt

# Configure your environment variables
cp .env_example .env
```

Open `backend/.env` and provide your Groq or OpenAI API key:
```ini
API_KEY="gsk_your_groq_api_key_here"
MODEL="llama-3.3-70b-versatile"
API_URL="https://api.groq.com/openai/v1"
DATABASE_URL="sqlite:///chinook.db"
```

Start the FastAPI backend server:
```powershell
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
*API docs and OpenAPI spec will be live at: `http://localhost:8000/docs`*

---

### 2. Frontend Setup

In a new terminal window:
```powershell
cd text-to-query/frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```
*Open your browser at: `http://localhost:5173`*

---

## 🔒 Security & Data Protection

- **Read-Only Invariant**: Guardrails strictly forbid state-mutating operations (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`).
- **Sandbox Isolation**: Arbitrary OS access, network sockets, subprocessing, and file writes are barred at the AST parsing layer.
- **Protected System Datasets**: Default datasets are immutable and safe from accidental deletion.
- **Secret Hygiene**: API credentials are read exclusively from local `.env` files and never tracked in Git.
