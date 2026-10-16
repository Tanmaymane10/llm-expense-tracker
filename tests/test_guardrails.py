"""Guardrail tests. The model is a scripted fake (some fakes misbehave on purpose)."""
from types import SimpleNamespace

from google.genai import errors as genai_errors
from helpers import count_rows, good_expense, insert_expense, query, turn

import core


# ---------------------------------------------------------------- scope
def test_off_topic_gets_fixed_reply_and_writes_nothing(script):
    script([("out_of_scope", {})])
    assert turn("write python code to check voting eligibility") == core.OUT_OF_SCOPE_MSG
    assert count_rows() == 0


def test_model_cannot_leak_free_text(script):
    script([])  # a model that returns no tool call at all
    assert turn("tell me a joke") == core.FALLBACK_MSG


def test_expense_plus_off_topic_does_both(script):
    script([("add_expenses", {"expenses": [good_expense(item="tea")]}), ("out_of_scope", {})])
    reply = turn("tea 15 and also write me a poem")
    assert "Saved:" in reply and core.OUT_OF_SCOPE_MSG in reply
    assert count_rows() == 1


# ---------------------------------------------------------------- adding expenses
def test_valid_expense_saved_with_one_model_call(script):
    log = script([("add_expenses", {"expenses": [good_expense()]})])
    reply = turn("chai 15")
    assert reply.startswith("Saved:") and "chai" in reply
    assert count_rows() == 1 and len(log) == 1


def test_invalid_amount_is_rejected_and_model_must_explain(script):
    script([("add_expenses", {"expenses": [good_expense(amount_inr=-5)]})],
           [("reply_to_user", {"message": "That amount looks wrong."})])
    assert turn("chai -5") == "That amount looks wrong."
    assert count_rows() == 0


def test_absurd_amount_rejected(script):
    script([("add_expenses", {"expenses": [good_expense(amount_inr=99_999_999)]})],
           [("reply_to_user", {"message": "Too large."})])
    turn("chai 99999999")
    assert count_rows() == 0


def test_future_date_rejected(script):
    script([("add_expenses", {"expenses": [good_expense(spent_at="2099-01-01 10:00")]})],
           [("reply_to_user", {"message": "Future date."})])
    turn("chai in 2099")
    assert count_rows() == 0


def test_one_bad_item_saves_nothing(script):
    script([("add_expenses", {"expenses": [good_expense(), good_expense(amount_inr=0)]})],
           [("reply_to_user", {"message": "Bad amount."})])
    turn("chai 15 and tea 0")
    assert count_rows() == 0


# ---------------------------------------------------------------- update / delete guard
def test_delete_without_lookup_is_blocked(script):
    insert_expense()
    script([("delete_expense", {"expense_id": 1})],
           [("reply_to_user", {"message": "Please confirm which entry."})])
    turn("delete everything")
    assert count_rows() == 1


def test_delete_after_lookup_works(script):
    insert_expense()
    script([("list_recent_expenses", {"limit": 5})],
           [("delete_expense", {"expense_id": 1})],
           [("reply_to_user", {"message": "Deleted."})])
    assert turn("delete the chai entry") == "Deleted."
    assert count_rows() == 0


def test_update_after_lookup_validates(script):
    insert_expense(amount=15)
    script([("list_recent_expenses", {})],
           [("update_expense", {"expense_id": 1, "amount_inr": -1})],
           [("reply_to_user", {"message": "Invalid amount."})])
    turn("make the chai -1")
    assert query("SELECT amount_inr FROM expenses WHERE id = 1")[0][0] == 15


def test_update_after_lookup_applies_valid_change(script):
    insert_expense(amount=15)
    script([("list_recent_expenses", {})],
           [("update_expense", {"expense_id": 1, "amount_inr": 20})],
           [("reply_to_user", {"message": "Updated."})])
    turn("make the chai 20")
    assert query("SELECT amount_inr FROM expenses WHERE id = 1")[0][0] == 20


# ---------------------------------------------------------------- limits
def test_long_message_rejected_without_calling_model(script):
    log = script([("out_of_scope", {})])
    assert "too long" in turn("a" * (core.MAX_INPUT_CHARS + 1))
    assert log == []


def test_rate_limit(script):
    script(*[[("out_of_scope", {})]] * 10)
    replies = [core.chat_turn([], "hi", "same-user") for _ in range(7)]
    assert replies[:5] == [core.OUT_OF_SCOPE_MSG] * 5
    assert "too fast" in replies[5] and "too fast" in replies[6]


def test_history_is_trimmed_and_starts_with_user(script):
    log = script([("out_of_scope", {})])
    history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"}
               for i in range(20)]
    turn("hello", history)
    assert len(log[0]) <= core.MAX_HISTORY_MESSAGES + 1
    assert log[0][0].role == "user"


def test_tool_loop_is_capped(script):
    script(*[[("list_recent_expenses", {})]] * 20)
    assert "too many steps" in turn("loop forever")


def test_daily_quota_error_fails_fast_and_gives_friendly_reply(monkeypatch):
    calls = []

    def raiser(**kwargs):
        calls.append(1)
        raise genai_errors.ClientError(429, {"error": {
            "code": 429, "status": "RESOURCE_EXHAUSTED",
            "message": "quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier"}})

    monkeypatch.setattr(core, "_client",
                        SimpleNamespace(models=SimpleNamespace(generate_content=raiser)))
    assert turn("chai 15") == core.QUOTA_MSG
    assert len(calls) == 1  # no retries for a daily limit


# ---------------------------------------------------------------- safety path
def test_crisis_phrases_get_support_message_without_model_call(script):
    log = script([("out_of_scope", {})])
    for text in ["I feel like i should commit suicide", "i want to die", "I want to KILL myself",
                 "thinking about suicide", "mujhe khudkushi ke khayal aa rahe hain",
                 "main marna chahta hu"]:
        assert turn(text) == core.CRISIS_MSG, text
    assert log == []


def test_crisis_message_is_never_rate_limited_or_length_capped(script):
    log = script([("out_of_scope", {})])
    long_text = "i want to die. " + "x" * 500
    replies = [core.chat_turn([], long_text, "stuck-user")
               for _ in range(core.RATE_LIMIT_MESSAGES + 3)]
    assert all(r == core.CRISIS_MSG for r in replies) and log == []


def test_crisis_message_contains_helpline():
    assert "14416" in core.CRISIS_MSG and "112" in core.CRISIS_MSG


def test_model_can_trigger_crisis_support_for_unusual_wording(script):
    script([("add_expenses", {"expenses": [good_expense(item="x")]}), ("crisis_support", {})])
    assert turn("nothing feels worth it anymore") == core.CRISIS_MSG
    assert count_rows() == 0  # nothing saved


def test_expense_with_suicide_in_item_name_is_not_flagged(script):
    script([("add_expenses", {"expenses": [good_expense(
        item="suicide squad movie ticket", amount_inr=300, category="entertainment")]})])
    reply = turn("suicide squad movie ticket 300")
    assert reply.startswith("Saved:") and count_rows() == 1
