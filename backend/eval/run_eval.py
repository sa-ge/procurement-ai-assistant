"""Run the evaluation suite against the live agent.

Usage (from backend/):
    python -m eval.run_eval            # all cases
    python -m eval.run_eval top_items  # selected case ids

For each case the ground-truth pipeline is executed directly, the expected values
are extracted, and the agent's answer is checked to contain them. Results are
printed as a table and saved to eval/results.json.
"""
import json
import re
import sys
import time
import uuid
from pathlib import Path

from app.agent.graph import ask
from app.db import get_collection
from eval.cases import CASES

TOLERANCE = 0.01  # 1% — the agent may round money in its answer


def numbers_in(text: str) -> list[float]:
    found = []
    for raw, suffix in re.findall(r"(-?\d[\d,]*\.?\d*)\s*(billion|million|thousand|B|M|K)?\b", text, re.I):
        try:
            value = float(raw.replace(",", ""))
        except ValueError:
            continue
        scale = {"billion": 1e9, "b": 1e9, "million": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}
        found.append(value * scale.get((suffix or "").lower(), 1))
    return found


def contains(answer: str, expected) -> bool:
    if isinstance(expected, (int, float)):
        return any(abs(n - expected) <= abs(expected) * TOLERANCE + 0.5 for n in numbers_in(answer))
    return str(expected).lower() in answer.lower()


def run_case(case: dict) -> dict:
    rows = list(get_collection().aggregate(case["truth"]))
    expected = case["expect"](rows)
    questions = case["question"] if isinstance(case["question"], list) else [case["question"]]
    thread = str(uuid.uuid4())
    started = time.time()
    try:
        for q in questions:
            result = ask(q, thread)
        answer, steps = result["answer"], result["steps"]
        error = None
    except Exception as exc:  # noqa: BLE001
        answer, steps, error = "", [], f"{type(exc).__name__}: {exc}"
    checks = {str(e): contains(answer, e) for e in expected}
    return {
        "id": case["id"], "category": case["category"], "question": questions[-1],
        "expected": [str(e) for e in expected], "passed": bool(checks) and all(checks.values()),
        "checks": checks, "queries": len(steps), "failed_queries": sum(1 for s in steps if s.get("error")),
        "seconds": round(time.time() - started, 1), "answer": answer, "error": error,
        "pipelines": [s.get("pipeline") for s in steps],
    }


def main(ids: list[str]) -> None:
    cases = [c for c in CASES if not ids or c["id"] in ids]
    results = []
    for case in cases:
        r = run_case(case)
        results.append(r)
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"[{mark}] {r['id']:<22} queries={r['queries']} retries={r['failed_queries']} {r['seconds']:>5}s  expected={r['expected']}")
        if not r["passed"]:
            print(f"        answer: {(r['error'] or r['answer'])[:300]!r}")
    passed = sum(r["passed"] for r in results)
    print(f"\nAccuracy: {passed}/{len(results)} ({passed / len(results):.0%})  "
          f"avg latency: {sum(r['seconds'] for r in results) / len(results):.1f}s")
    out = Path(__file__).with_name("results.json")
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"Saved {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
