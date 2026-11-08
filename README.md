# Text to Query ⚡

> **Intelligent Conversational Data Agent & Polyglot Code Generator**  
> Converts natural language questions into safe, verified, and executable code and formulas across **SQL**, **NoSQL (MongoDB MQL)**, **Python (Pandas)**, **R**, and **Excel Formulas**.

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.14-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-6-646CFF?logo=vite&logoColor=white)](https://vitejs.dev)
[![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-v4-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![Tests](https://img.shields.io/badge/Tests-187%20Passed-success?logo=pytest&logoColor=white)](tests/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

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

### 1. 💬 Conversational Intelligence & Memory
- **4-Turn Context Window**: Maintains a sliding conversational history window to resolve pronouns and coreferences (e.g. *"Show their top 5 invoices"*, *"Filter those by USA"*).
- **Compound Query Decomposition**: Automatically detects multi-intent questions (e.g. *"1. Top sales reps by revenue, 2. Monthly growth rate"*), splits them into discrete sub-queries, and presents them in the UI via sub-query tabs.
- **Out-of-Domain (OOD) Guard**: Gracefully intercepts questions referencing non-existent tables or business concepts, explaining missing schema entities and providing helpful suggestions.

### 2. 🛡️ Zero-Mutation Guardrails & Sandboxing
- **SQL Guard (`sqlglot` AST)**: Strictly permits `SELECT` and `UNION` statements. Automatically blocks mutations (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`) and multi-statement injection attacks.
- **NoSQL Guard (AST Walker)**: Enforces read-only MQL operations (`find`, `aggregate`). Blocks destructive operators (`$set`, `$unset`, `$delete`, `$drop`, `$merge`).
- **Tabular/Pandas AST Sandbox**: Analyzes Python syntax trees via `ast.NodeVisitor`. Blocks unauthorized imports (`os`, `sys`, `subprocess`), system calls (`eval`, `exec`, `open`), loops, and custom function definitions.

### 3. 🔁 3-Attempt Self-Healing Reflection Loop
- If a generated query encounters syntax or execution errors (e.g. invalid column name or type mismatch), the error traceback and live schema are reflected back to the LLM.
- Automatically repairs the query in up to **3 iterative attempts** before presenting the result.

### 4. ⚖️ LLM-as-a-Judge Evaluation & Telemetry
- A secondary evaluation pass analyzes the generated code against user intent and execution output.
- Returns a semantic **confidence score (0.0 to 1.0)**, execution latency metrics, retry counts, and a concise natural language explanation.

### 5. 🖥️ Modern Web UI (React 19 + Tailwind CSS v4)
- **Adaptive Data Viewer**: Seamlessly renders relational and spreadsheet data in virtualized **Data Tables** (with CSV & JSON export) and document collections in an expandable **JSON Tree Viewer**.
- **Interactive ER Canvas**: Draggable schema diagram with dynamic cubic bezier SVG lines connecting foreign keys to primary keys.
- **Dialect Switcher**: Live code card allowing instant syntax highlighting and one-click polyglot conversion.
- **Dataset Manager**: Upload standalone files or merged multi-file datasets (`.db`, `.sqlite`, `.json`, `.bson`, `.csv`, `.xlsx`).

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
└── tests/                             # 187 comprehensive unit & integration tests
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

## 🧪 Testing & Verification

The test suite contains **187 automated tests** covering AST guardrails, dialect engines, router pipelines, self-healing reflection loops, and session storage:

```powershell
# Run all backend tests
pytest tests/

# Run frontend linting & production build check
cd frontend
npm run lint
npm run build
```

---

## 💡 Example Queries by Dialect

| Dialect | Example Natural Language Prompt | Generated Code / Output |
|---|---|---|
| **SQL** | *"Which 5 artists have the most tracks in the catalog?"* | `SELECT Artist.Name, COUNT(Track.TrackId) AS TrackCount FROM Artist JOIN Album ... LIMIT 5;` |
| **NoSQL (MQL)** | *"Find all electronics products with rating above 4.5 sorted by price"* | `db.products.find({"category": "Electronics", "rating": {"$gt": 4.5}}).sort({"price": -1})` |
| **Python (Pandas)** | *"Calculate total sales and profit margin grouped by region"* | `result_df = df.groupby('Region').agg({'Sales': 'sum', 'Profit': 'sum'}).reset_index()` |
| **Excel Formulas** | *"Sum the revenue in column C where status in column D is Completed"* | `=SUMIFS(C:C, D:D, "Completed")` |
| **R (Tidyverse)** | *"Filter active customers and count orders per state"* | `customers %>% filter(status == 'Active') %>% count(state, sort = TRUE)` |

---

## 🔒 Security & Data Protection

- **Read-Only Invariant**: Guardrails strictly forbid state-mutating operations (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`).
- **Sandbox Isolation**: Arbitrary OS access, network sockets, subprocessing, and file writes are barred at the AST parsing layer.
- **Protected System Datasets**: Default datasets are immutable and safe from accidental deletion.
- **Secret Hygiene**: API credentials are read exclusively from local `.env` files and never tracked in Git.

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.
