"""Run the test set through the agent and report accuracy."""
import time
import pandas as pd

from graph import ask, conn
from testset import CASES


def norm(v):
    if isinstance(v, float):
        v = round(v, 2)
        if v.is_integer():
            return int(v)
    return v


def column_signatures(rows):
    """Each column -> sorted list of normalised values (order-insensitive)."""
    return [sorted(str(norm(v)) for v in col) for col in zip(*rows)]


def results_match(gold_rows, pred_rows):
    """Same row count, and every gold column appears in the prediction.
    Extra columns / different column names / aliases are allowed."""
    if len(gold_rows) != len(pred_rows):
        return False
    if not gold_rows:
        return True
    pred_cols = column_signatures(pred_rows)
    return all(g in pred_cols for g in column_signatures(gold_rows))


def main():
    records = []
    for i, case in enumerate(CASES, 1):
        q = case["q"]
        try:
            res = ask(q)
        except Exception as e:  # e.g. rate limit
            res = {"error": f"EXCEPTION: {e}", "retries": 0, "sql": ""}

        if case.get("refuse"):
            ok = str(res.get("error", "")).startswith("REFUSED")
        elif res.get("error"):
            ok = False
        else:
            gold_rows = conn.execute(case["gold"]).fetchall()
            ok = results_match(gold_rows, res["rows"])

        retries = res.get("retries", 0)
        print(f"{i:>2}. {'PASS' if ok else 'FAIL'} | retries={retries} | {q}")
        if not ok:
            print(f"      SQL: {res.get('sql', '')}")
            if res.get("error"):
                print(f"      ERR: {res['error']}")

        records.append(
            {"q": q, "pass": ok, "retries": retries,
             "sql": res.get("sql", ""), "error": res.get("error")}
        )
        time.sleep(1)  # be gentle with rate limits

    df = pd.DataFrame(records)
    answerable = [r for r, c in zip(records, CASES) if not c.get("refuse")]
    refusals = [r for r, c in zip(records, CASES) if c.get("refuse")]

    print("\n===== RESULTS =====")
    print(f"Overall:     {df['pass'].sum()}/{len(df)}")
    print(f"Answerable:  {sum(r['pass'] for r in answerable)}/{len(answerable)}")
    print(f"Refusals:    {sum(r['pass'] for r in refusals)}/{len(refusals)}")
    print(f"Self-corrected queries: {(df['retries'] > 0).sum()}")
    df.to_csv("eval_results.csv", index=False)
    print("Saved eval_results.csv")


if __name__ == "__main__":
    main()