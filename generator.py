"""Step 3: Natural language question -> SQL using Groq."""
import re
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from db import get_connection, get_schema
 
load_dotenv()
 
llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0)
 
SYSTEM_PROMPT = """You are an expert SQLite data analyst.
Given the database schema, write ONE SQLite SELECT query that answers the user's question.
 
Rules:
- Return ONLY the SQL. No explanation, no markdown.
- Use only tables and columns that exist in the schema.
- SELECT only. Never modify data.
- Use explicit JOINs based on the foreign keys shown.
- Add LIMIT 100 unless the question asks for fewer rows.
- If the question asks to modify data or cannot be answered from the schema, return exactly: CANNOT_ANSWER
 
Schema:
{schema}
"""
 
 
def clean_sql(text):
    """Strip markdown fences if the model adds them."""
    text = re.sub(r"```(?:sql)?", "", text).strip()
    return text
 
 
def generate_sql(question, schema, previous_sql=None, error=None):
    """Generate SQL. If previous_sql + error are given, ask the model to fix it
    (used later in the LangGraph retry loop)."""
    user_msg = question
    if error:
        user_msg += (
            f"\n\nYour previous SQL:\n{previous_sql}\n"
            f"It failed with this error:\n{error}\nFix it."
        )
    messages = [
        ("system", SYSTEM_PROMPT.format(schema=schema)),
        ("human", user_msg),
    ]
    return clean_sql(llm.invoke(messages).content)
 
 
if __name__ == "__main__":
    conn = get_connection()
    schema = get_schema(conn, sample_rows=2)
 
    questions = [
        "Top 5 customers by total spend",
        "Which country has the most customers?",
        "Total sales per year",
    ]
    for q in questions:
        print(f"\nQ: {q}")
        sql = generate_sql(q, schema)
        print(f"SQL: {sql}")
        try:
            for row in conn.execute(sql).fetchmany(5):
                print("  ", row)
        except Exception as e:
            print("  ERROR:", e)
 