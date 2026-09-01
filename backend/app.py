import os
import sys
from pathlib import Path

# Add src folder to sys.path so modules are easily discovered
SRC_PATH = Path(__file__).resolve().parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import streamlit as st
from F06_pipeline import TextToSQLPipeline

# ==============================================================================
# 1. Page Configuration & Custom Styling
# ==============================================================================
st.set_page_config(
    page_title="Enterprise Text-to-SQL Assistant",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==============================================================================
# 2. Pipeline Initialization (Cached for High Performance)
# ==============================================================================
@st.cache_resource
def get_pipeline():
    return TextToSQLPipeline()

pipeline = get_pipeline()

# ==============================================================================
# 3. Sidebar: Database Schema & Live Introspection Explorer
# ==============================================================================
with st.sidebar:
    st.title("🗄️ Database Explorer")
    st.caption("Live relational schema introspection on Chinook SQLite")

    try:
        tables = pipeline.db_engine.get_table_names()
        selected_table = st.selectbox("Inspect Table:", tables)

        if selected_table:
            cols = pipeline.db_engine.get_table_schema(selected_table)
            st.markdown(f"**Columns in `{selected_table}` ({len(cols)} cols):**")
            for c in cols:
                pk_badge = " *(PK)*" if c.get("primary_key") else ""
                st.text(f"• {c['name']} [{c['type']}]{pk_badge}")
    except Exception as e:
        st.error(f"Error reading schema: {e}")

    st.markdown("---")
    st.markdown("### 💡 Example Questions")
    st.markdown("Click any sample query to copy:")
    st.code("How many total tracks are in the database?", language="text")
    st.code("Which 3 artists have the most albums?", language="text")
    st.code("List the top 5 customers by total invoice spending.", language="text")
    st.code("DROP TABLE Customer;", language="sql")

# ==============================================================================
# 4. Main Chat Interface & Session State History
# ==============================================================================
st.title("🛡️ Enterprise Text-to-SQL AI Assistant")
st.markdown(
    "Query your enterprise database in natural English with **AST Security Guardrails**, **Self-Correction Recovery**, and **Hallucination Scoring**."
)

# Initialize conversational session history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous conversation messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "data" in msg and msg["data"]:
            st.dataframe(msg["data"], use_container_width=True)

# ==============================================================================
# 5. User Input Handling & Pipeline Execution
# ==============================================================================
user_prompt = st.chat_input("Ask a question about your database (e.g. 'Who are our top 5 customers?')...")

if user_prompt:
    # Append & render user message
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    # Execute Master Pipeline with UI Feedback
    with st.chat_message("assistant"):
        with st.spinner("Analyzing schema, verifying guardrails, and executing query..."):
            result = pipeline.run_pipeline(user_prompt)

        # Telemetry Badges
        col1, col2, col3, col4 = st.columns(4)
        status_color = "green" if result.get("status") == "SUCCESS" else "red"
        col1.metric("Pipeline Status", result.get("status", "UNKNOWN"))
        col2.metric("Confidence Score", f"{result.get('confidence_score', 0) * 100:.0f}%")
        col3.metric("Latency", f"{result.get('latency_ms', 0)} ms")
        col4.metric("Retry Attempts", result.get("attempts", 1))

        # Status Alert Banner
        if result.get("status") == "SUCCESS":
            st.success("Query passed security guardrails and executed cleanly.")
        else:
            st.error(f"Security / Execution Warning: {result.get('summary')}")

        # Inspection Tabs
        tab_summary, tab_data, tab_sql = st.tabs([
            "💬 Plain English Answer",
            "📋 Data Table",
            "💻 Generated SQL Query"
        ])

        with tab_summary:
            st.write(result.get("summary", "No summary available."))

        with tab_data:
            if result.get("data"):
                st.dataframe(result["data"], use_container_width=True)
            else:
                st.info("No data rows returned.")

        with tab_sql:
            st.code(result.get("final_sql", "-- No SQL generated"), language="sql")

        # Save assistant message to session history
        st.session_state.messages.append({
            "role": "assistant",
            "content": result.get("summary", ""),
            "data": result.get("data", [])
        })
