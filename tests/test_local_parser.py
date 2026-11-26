"""Local fast path: plain 'item amount' messages are saved with no model call; anything else,
or any item without history, goes to the model."""
import time

import pytest
from helpers import FakeResp, count_rows, insert_expense, query, turn, usage

import analytics as an
import core

CARDS = ["HDFC MoneyBack", "Swiggy HDFC", "SBI Cashback", "Slice UPI"]


@pytest.mark.parametrize("text, pairs", [
    ("chai 15", [("chai", 15)]),
    ("Chai  15", [("chai", 15)]),
    ("metro 40, auto 120", [("metro", 40), ("auto", 120)]),
    ("metro 40,auto 120", [("metro", 40), ("auto", 120)]),
    ("vada pav 30 and chai 15", [("vada pav", 30), ("chai", 15)]),
    ("t-shirt 1,299", [("t-shirt", 1299)]),
    ("laptop 1,00,000", [("laptop", 100000)]),
    ("rent 2k", [("rent", 2000)]),
    ("shoes 2.5k", [("shoes", 2500)]),
])
def test_parser_accepts_plain_item_amount_lists(text, pairs):
    assert core._parse_local(text, CARDS) == pairs


@pytest.mark.parametrize("text", [
    "yesterday chai 15", "chai yesterday 15", "chai 15 yesterday", "chai 15 at 9pm",
    "chai at 9pm 15", "kal chai 15", "aaj chai 20", "chai ke 20",
    "change chai 20", "delete chai 15", "chai 15?", "how much chai 15",
    "chai 15 upi", "upi chai 15", "cash chai 15", "hdfc 500", "swiggy 300", "slice 99",
    "chai ₹15", "chai rs 15", "₹15 chai", "15 chai", "2 samosa 40", "chai 15.5",
    "auto 80 metro 40", "chai 15,", "chai 15, ", "chai 1,2345", "chai",
    "paid chai 15", "spent 15 on chai", "salary 50000", "refund chai 15", "budget food 6000",
    "chai 15 and", "netflix 649 every month", "free coffee 0", "chai 15 lol", "",
])
def test_parser_refuses_anything_else(text):
    assert core._parse_local(text, CARDS) is None


def _no_model(monkeypatch):
    def fail(*a, **k):
        raise AssertionError("the model must not be called")
    monkeypatch.setattr(core, "_generate", fail)


def test_known_items_save_locally_with_history_category(monkeypatch):
    insert_expense("chai", 20, "food")
    insert_expense("chai", 20, "food")
    insert_expense("metro", 30, "transport")
    insert_expense("metro", 30, "bills")  # the most recent category wins
    _no_model(monkeypatch)
    reply = turn("chai 15, Metro 40")
    assert reply.startswith("Saved:\n- chai: ₹15 (food, ")
    assert "- metro: ₹40 (bills, " in reply
    assert query("SELECT item, amount_inr, category, raw_text FROM expenses WHERE id > 4") == [
        ("chai", 15.0, "food", "chai 15, Metro 40"), ("metro", 40.0, "bills", "chai 15, Metro 40")]
    assert query("SELECT purpose, status, total_tokens, attempts FROM llm_calls") == [
        ("local", "ok", 0, 0)]


def test_one_unknown_item_sends_the_whole_message_to_the_model(script):
    insert_expense("chai", 20, "food")
    log = script([("add_expenses", {"expenses": [{"spent_at": "2026-10-03 09:00", "item": "chai",
                                                  "amount_inr": 15, "category": "food"}]})])
    turn("chai 15 and samosa 20")
    assert len(log) == 1 and count_rows() == 2  # model was called; nothing saved locally twice


def test_item_saved_only_once_goes_to_the_model(script):
    insert_expense("petorl", 200, "transport")  # a typo stored once must not be repeated
    log = script([("add_expenses", {"expenses": [{"spent_at": "2026-10-03 09:00",
                                                  "item": "petrol", "amount_inr": 200,
                                                  "category": "transport"}]})])
    turn("petorl 200")
    assert len(log) == 1
    assert query("SELECT item FROM expenses ORDER BY id") == [("petorl",), ("petrol",)]


def test_refund_history_does_not_count(script):
    insert_expense("refund: chai", -20, "food")
    log = script([("reply_to_user", {"message": "ok"})])
    turn("refund: chai 20")
    assert len(log) == 1


def test_answer_to_a_model_question_goes_to_the_model(script):
    insert_expense("chai", 20, "food")
    log = script([("reply_to_user", {"message": "ok"})])
    history = [{"role": "user", "content": "chai"},
               {"role": "assistant", "content": "How much was the chai?"}]
    core.chat_turn(history, "chai 15", "u-question")
    assert len(log) == 1 and count_rows() == 1


def test_amount_over_the_limit_falls_back_to_the_model(script):
    insert_expense("laptop", 50000, "shopping")
    log = script([("reply_to_user", {"message": "That amount looks too high."})])
    assert turn("laptop 20,00,000") == "That amount looks too high."
    assert len(log) == 1 and count_rows() == 1


def test_guardrails_still_run_first(monkeypatch):
    insert_expense("chai", 20, "food")
    insert_expense("chai", 20, "food")
    _no_model(monkeypatch)
    assert core.chat_turn([], "chai 15 " + "x" * 400, "u-long").startswith("That message is too")
    for _ in range(core.RATE_LIMIT_MESSAGES):
        core.chat_turn([], "chai 15", "u-rate")
    assert core.chat_turn([], "chai 15", "u-rate").startswith("You're sending messages too fast")


def test_local_saves_stay_out_of_call_metrics(monkeypatch):
    core._log_llm_call("chat", "ok", time.perf_counter(), 1, resp=FakeResp([], usage()))
    insert_expense("chai", 20, "food")
    insert_expense("chai", 20, "food")
    _no_model(monkeypatch)
    turn("chai 15")
    summary = an.llm_summary(an.load_llm_calls())
    assert summary["calls"] == 1 and summary["success_rate"] == 100.0
    assert an.local_saves() == 1
    assert an.llm_daily(an.load_llm_calls())["Calls"].sum() == 1


def offline_eval(cases):
    """[(text, handled, passed)] for each eval case run through the local parser alone.
    History can't be known offline. Stand-in: an item is "in history" only if it is an item
    the model is labelled to store (it contains a label's item_contains), with the label's
    category. So a typo like "petorl" counts as unknown, as it would be in real history."""
    import eval as ev
    from eval_cases import NOW

    out = []
    for case in cases:
        pairs, preds = core._parse_local(case["text"], CARDS), []
        for item, amount in pairs or []:
            label = next((e for e in case["expected"]
                          if any(k in item for k in e["item_contains"])), None)
            if label is None:
                break  # no history for this item -> the whole message goes to the model
            preds.append({"item": item, "amount_inr": amount, "category": label.get("category"),
                          "spent_at": NOW.strftime("%Y-%m-%d %H:%M")})
        else:
            if pairs:
                calls = [("add_expenses", {"expenses": preds})]
                out.append((case["text"], True, ev.score_case(case, preds, calls)["passed"]))
                continue
        out.append((case["text"], False, None))
    return out


def test_eval_cases_never_disagree_with_their_labels():
    from eval_cases import CASES

    handled = [(t, ok) for t, h, ok in offline_eval(CASES) if h]
    assert handled  # the parser does handle the plain cases
    assert [t for t, ok in handled if not ok] == []


def test_replay_script_reports_handled_and_mismatches():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "replay", Path(__file__).resolve().parent.parent / "scripts" / "replay_local_parser.py")
    replay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replay)

    def say(text, *rows, when="2026-11-01 09:00"):
        core.add_expenses([{"spent_at": when, "item": i, "amount_inr": a, "category": c}
                           for i, a, c in rows], text)

    say("chai 20", ("chai", 20, "food"))                                 # no history yet
    say("metro 40 and chai 15", ("metro", 40, "transport"), ("chai", 15, "food"))  # metro new
    say("chai 10", ("chai", 10, "food"), when="2026-11-02 09:00")        # handled, matches
    say("metro 45", ("metro", 45, "transport"), when="2026-11-02 09:30")  # metro seen once
    say("metro 50", ("metro", 50, "bills"), when="2026-11-02 10:00")     # handled, mismatch
    say("auto: recurring", ("netflix", 649, "entertainment"))            # not a message
    r = replay.replay(core.DB_PATH)
    assert (r["messages"], r["handled"]) == (5, 2)
    assert [m["text"] for m in r["mismatches"]] == ["metro 50"]
    assert count_rows() == 7  # read-only: nothing written
