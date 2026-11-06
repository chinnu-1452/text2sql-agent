"""Step 6: Streamlit UI for the Text-to-SQL agent."""
import pandas as pd
import plotly.express as px
import streamlit as st
 
from graph import ask
from generator import llm
 
st.set_page_config(page_title="Text-to-SQL Analytics Agent", page_icon="📊", layout="wide")
 
EXAMPLES = [
    "Top 5 customers by total spend",
    "Total sales per year",
    "Which genre generates the most revenue?",
    "Top 10 best selling artists",
    "Number of customers per country",
]
 
 
def pick_chart(df: pd.DataFrame):
    """Choose a chart from the result shape. Returns a plotly figure or None."""
    if len(df) < 2 or df.shape[1] < 2:
        return None
 
    is_id = lambda c: c.lower().endswith("id")
    num_cols = [c for c in df.select_dtypes("number").columns if not is_id(c)]
    cat_cols = [c for c in df.columns if c not in num_cols and not is_id(c)]
    if not num_cols or not cat_cols or len(cat_cols) > 2:
        return None
 
    y = num_cols[-1]
    plot_df = df.copy()
    plot_df["label"] = plot_df[cat_cols].astype(str).agg(" ".join, axis=1)
 
    time_like = any(k in cat_cols[0].lower() for k in ("year", "month", "date"))
    if time_like:
        return px.line(plot_df, x="label", y=y, markers=True)
    return px.bar(plot_df, x="label", y=y)
 
 
def summarize(question: str, df: pd.DataFrame) -> str:
    prompt = (
        f"Question: {question}\n\nData (first 20 rows):\n"
        f"{df.head(20).to_string(index=False)}\n\n"
        "Write a 2-3 sentence plain-language answer for a business user. "
        "Use only the numbers shown above. No markdown."
    )
    return llm.invoke(prompt).content
 
 
# ---------------- UI ----------------
st.title("📊 Text-to-SQL Analytics Agent")
st.caption(
    "Ask questions in English about the Chinook music store database. "
    "Read-only, validated SQL, self-correcting (LangGraph + Groq)."
)
 
st.sidebar.header("Try an example")
question = st.chat_input("Ask a question about the data...")
for ex in EXAMPLES:
    if st.sidebar.button(ex):
        question = ex
 
if question:
    st.subheader(f"Q: {question}")
    with st.spinner("Thinking..."):
        result = ask(question)
 
    if result.get("error"):
        if result["error"].startswith("REFUSED"):
            st.warning(result["error"])
        else:
            st.error(f"Could not answer after {result.get('retries', 0)} attempts: {result['error']}")
        if result.get("sql"):
            with st.expander("Last SQL tried"):
                st.code(result["sql"], language="sql")
    else:
        df = pd.DataFrame(result["rows"], columns=result["columns"])
 
        retries = result.get("retries", 0)
        if retries:
            st.info(f"Self-corrected {retries} time(s) before getting a valid query.")
 
        with st.spinner("Writing summary..."):
            st.success(summarize(question, df))
 
        fig = pick_chart(df)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
 
        st.dataframe(df, use_container_width=True)
        with st.expander("Generated SQL"):
            st.code(result["sql"], language="sql")