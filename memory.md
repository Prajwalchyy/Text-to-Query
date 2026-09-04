# 🧠 Master Project Memory & Architecture Context

> **Single Source of Truth for Future Sessions & Agents.**
> Read this file first when starting a new session to understand the complete codebase architecture, user preferences, implemented features, and roadmap.

---

## 📌 1. Project Overview & Technology Stack
* **Project Name:** Enterprise Multi-Source Data Intelligence Engine (Text-to-SQL & Text-to-NoSQL).
* **Backend:** Python 3.12, FastAPI, Uvicorn, SQLAlchemy, SQLite3, OpenAI/Gemini SDK.
* **Frontend:** React 19, Vite, Tailwind CSS v4, Lucide React icons.
* **Storage:** Human-readable JSON files (`chat_history.json`, `databases.json`).

---

## 🏛️ 2. Core Backend Architecture & File Map

```text
backend/
├── main.py                          # Slim 45-line entry point (CORS, router mounts, /api/health)
├── requirements.txt                 # Backend Python dependencies
├── data/
│   ├── databases.json               # Registry of all installed SQL and NoSQL databases
│   ├── chat_history.json            # Persistent conversational chat storage
│   ├── chinook.db                   # System Default SQL Database (Locked/Permanent)
│   ├── nosql_default/
│   │   └── ecommerce_store.json     # System Default NoSQL Database (4 Collections, Locked)
│   ├── relational/                  # 🗄️ Uploaded Relational SQL Databases (.db, .sqlite, .sqlite3, .sql)
│   ├── nosql/                       # 📄 Uploaded NoSQL Document Collections (.json, .jsonl)
│   ├── csv/                         # 📊 Uploaded CSV Datasets (.csv) [Ready for Phase 3]
│   └── excel/                       # 📈 Uploaded Excel Spreadsheets (.xlsx, .xls) [Ready for Phase 2]
│
└── src/
    ├── F00_imports.py               # Shared SDK imports & environment loaders
    ├── F01_db_engine.py             # SQLAlchemy connection & PRAGMA schema introspection
    ├── F02_generator.py             # SQL Query prompt generator via LLM
    ├── F03_guardrails.py            # 4-Layer SQL safety: sqlglot AST parsing, keyword blocking, allowlists
    ├── F04_self_correction.py       # 3-Attempt self-repair loop for SQL syntax/schema errors
    ├── F05_evaluator.py             # Hallucination evaluator & confidence scoring
    ├── F06_pipeline.py              # End-to-end Text-to-SQL pipeline
    ├── F07_chat_storage.py          # Chat session CRUD and JSON persistence
    ├── F08_database_registry.py     # Multi-format dataset registry (SQL & NoSQL)
    ├── F09_nosql_engine.py          # Multi-collection in-memory MongoDB MQL execution engine
    ├── F10_nosql_generator.py       # Multi-collection MQL prompt synthesizer
    ├── F11_nosql_guardrails.py      # NoSQL Read-Only guardrail, collection parser, chained .limit()
    ├── F12_nosql_pipeline.py        # End-to-end Text-to-NoSQL pipeline with 3-step self-repair
    │
    ├── controllers/                 # Business Logic Layer
    │   ├── database_controller.py   # Dataset uploads, schema introspection, pipeline caching
    │   └── chat_controller.py       # Chat CRUD, title renames, query routing (SQL vs NoSQL)
    │
    └── routes/                      # FastAPI Route Endpoints
        ├── database_routes.py       # /api/databases, /api/databases/upload, /api/tables
        └── chat_routes.py           # /api/chats, /api/chats/{id}, /api/chats/{id}/query
```
---

## ⚛️ 3. Frontend Architecture & Components

```text
frontend/src/
├── App.jsx                          # Main chat view, URL state persistence, top bar dataset dropdown
├── components/
│   ├── Sidebar.jsx                  # ChatGPT-style left sidebar: chats, inline rename, schema search
│   ├── ChatMessage.jsx              # Message bubble: routes SQL to DataTable and NoSQL to JsonDocumentViewer
│   ├── ChatInput.jsx                # Expanded bottom prompt bar with multi-line textarea
│   ├── SqlCodeBlock.jsx             # Code box for SQLite Dialect & MongoDB MQL with copy button & local scroll
│   ├── DataTable.jsx                # SQL result table with horizontal/vertical bounds & custom scrollbars
│   ├── JsonDocumentViewer.jsx       # Collapsible interactive JSON tree viewer with syntax colors
│   ├── SchemaMapModal.jsx           # Draggable Visual ER Diagram canvas with live stretching SVG connector lines
│   ├── DatabaseSelectorPopover.jsx  # Floating popover modal with categorized datasets, search, & active checkmarks
│   ├── UploadDbModal.jsx            # Multi-format dataset manager (.db, .sqlite, .json, .jsonl)
│   └── DetailsPopover.jsx           # Diagnostic telemetry, confidence score, latency, guardrail errors
└── index.css                        # Tailwind v4 base styles and sleek .custom-scrollbar utilities
```

---

## 🚀 4. Key Implemented Features

### 🗄️ A. Multi-Model Data Support (SQL & NoSQL in Same Chat)
* **SQL Relational Engine:** Queries `.db`, `.sqlite`, `.sqlite3`, `.s3db`, `.sl3`, and **`.sql` scripts/dumps** (automatically executes SQL DDL/DML into an active SQLite database). Introspects tables/columns, generates SQL, validates with `sqlglot` AST.
* **Dual Upload Modes (Full Database vs. Multiple Tables / Collections Merge):**
  * **Full Database(s) Mode:**
    * Single database upload (`.db`, `.sqlite`, `.sql`, `.json`, `.bson`).
    * **Bulk Import:** Multi-select any number of standalone database files (e.g. 5 `.db` files or multiple `.json` datasets) to register them in bulk with auto-derived display names.
  * **Multiple Tables / Collections (Merge) Mode:**
    * **SQL:** Multi-select `.sql` table script dumps (e.g. `customers.sql`, `orders.sql`, `products.sql`); merges them sequentially into a single unified `.db` database for multi-table `JOIN` queries.
    * **NoSQL:** Multi-select separate collection files (e.g. `users.json`, `orders.json`, `reviews.bson`); compiles them into a unified multi-collection JSON dataset for cross-collection aggregation pipelines.
* **Granular Table & Collection Appending (`[ + Add Table ]` & `[ + Add Collection ]`):**
  * Click `+ Add Table` on any custom SQL database to upload an additional `.sql` table script.
  * Click `+ Add Collection` on any custom NoSQL database to upload an additional `.json`, `.jsonl`, or `.bson` collection.
  * **Collision & Overwrite Guardrails:** Proactively checks for table or collection name collisions before execution. Returns HTTP 409 Conflict and prompts an interactive amber warning modal offering 'Overwrite & Replace' (safely drops the old table/collection first) or 'Cancel', preventing data corruption and accidental duplicates.
* **NoSQL Document Engine:** Queries `.json`, `.jsonl`, and **MongoDB Binary `.bson` files** (automatically decodes BSON streams, serializing ObjectIds and timestamps). Introspects nested fields, generates MongoDB MQL (`db.collection.aggregate()`, `db.collection.find()`), and executes in-memory.
* **Connected NoSQL Collections:** `ecommerce_store.json` contains 4 streamlined collections with strictly 5–6 fields max: `customers` (30 docs), `products` (12 docs), `orders` (40 docs), and `reviews` (25 docs).

### 🛡️ B. Defense-in-Depth Safety
* **SQL:** Blocks destructive keywords (`DROP`, `DELETE`, `UPDATE`, `ALTER`, `TRUNCATE`, `GRANT`) and verifies tables against real-time metadata.
* **NoSQL:** Blocks destructive operators (`$drop`, `$deleteMany`, `$deleteOne`, `$updateMany`, `$out`, `$merge`) and enforces Read-Only queries.
* **Self-Correction:** 3-attempt self-repair loop on both SQL and NoSQL pipelines.

### 🌐 C. URL-Based State Persistence (ChatGPT-Style)
* Active Chat ID and Selected Database ID are synchronized directly in the URL: `http://localhost:5173/?chat=...&db=ecommerce_store`.
* **Zero-Reset on Refresh (`F5`):** Retains exact active chat and database.
* **Browser Navigation (`←` / `→`):** Supports browser back/forward buttons via `popstate` listeners.

### 🎨 D. UI / UX Design Standards
* **High Signal-to-Noise:** Successful queries only show the Code Block + Data Output (no chatty paragraphs). Technical diagnostics are inside the `DetailsPopover`.
* **Adaptive Output Format:**
  * SQL queries render the **Data Table** (with sticky headers and horizontal/vertical scroll bounds).
  * NoSQL queries render the **JSON Document Viewer** (individual collapsible document cards with syntax highlighting).
* **Expanded Viewport:** Wide layout (`max-w-5xl xl:max-w-6xl`) eliminates wasted desktop margins.
* **Searchable Left Sidebar:** Real-time filter across tables and columns with independent multi-table expansion (`Set`).
* **Resizable & Collapsible Sidebar:** Freeform horizontal drag-handle on the right edge (220px to 500px, double-click to reset), 1-click total collapse to 0px (`PanelLeftClose`), top navbar reopen button (`PanelLeftOpen`), `Ctrl+B` global keyboard shortcut, and `localStorage` persistence.
* **Elevated Header Stacking Context:** Top `<header>` configured with `relative z-30` and `DatabaseSelectorPopover` with `z-40 / z-50`, ensuring floating dropdown menus always float cleanly above sticky table headers (`z-10`) with zero z-index clipping or interference.
* **Non-Blocking Inline Delete Confirmation:** Replaced native `window.confirm()` with a 2-step inline `[ Confirm ]` / `[ Cancel ]` button in `UploadDbModal` and added 1-click delete support with inline confirmation directly inside `DatabaseSelectorPopover`. When deleting the active database, automatically falls back to `chinook`, reloads schema, and synchronizes URL params.

---

## ⚠️ 5. Critical User Guidelines & Preferences (MUST FOLLOW)

1. **NO Unnecessary Git Commits:**
   * **MANDATE:** NEVER run `git commit` automatically after changes.
   * **RULE:** ONLY commit when the user explicitly types `"push"`, `"commit"`, or issues a git commit command.
2. **Explicit User Approval:**
   * Always explain what will change and ask for user permission before creating or editing files.
3. **Explicit `==` Coding Style:**
   * User prefers explicit comparisons (e.g. `if var == False:`, `if var == None:`, `if content == "":`) over `if not var:`.
4. **Local Running Instructions:**
   * **Backend:** `cd backend && python main.py` (Port 8000).
   * **Frontend:** `cd frontend && npm run dev` (Port 5173).

---

## 🗺️ 6. Future Expansion Roadmap

* **Phase 1: NoSQL & JSON Document Engine:** ✅ Completed & Tested.
* **Phase 2: Excel Engine (`.xlsx`):** Multi-sheet virtual table mapping, cross-sheet `JOIN`s, and native Excel formula generator (`=XLOOKUP`, `=SUMIFS`).
* **Phase 3: CSV Engine (`.csv`):** In-memory tabular SQL execution, Python Pandas code snippet toggle, and 1-click CSV export button.
* **Phase 4: Unified Multi-Source Router & Docker:** Auto-intent query router and fullstack `docker-compose.yml`.
* **Milestone 8:** 50-Query Golden Evaluation Benchmark Suite (`benchmark_golden_set.json` & `benchmark_eval.py`).
