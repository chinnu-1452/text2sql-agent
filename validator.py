"""Step 4: SQL safety validator using sqlglot."""
import sqlglot
from sqlglot import exp
from db import get_connection
 
FORBIDDEN = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop,
    exp.Create, exp.Alter, exp.Command, exp.Merge,
)
 
 
def get_table_names(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {r[0].lower() for r in rows}
 
 
def validate_sql(sql, allowed_tables, max_rows=100):
    """Return (ok, result). result = safe SQL if ok, else error message."""
    sql = sql.strip()
    if not sql:
        return False, "Empty SQL."
 
    try:
        statements = [s for s in sqlglot.parse(sql, dialect="sqlite") if s]
    except sqlglot.errors.ParseError as e:
        return False, f"Syntax error: {e}"
 
    if len(statements) != 1:
        return False, "Exactly one SQL statement is allowed."
 
    tree = statements[0]
 
    if not isinstance(tree, (exp.Select, exp.Union)):
        return False, "Only SELECT queries are allowed."
 
    bad = tree.find(*FORBIDDEN)
    if bad:
        return False, f"Forbidden operation: {type(bad).__name__}"
 
    cte_names = {c.alias.lower() for c in tree.find_all(exp.CTE)}
    used = {t.name.lower() for t in tree.find_all(exp.Table)}
    unknown = used - allowed_tables - cte_names
    if unknown:
        return False, f"Unknown table(s): {', '.join(sorted(unknown))}"
 
    if isinstance(tree, exp.Select) and not tree.args.get("limit"):
        tree = tree.limit(max_rows)
 
    return True, tree.sql(dialect="sqlite")
 
 
if __name__ == "__main__":
    conn = get_connection()
    allowed = get_table_names(conn)
 
    tests = [
        "SELECT * FROM Customer",
        "DROP TABLE Customer",
        "DELETE FROM Invoice WHERE InvoiceId = 1",
        "SELECT * FROM Customer; DROP TABLE Invoice",
        "SELECT * FROM Employees",
        "SELEC * FROM Customer",
        "WITH t AS (SELECT CustomerId FROM Invoice) SELECT * FROM t",
    ]
    for q in tests:
        ok, result = validate_sql(q, allowed)
        print(f"{'PASS' if ok else 'BLOCK'} | {q}\n      -> {result}\n")
 