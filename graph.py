"""Step 5: LangGraph self-correcting Text-to-SQL agent.
 
generate -> validate -> execute -> END
   ^           |           |
   +-- error --+-----------+   (max MAX_RETRIES)
"""
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, START, END
 
from db import get_connection, get_schema
from generator import generate_sql
from validator import validate_sql, get_table_names
 
MAX_RETRIES = 3
 
 
class State(TypedDict, total=False):
    question: str
    sql: str
    error: Optional[str]
    columns: list
    rows: list
    retries: int
 
 
conn = get_connection()
SCHEMA = get_schema(conn, sample_rows=2)
ALLOWED = get_table_names(conn)
 
 
# ---------- Nodes ----------
def generate_node(state: State):
    sql = generate_sql(
        state["question"],
        SCHEMA,
        previous_sql=state.get("sql"),
        error=state.get("error"),
    )
    return {"sql": sql}


def validate_node(state: State):
    if state["sql"].strip().upper().startswith("CANNOT_ANSWER"):
        return {
            "error": "REFUSED: I can only answer read-only questions this database can answer.",
            "retries": MAX_RETRIES,
        }

    ok, result = validate_sql(state["sql"], ALLOWED)
    if ok:
        return {"sql": result, "error": None}
    return {"error": result, "retries": state.get("retries", 0) + 1}
 
def validate_node(state: State):
    if state["sql"].strip().upper().startswith("CANNOT_ANSWER"):
        return {
            "error": "REFUSED: I can only answer read-only questions this database can answer.",
            "retries": MAX_RETRIES,
        }

    ok, result = validate_sql(state["sql"], ALLOWED)
    if ok:
        return {"sql": result, "error": None}
    return {"error": result, "retries": state.get("retries", 0) + 1}
 
def execute_node(state: State):
    try:
        cur = conn.execute(state["sql"])
        columns = [d[0] for d in cur.description]
        rows = cur.fetchall()
        return {"columns": columns, "rows": rows, "error": None}
    except Exception as e:
        return {"error": str(e), "retries": state.get("retries", 0) + 1}
 
 
# ---------- Conditional edges ----------
def after_validate(state: State):
    if state.get("error"):
        return "stop" if state.get("retries", 0) >= MAX_RETRIES else "retry"
    return "execute"
 
 
def after_execute(state: State):
    if state.get("error"):
        return "stop" if state.get("retries", 0) >= MAX_RETRIES else "retry"
    return "done"
 
 
# ---------- Build graph ----------
builder = StateGraph(State)
builder.add_node("generate", generate_node)
builder.add_node("validate", validate_node)
builder.add_node("execute", execute_node)
 
builder.add_edge(START, "generate")
builder.add_edge("generate", "validate")
builder.add_conditional_edges(
    "validate",
    after_validate,
    {"retry": "generate", "execute": "execute", "stop": END},
)
builder.add_conditional_edges(
    "execute",
    after_execute,
    {"retry": "generate", "done": END, "stop": END},
)
app = builder.compile()
 
 
def ask(question: str, verbose=False):
    """Run the agent and return the final state."""
    init = {"question": question, "retries": 0, "error": None}
    if not verbose:
        return app.invoke(init)
 
    final = dict(init)
    for step in app.stream(init, stream_mode="updates"):
        for node, update in step.items():
            final.update(update)
            print(f"  [{node}]", end=" ")
            if update.get("error"):
                print(f"ERROR: {update['error']}")
            elif node == "execute":
                print(f"{len(update['rows'])} rows")
            else:
                print((update.get("sql") or "").replace("\n", " "))
    return final
 
 
if __name__ == "__main__":
    questions = [
        "Top 5 customers by total spend",
        "List all rows from the Employees table",  # likely triggers a retry
        "Which genre generates the most revenue?",
        "Delete all customers from Brazil",  # must NOT run
    ]
    for q in questions:
        print(f"\nQ: {q}")
        result = ask(q, verbose=True)
        if result.get("error"):
            print(f"  FAILED: {result['error']}")
        else:
            print("  Columns:", result["columns"])
            for row in result["rows"][:5]:
                print("  ", row)