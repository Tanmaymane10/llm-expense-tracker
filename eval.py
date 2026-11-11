
"""
Run the parser against eval_cases.py and report accuracy.

    uv run python eval.py
    uv run python eval.py --case "cab at 10pm 500"
    uv run python eval.py --case "cab at 10pm 500" --case "electricity bill is 2000 but I paid 500 for groceries"

Writes eval_results.json so you can track accuracy across prompt/model changes.
"""

import argparse
import json
from datetime import timedelta

from core import MODEL, extract_expenses
from eval_cases import CASES, NOW


def score_case(case: dict, preds: list) -> dict:
    expected = case["expected"]
    used, matched = set(), []

    for exp in expected:
        for i, p in enumerate(preds):
            if i in used:
                continue

            item = str(p.get("item", "")).lower()

            if (
                abs(float(p.get("amount_inr", -1)) - exp["amount"]) < 0.01
                and any(k in item for k in exp["item_contains"])
            ):
                used.add(i)
                matched.append((exp, p))
                break

    cat_checks = [
        p.get("category") == e["category"]
        for e, p in matched if "category" in e
    ]

    date_checks = []

    for e, p in matched:
        want = (NOW + timedelta(days=e.get("day_offset", 0))).strftime("%Y-%m-%d")
        ok = str(p.get("spent_at", ""))[:10] == want

        if "hour" in e:
            try:
                ok = ok and int(str(p["spent_at"])[11:13]) == e["hour"]
            except (ValueError, KeyError):
                ok = False

        date_checks.append(ok)

    passed = (
        len(matched) == len(expected) == len(preds)
        and all(cat_checks)
        and all(date_checks)
    )

    return {
        "passed": passed,
        "n_expected": len(expected),
        "n_pred": len(preds),
        "n_matched": len(matched),
        "cat_checks": cat_checks,
        "date_checks": date_checks,
    }


def pct(a, b):
    return f"{100 * a / b:.1f}%" if b else "n/a"


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate the expense parser against selected or all test cases."
    )

    parser.add_argument(
        "--case",
        action="append",
        dest="selected_cases",
        help="Run only the case matching this exact input. Can be repeated.",
    )

    args = parser.parse_args()

    if args.selected_cases:
        case_map = {case["text"]: case for case in CASES}
        missing = [text for text in args.selected_cases if text not in case_map]

        if missing:
            parser.error(f"Case(s) not found in eval_cases.py: {missing}")

        selected = [case_map[text] for text in args.selected_cases]
    else:
        selected = CASES

    results = []

    for case in selected:
        preds = extract_expenses(case["text"], NOW)
        s = score_case(case, preds)

        results.append({
            "text": case["text"],
            "expected": case["expected"],
            "predicted": preds,
            **s,
        })

        print(("PASS  " if s["passed"] else "FAIL  ") + case["text"])

    n_exp = sum(r["n_expected"] for r in results)
    n_pred = sum(r["n_pred"] for r in results)
    n_match = sum(r["n_matched"] for r in results)

    cat = [c for r in results for c in r["cat_checks"]]
    dat = [d for r in results for d in r["date_checks"]]

    passed = sum(r["passed"] for r in results)

    print(f"\nModel: {MODEL}")
    print(f"Cases fully correct : {passed}/{len(results)} ({pct(passed, len(results))})")
    print(f"Item+amount recall  : {pct(n_match, n_exp)}")
    print(f"Item+amount precision: {pct(n_match, n_pred)}")
    print(f"Category accuracy   : {pct(sum(cat), len(cat))}")
    print(f"Date/time accuracy  : {pct(sum(dat), len(dat))}")

    print("\nFailures:")

    failures = [r for r in results if not r["passed"]]

    if not failures:
        print("None")

    for r in failures:
        print(
            f"- {r['text']}\n"
            f"    expected : {r['expected']}\n"
            f"    predicted: {r['predicted']}"
        )

    with open("eval_results.json", "w") as f:
        json.dump(
            {
                "model": MODEL,
                "cases_passed": passed,
                "total": len(results),
                "results": results,
            },
            f,
            indent=2,
            default=str,
        )


if __name__ == "__main__":
    main()
