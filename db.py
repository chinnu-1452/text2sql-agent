"""Step 1 + 2: Chinook DB setup and schema extractor."""
import sqlite3
import urllib.request
from pathlib import Path
 
DB_PATH = Path(__file__).parent / "chinook.db"
URL = (
    "https://raw.githubusercontent.com/lerocha/chinook-database/"
    "master/ChinookDatabase/DataSources/Chinook_Sqlite.sqlite"
)
 
 
def download_db():
    """Download Chinook once."""
    if not DB_PATH.exists():
        print("Downloading Chinook...")
        urllib.request.urlretrieve(URL, DB_PATH)
 
 
def get_connection():
    """Read-only connection, so even a bad query cannot modify data."""
    download_db()
    return sqlite3.connect(
        f"file:{DB_PATH.as_posix()}?mode=ro", uri=True, check_same_thread=False
    )
 
def get_schema(conn, sample_rows=3):
    """Return schema as text: columns, foreign keys, sample rows per table."""
    cur = conn.cursor()
    tables = [
        r[0]
        for r in cur.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    parts = []
    for t in tables:
        cols = cur.execute(f'PRAGMA table_info("{t}")').fetchall()
        col_txt = ", ".join(
            f"{c[1]} ({c[2]}{', PK' if c[5] else ''})" for c in cols
        )
        fks = cur.execute(f'PRAGMA foreign_key_list("{t}")').fetchall()
        fk_txt = "; ".join(f"{f[3]} -> {f[2]}.{f[4]}" for f in fks) or "none"
        rows = cur.execute(f'SELECT * FROM "{t}" LIMIT {sample_rows}').fetchall()
        row_txt = "\n".join(f"  {r}" for r in rows)
        parts.append(
            f"Table: {t}\nColumns: {col_txt}\nForeign keys: {fk_txt}\n"
            f"Sample rows:\n{row_txt}"
        )
    return "\n\n".join(parts)
 
 
if __name__ == "__main__":
    conn = get_connection()
    print(get_schema(conn))
    print("\n--- Manual test query ---")
    q = (
        "SELECT g.Name, COUNT(*) AS tracks FROM Track t "
        "JOIN Genre g ON t.GenreId = g.GenreId "
        "GROUP BY g.Name ORDER BY tracks DESC LIMIT 5"
    )
    for row in conn.execute(q):
        print(row)