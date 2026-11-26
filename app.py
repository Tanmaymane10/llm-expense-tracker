"""Streamlit dashboard.  Run with:  streamlit run app.py"""
import time
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta

import altair as alt
import pandas as pd
import streamlit as st

import analytics as an
import core
import ui
from auth import require_pin
from core import (
    CATEGORIES,
    FREQUENCIES,
    INCOME_SOURCES,
    MAX_AMOUNT_INR,
    MAX_INPUT_CHARS,
    add_income,
    budget_status,
    card_status,
    chat_turn,
    delete_income,
    due_line,
    get_conn,
    init_db,
    inr,
    list_cards,
    manage_subscription,
    post_due_recurring,
    register_card,
    savings,
    set_budget,
    set_paid_through,
    subscription_status,
)

THEME_CSS = """
<style>
/* Tokens: docs/design/DESIGN-SPEC.md. Accent is the only accent. */
:root {
  --bg: #0B0E13;
  --surface: #151A21;
  --surface-2: #1C222B;
  --inset: #0F1318;
  --border: #232A33;
  --border-2: #2A323D;
  --text: #EEF2F6;
  --muted: #8C97A6;
  --accent: #C8F25A;
  --on-accent: #0B0E13;
  --warn: #F5B84B;
  --warn-ink: #F7C873;
  --danger: #FF7A7A;
  --danger-ink: #FF9A9A;
  --credit: #9BE88A;
}
.stApp { background: var(--bg); color: var(--text); }
[data-testid="stHeader"] { background: transparent; }
/* one centered column, also on desktop; room at the bottom for the fixed nav */
[data-testid="stMainBlockContainer"] {
  max-width: 560px;
  padding: 22px 20px 132px;
}
[data-testid="stMetricValue"], .num { font-variant-numeric: tabular-nums; }
h1 { font-size: 26px; font-weight: 700; letter-spacing: 0; }
h2, h3 { font-size: 17px !important; font-weight: 600 !important; }
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p {
  color: var(--muted) !important;
}
a { color: var(--accent); }

/* cards */
[data-testid="stForm"], [data-testid="stChatMessage"], [data-testid="stMetric"],
[data-testid="stExpander"] details, [data-testid="stDataFrame"],
[data-testid="stVegaLiteChart"], [data-testid="stArrowVegaLiteChart"] {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 18px;
}
[data-testid="stForm"], [data-testid="stChatMessage"] { padding: 14px 16px; }
[data-testid="stMetric"] {
  padding: 12px 14px;
  border-radius: 14px;
  background: var(--surface-2);
  border: 0;
}
[data-testid="stMetricLabel"] p { color: var(--muted); font-size: 12px; }
[data-testid="stMetricValue"] { font-size: 22px; font-weight: 700; }
[data-testid="stDataFrame"] { padding: 4px; overflow: hidden; }
[data-testid="stVegaLiteChart"],
[data-testid="stArrowVegaLiteChart"] {
  padding: 14px 12px 6px;
  overflow: hidden;
}

/* buttons: secondary = surface pill, primary = lime */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
  min-height: 44px;
  border-radius: 999px;
  border: 1px solid var(--border-2);
  background: var(--surface-2);
  color: var(--text);
  font-weight: 600;
}
.stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {
  border-color: var(--accent);
  color: var(--text);
}
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {
  background: var(--accent) !important;
  border-color: var(--accent) !important;
  color: var(--on-accent) !important;
}
[data-testid="stBaseButton-primary"] *,
[data-testid="stBaseButton-primaryFormSubmit"] * {
  color: inherit !important;
}
button:focus-visible { outline: 2px solid var(--accent) !important; outline-offset: 2px; }

/* inputs: wells */
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"],
[data-testid="stChatInput"] > div {
  background: var(--inset) !important;
  border-color: var(--border-2) !important;
  border-radius: 14px !important;
}
hr { border-color: var(--border); }

/* bottom nav: fixed bar. Fallback: delete this rule and the bar is a normal row. */
.st-key-bottomnav {
  position: fixed;
  left: 50%;
  bottom: 16px;
  transform: translateX(-50%);
  width: min(536px, calc(100% - 24px));
  height: 72px;
  z-index: 999990;
  background: rgba(21, 26, 33, 0.94);
  border: 1px solid #262D37;
  border-radius: 24px;
  padding: 0 4px;
  flex-wrap: nowrap !important;
}
.st-key-bottomnav button {
  flex-direction: column;
  gap: 3px;
  min-width: 52px;
  min-height: 56px;
  padding: 4px 6px !important;
  border: 0 !important;
  background: transparent !important;
  color: var(--muted) !important;
  box-shadow: none !important;
}
.st-key-bottomnav button span[data-has-shortcut] {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
}
.st-key-bottomnav button p { font-size: 11px !important; font-weight: 500; margin: 0; }
.st-key-bottomnav button span[data-testid="stIconMaterial"] { font-size: 22px; }
.st-key-bottomnav [data-testid="stBaseButton-primary"] { color: var(--accent) !important; }
.st-key-nav_add button {
  width: 56px; height: 56px; min-height: 56px; border-radius: 50% !important;
  margin-top: -26px;
  background: var(--accent) !important;
  color: var(--on-accent) !important;
  box-shadow: 0 8px 24px rgba(200, 242, 90, 0.28) !important;
}
/* Home header: lock button as a 44px circle */
.st-key-lock button {
  width: 44px;
  height: 44px;
  min-height: 44px;
  padding: 0 !important;
  border-radius: 50% !important;
  border-color: #262D37 !important;
  background: var(--surface) !important;
}
[class*="st-key-sec_"] { justify-content: space-between; }
[class*="st-key-sec_"] h3 { padding: 0; margin: 0; }
[class*="st-key-sec_"] button { color: var(--accent) !important; min-height: 44px; }
/* the label stays for screen readers only */
.st-key-lock button p,
.st-key-nav_add button p {
  position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0);
}
.st-key-nav_add span[data-testid="stIconMaterial"] { font-size: 26px; }
/* on phones, the keyboard owns the bottom of the screen while typing */
@media (pointer: coarse) {
  body:has(textarea:focus, input:focus) .st-key-bottomnav { display: none; }
}
</style>
"""


# ---- chart helpers: transparent background, no grid clutter, the THEME_CSS tokens
ACCENT, ACCENT_SOFT = "#C8F25A", "rgba(200,242,90,0.45)"  # = --accent in THEME_CSS
MUTED, GRID = "#8C97A6", "rgba(255,255,255,0.05)"
WARN, DANGER = "#F5B84B", "#FF7A7A"


def _style(chart):
    return (chart.configure(background="transparent")
            .configure_view(stroke=None, fill="transparent")
            .configure_axis(domain=False, ticks=False, gridColor=GRID, labelColor=MUTED,
                            titleColor=MUTED, labelFontSize=12, labelPadding=6)
            .configure_legend(labelColor=MUTED, titleColor=MUTED, orient="top",
                              symbolType="stroke", title=None, labelFontSize=12))


def glass_line_chart(df: pd.DataFrame, date_format: str = "%d %b"):
    """df: datetime index, one column per series. The first series gets a soft area under it."""
    long = (df.rename_axis("date").reset_index()
            .melt("date", var_name="series", value_name="Rs"))
    names = list(df.columns)
    colors = [ACCENT, ACCENT_SOFT, MUTED][:len(names)]
    color = alt.Color("series:N", scale=alt.Scale(domain=names, range=colors), title=None)
    x = alt.X("date:T", title=None, axis=alt.Axis(format=date_format, grid=False, tickCount=7),
              scale=alt.Scale(nice=False))
    low = min(0.0, float(long["Rs"].min()))  # savings can go negative
    y = alt.Y("Rs:Q", title=None, scale=alt.Scale(domainMin=low, nice=True),
              axis=alt.Axis(format="~s"))
    lines = alt.Chart(long).encode(x=x, y=y, color=color).mark_line(
        strokeWidth=2.5, interpolate="monotone")
    if len(names) == 1:  # a fill under one of several lines reads as that series' band
        lines = alt.Chart(long).mark_area(opacity=0.15, interpolate="monotone",
                                          color=colors[0]).encode(x=x, y=y) + lines
    # right padding keeps the last x label from being cut off
    return _style(lines.properties(height=280, padding={"left": 5, "top": 5, "bottom": 5,
                                                        "right": 28}))


def glass_bar_chart(df: pd.DataFrame, color: str = ACCENT):
    """df: one value column, index = labels (text or dates). Keeps the row order."""
    col = df.columns[0]
    labels = df.index
    if pd.api.types.is_datetime64_any_dtype(labels):
        labels = labels.strftime("%d %b")
    labels = [str(lbl).split(" ", 1)[1] if str(lbl)[:1].isdigit() and " " in str(lbl)
              and str(lbl).split(" ", 1)[0].isdigit() else str(lbl) for lbl in labels]
    data = pd.DataFrame({"label": labels, "value": df[col].to_numpy()})
    chart = (alt.Chart(data)
             .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6, color=color, size=22)
             .encode(x=alt.X("label:N", sort=None, title=None,
                             axis=alt.Axis(labelAngle=0, grid=False)),
                     y=alt.Y("value:Q", title=None, axis=alt.Axis(format="~s")),
                     tooltip=["label", alt.Tooltip("value:Q", format=",.0f", title=col)])
             .properties(height=240))
    return _style(chart)


def budget_chart(df: pd.DataFrame):
    """df from an.budget_progress(): % of each budget used, coloured by state, line at 100%."""
    pairs = zip(df["spent"], df["budget"], strict=True)
    data = df.assign(label=df["category"].str.capitalize(),
                     text=[f"{inr(s)} / {inr(b)}" for s, b in pairs])
    y = alt.Y("label:N", sort=None, title=None, axis=alt.Axis(grid=False))
    x = alt.X("pct:Q", title=None, axis=alt.Axis(format=".0f", labelExpr="datum.label + '%'",
                                           tickCount=6, labelFlush=True),
              scale=alt.Scale(domain=[0, max(100, float(data["pct"].max()) * 1.15)], nice=False))
    bars = alt.Chart(data).mark_bar(cornerRadiusEnd=6, size=18).encode(
        x=x, y=y,
        color=alt.Color("state:N", legend=None, scale=alt.Scale(
            domain=["ok", "warn", "over"], range=[ACCENT, WARN, DANGER])),
        tooltip=["label", alt.Tooltip("spent:Q", format=",.0f", title="Spent (₹)"),
                 alt.Tooltip("budget:Q", format=",.0f", title="Budget (₹)"),
                 alt.Tooltip("pct:Q", format=".0f", title="% used")])
    text = bars.mark_text(align="left", dx=6, color=MUTED).encode(text="text:N")
    limit = alt.Chart(pd.DataFrame({"pct": [100]})).mark_rule(
        color=MUTED, strokeDash=[4, 4]).encode(x="pct:Q")
    # right padding leaves room for the "₹spent / ₹budget" label past the longest bar
    return _style((bars + text + limit).properties(
        height=40 * len(data) + 20, padding={"left": 5, "top": 5, "bottom": 5, "right": 110}))


# ---- cached reads: heavy reads are cached for 60 s, so writes from Telegram or the recurring
# job show up within that. The DB path is part of the key, so each test DB gets its own
# entries. Every UI write clears the cache.
def _recent_rows() -> pd.DataFrame:
    with get_conn() as conn:
        df = pd.read_sql_query(
            "SELECT e.id, e.spent_at, e.item, e.amount_inr, e.category, e.payment_method, "
            "c.card_name, e.recurring_id IS NOT NULL AS auto, e.counts_d2d FROM expenses e "
            "LEFT JOIN credit_cards c ON c.id = e.card_id ORDER BY e.id DESC LIMIT 50", conn)
    df["payment"] = [core.payment_label(m, c) for m, c in
                     zip(df.pop("payment_method"), df.pop("card_name"), strict=True)]
    df["spent_at"] = pd.to_datetime(df["spent_at"], errors="coerce")
    df["auto"] = df["auto"].astype(bool)
    df["counts_d2d"] = df["counts_d2d"].map({1: "yes", 0: "no"}).fillna("default")
    return df[["id", "spent_at", "item", "amount_inr", "category", "payment", "counts_d2d",
               "auto"]]


_READS = {
    "expenses": an.load_expenses, "income": an.load_income, "llm_calls": an.load_llm_calls,
    "budget_progress": an.budget_progress, "budget_status": budget_status,
    "card_status": card_status, "subscription_status": subscription_status,
    "savings": savings, "list_cards": list_cards, "recent": _recent_rows,
    "local_saves": an.local_saves, "quick_items": core.quick_items,
    "payment_options": core.payment_options, "month_figures": core.month_figures,
}


@st.cache_data(ttl=60, show_spinner=False)
def _cached(name: str, db_path: str, *args):
    return _READS[name](*args)


def read(name: str, *args):
    return _cached(name, core.DB_PATH, *args)


def _money(df: pd.DataFrame, *cols):
    """Show `cols` as ₹ text; the data stays numeric underneath, so sorting still works."""
    return df.style.format(inr, subset=[c for c in cols if c in df.columns], na_rep="")


def _after_write(msg: str):
    """Toast, drop cached reads so the redraw shows the change, then rerun."""
    st.toast(msg)
    st.cache_data.clear()
    st.rerun()


def render_subscriptions():
    st.subheader("Subscriptions")
    st.caption("Each payment is logged automatically on its due date. You can also say "
               "\"netflix 649 every month on the 5th\" in Chat.")
    today = date.today()
    subs = read("subscription_status", today)
    if subs:
        # a display string: a date column filled with "" for paused rules breaks Arrow
        rows = [{**r, "next_due": f"{r['next_due'].day} {r['next_due']:%b %Y}"
                 if r["next_due"] else ""} for r in subs]
        st.dataframe(
            _money(pd.DataFrame(rows)[["item", "amount_inr", "schedule", "next_due", "monthly",
                                       "card_name", "status"]].fillna(""),
                   "amount_inr", "monthly"),
            hide_index=True, width="stretch",
            column_config={
                "item": "Item", "schedule": "Renews", "next_due": "Next due",
                "card_name": "Card", "status": "Status",
                "amount_inr": "Amount (₹)", "monthly": "Per month (₹)",
            })
    names = [r["item"] for r in subs]
    pick = st.selectbox("Add or update", ["New subscription"] + names)
    cur = next((r for r in subs if r["item"] == pick), None)
    with st.form("sub_form"):
        c1, c2, c3 = st.columns(3)
        item = c1.text_input("Item", value=pick if cur else "", disabled=bool(cur), max_chars=80)
        amount = c2.number_input("Amount (₹)", 0.0, float(MAX_AMOUNT_INR), step=100.0,
                                 value=float(cur["amount_inr"]) if cur else 0.0, format="%.0f")
        category = c3.selectbox("Category", CATEGORIES, index=CATEGORIES.index(
            cur["category"] if cur else "entertainment"))
        c1, c2, c3, c4 = st.columns(4)
        freq = c1.selectbox("Frequency", FREQUENCIES,
                            index=FREQUENCIES.index(cur["frequency"]) if cur else 0)
        day = c2.number_input("Day of month (monthly)", 1, 31, step=1,
                              value=(cur and cur["day"]) or today.day)
        start = c3.date_input("A payment date (yearly/weekly)",
                              value=date.fromisoformat(cur["start_date"]) if cur else today)
        has_card = bool(cur and cur["card_name"])
        cards = ["(remove card)" if has_card else "(none)"] + read("list_cards")
        card = c4.selectbox("Card", cards,
                            index=cards.index(cur["card_name"]) if has_card else 0)
        if st.form_submit_button("Save subscription"):
            try:
                _after_write(manage_subscription(
                    "update" if cur else "add", pick if cur else item, amount_inr=amount,
                    category=category, frequency=freq,
                    day=day if freq == "monthly" else None,
                    start_date=start.isoformat() if freq != "monthly" else None,
                    card_name=None if card.startswith("(") else card,
                    remove_card=card == "(remove card)"))
            except ValueError as e:
                st.error(str(e))
    if not subs:
        return

    target = st.selectbox("Pause, resume or cancel", names)
    rule = next(r for r in subs if r["item"] == target)
    b1, b2 = st.columns(2)
    if b1.button("Pause" if rule["status"] == "active" else "Resume"):
        _after_write(manage_subscription("pause" if rule["status"] == "active" else "resume",
                                         target))
    if b2.button("Cancel subscription"):
        st.session_state.confirm_cancel = target
    if st.session_state.get("confirm_cancel") == target:
        st.warning(f"Cancel {target}? No more payments are logged; past ones stay.")
        yes, no = st.columns(2)
        if yes.button("Yes, cancel it", type="primary"):
            del st.session_state.confirm_cancel
            _after_write(manage_subscription("cancel", target))
        if no.button("Keep it"):
            del st.session_state.confirm_cancel
            st.rerun()


def render_plan():
    st.subheader("Monthly budgets")
    st.caption("Leave a row at 0 for no budget. You can also say \"food budget 6000\" in Chat.")
    current = {r["category"]: r["budget"] for r in read("budget_status")}
    table = pd.DataFrame({"category": CATEGORIES + ["overall"]})
    table["budget"] = table["category"].map(current).fillna(0.0)
    edited = st.data_editor(
        table, hide_index=True, width="stretch", key="budgets_editor",
        column_config={
            "category": st.column_config.TextColumn("Category", disabled=True),
            "budget": st.column_config.NumberColumn("Monthly budget (₹)", min_value=0,
                                                    max_value=MAX_AMOUNT_INR, step=500,
                                                    format="%.0f"),
        })
    if st.button("Save budgets"):
        changed = edited[edited["budget"].fillna(0) != table["budget"]]
        for cat, amount in zip(changed["category"], changed["budget"].fillna(0), strict=True):
            set_budget(cat, float(amount))
        if len(changed):
            _after_write(f"Saved {len(changed)} budget change(s).")
        st.toast("No changes.")

    render_subscriptions()

    st.subheader("Cards")
    st.caption("Statement and due days drive the bill reminders. Leave a field empty to keep it.")
    cards = {c["card"]: c for c in read("card_status")}
    name = st.selectbox("Card", list(cards))
    if name:
        c = cards[name]
        with st.form("card_form"):
            c1, c2, c3 = st.columns(3)
            day_help = "The day from your statement, e.g. 15"
            sday = c1.number_input("Statement day (1-31)", 1, 31, value=c["statement_day"],
                                   step=1, help=day_help)
            dday = c2.number_input("Due day (1-31)", 1, 31, value=c["due_day"], step=1,
                                   help=day_help)
            limit = c3.number_input("Credit limit (₹)", 1.0, float(MAX_AMOUNT_INR),
                                    value=c["limit"], step=5000.0, format="%.0f",
                                    help="Total limit, not available limit")
            if st.form_submit_button("Save card"):
                try:
                    _after_write(register_card(name, sday, dday, limit))
                except ValueError as e:
                    st.error(str(e))
        if c["paid"] is False:
            bill = (f"{c['prev_start']:%d %b}-{c['prev_end']:%d %b} "
                    f"({inr(c['amount_due'])})")
            st.caption(f"Closed cycle {bill} unpaid.")
            if st.button("Mark bill paid"):
                st.session_state.confirm_paid = name
            if st.session_state.get("confirm_paid") == name:
                st.warning(f"Mark the {name} bill for {bill} as paid? "
                           "This logs no expense or income.")
                yes, no = st.columns(2)
                if yes.button("Yes, mark paid", type="primary"):
                    st.session_state.undo_paid = (name, c["id"], c["paid_through"])
                    del st.session_state.confirm_paid
                    _after_write(register_card(name, bill_paid=True))
                if no.button("Cancel", key="cancel_paid"):
                    del st.session_state.confirm_paid
                    st.rerun()
        undo = st.session_state.get("undo_paid")
        if undo and undo[0] == name and st.button("Undo paid"):
            set_paid_through(undo[1], undo[2])
            del st.session_state.undo_paid
            _after_write(f"{name}: bill marked unpaid again.")

    st.subheader("Income")
    st.caption("Salary, freelance or other money received. Refunds and cashback are not income.")
    with st.form("income_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        amount = c1.number_input("Amount (₹)", min_value=0.0, max_value=float(MAX_AMOUNT_INR),
                                 step=1000.0, format="%.0f")
        source = c2.selectbox("Source", INCOME_SOURCES)
        received = c3.date_input("Received on", value=date.today(), max_value=date.today())
        note = st.text_input("Note (optional)", max_chars=80)
        if st.form_submit_button("Add income"):
            try:
                _after_write(add_income(amount, source, received.isoformat(), note, "plan tab"))
            except ValueError as e:
                st.error(str(e))

    rows = read("income").head(10)
    if rows.empty:
        return
    st.caption("Last 10 entries")
    st.dataframe(_money(rows.drop(columns="month").fillna({"note": ""}), "amount_inr"),
                 hide_index=True,
                 width="stretch",
                 column_config={"id": "Id", "source": "Source", "note": "Note",
                                "received_at": st.column_config.DatetimeColumn(
                                    "Received", format="YYYY-MM-DD"),
                                "amount_inr": "Amount (₹)"})
    labels = {int(r.id): f"#{r.id} {r.received_at:%Y-%m-%d} {r.source} {inr(r.amount_inr)}"
              for r in rows.itertuples()}
    pick = st.selectbox("Delete an entry", list(labels), format_func=labels.get, index=None,
                        placeholder="Choose an entry")
    if pick is not None and st.button("Delete"):
        st.session_state.confirm_income = pick
    if st.session_state.get("confirm_income") in labels:
        target = st.session_state.confirm_income
        st.warning(f"Delete {labels[target]}? This cannot be undone.")
        yes, no = st.columns(2)
        if yes.button("Yes, delete", type="primary"):
            delete_income(target)
            del st.session_state.confirm_income
            _after_write("Income entry deleted.")
        if no.button("Cancel"):
            del st.session_state.confirm_income
            st.rerun()


UNDO_SECONDS = 120


@contextmanager
def _undoable():
    """Collect the ids a save creates so Undo can remove exactly those. Ends any older Undo."""
    st.session_state.pop("undo", None)
    ids = []
    token = core.saved_ids.set(ids)
    try:
        yield
    finally:
        core.saved_ids.reset(token)
        if ids:
            st.session_state.undo = {"rows": core.expense_snapshot(ids), "at": time.time()}


def render_undo():
    undo = st.session_state.get("undo")
    if not undo:
        return
    if time.time() - undo["at"] > UNDO_SECONDS:
        del st.session_state.undo
        if st.session_state.get("undo_btn"):  # clicked after the time ran out
            st.warning("Too late to undo; the entries are kept.")
        return
    n = len(undo["rows"])
    if st.button(f"Undo ({n} {'entry' if n == 1 else 'entries'})", key="undo_btn"):
        del st.session_state.undo
        deleted, edited, gone = core.undo_expenses(undo["rows"])
        notes = [f"Removed {deleted} {'entry' if deleted == 1 else 'entries'}."]
        if edited:
            notes.append(f"{edited} edited after saving, so kept.")
        if gone:
            notes.append(f"{gone} already deleted.")
        _after_write(" ".join(notes))


def render_quick_add():
    """Chips for the most frequent items; one tap opens a prefilled form. No model call."""
    items, opts = read("quick_items"), read("payment_options")
    labels = [f"{r['item']} · {inr(r['amount_inr'])}" for r in items] + ["+ Other"]
    v = st.session_state.get("qa_v", 0)  # bumped after a save, which resets the chips
    pick = st.pills("Quick add", labels, key=f"qa_pick_{v}", label_visibility="collapsed")
    if pick is None:
        return
    cur = None if pick == "+ Other" else items[labels.index(pick)]
    with st.form(f"qa_form_{v}"):
        item = cur["item"] if cur else st.text_input("Item", max_chars=80)
        c1, c2 = st.columns(2)
        amount = c1.number_input("Amount (₹)", 0.0, float(MAX_AMOUNT_INR), step=10.0,
                                 value=float(cur["amount_inr"]) if cur else 0.0)
        category = c2.selectbox("Category", CATEGORIES,
                                index=CATEGORIES.index(cur["category"] if cur else "other"))
        last = cur and core.payment_label(cur["payment_method"], cur["card_name"])
        method = st.pills("Paid with", list(opts), default=last if last in opts else None)
        at = st.time_input("Time today (leave empty for now)", value=None)
        if st.form_submit_button(f"Save {item}" if cur else "Save"):
            payment_method, card_name = opts.get(method, (None, None))
            try:
                with _undoable():
                        reply = core.quick_add(item, amount, category, payment_method,
                                           card_name,
                                           datetime.combine(date.today(), at) if at else None)
            except ValueError as e:
                st.error(str(e))
                return
            st.session_state.history += [  # tagged: shown in the chat, never sent to the model
                {"role": "user", "content": f"Quick add: {item}", "source": "quick_add"},
                {"role": "assistant", "content": reply, "source": "quick_add"}]
            st.session_state.qa_v = v + 1
            _after_write("Saved")


def _lock():
    st.session_state.pop("authed", None)  # require_pin() shows the PIN gate on the rerun


def _section(title: str, button: str = None, key: str = None, view: str = None):
    """A section title, with an optional text button on the right that opens `view`."""
    with st.container(horizontal=True, vertical_alignment="center", key=f"sec_{key or title}"):
        st.subheader(title)
        if button:
            st.button(button, key=key, type="tertiary", on_click=_go, args=(view,))


def render_home():
    if "history" not in st.session_state:
        st.session_state.history = []  # plain-text turns only
    if "sid" not in st.session_state:
        st.session_state.sid = uuid.uuid4().hex  # key for the per-user rate limit
    today = date.today()
    fig = read("month_figures", today)

    with st.container(horizontal=True, vertical_alignment="center", key="home_header"):
        st.html(ui.header(today))
        st.button("Lock app", icon=":material/lock:", key="lock", on_click=_lock)
    st.html(ui.hero(fig, today))
    st.html(ui.total_out(fig))

    _section("Cards")
    cards = read("card_status", today)
    st.html(ui.cards(cards, fig["upi_cash"]))
    for card in cards:
        if line := due_line(card, today):
            st.warning(line)

    _section("Quick add")
    render_quick_add()
    with st.container(key="chat_box"):  # inside a container, so it doesn't dock to the bottom
        prompt = st.chat_input("Spent 20 on chai at 7 pm using UPI", max_chars=MAX_INPUT_CHARS)
    if prompt:
        slot = st.empty()  # removed after the reply, like the old spinner
        with slot.status("Working on it...") as box:
            token = core.status_hook.set(lambda text: box.update(label=text))
            try:
                with _undoable():
                    reply = chat_turn(st.session_state.history, prompt, st.session_state.sid)
            except Exception:  # model or network failure: show a clean message, not a trace
                reply = "The AI service is unavailable right now. Please try again shortly."
            finally:
                core.status_hook.reset(token)
        slot.empty()
        st.session_state.history += [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": reply},
        ]
        st.cache_data.clear()  # any turn may have written (expenses, budgets, cards...)
        st.rerun()  # redraw the cards above with the new numbers
    render_undo()
    render_history()

    _section("Recent", "View all", "view_all", "All")
    st.html(ui.recent(read("recent").head(15), today))


def render_history():
    """Newest exchange first under the input (the model may be asking a question); older
    exchanges stay folded away so Home stays short."""
    history = st.session_state.history
    pairs = [history[i:i + 2] for i in range(0, len(history), 2)][::-1]
    for i, pair in enumerate(pairs):
        if i == 1:
            older = st.expander(f"Earlier messages ({len(pairs) - 1})")
        with older if i else st.container():
            for m in pair:
                with st.chat_message(m["role"]):
                    st.write(m["content"])


def render_all():
    st.button("Back", icon=":material/arrow_back:", key="back_home", type="tertiary",
              on_click=_go, args=("Home",))
    st.subheader("All expenses")
    render_recent()


def render_recent():
    """Last 50 entries, editable in place. Every write uses core's validation; no model call."""
    recent = read("recent")
    if recent.empty:
        st.info("No expenses yet.")
        return
    st.caption("Last 50 entries. Edit a cell and save, or tick rows to delete.")
    v = st.session_state.get("editor_v", 0)  # bumped after a write so old edits don't linger
    ids = recent["id"].astype(int).tolist()
    # edits are stored by row position: new ids (any save, Undo, Telegram) must start fresh
    key = f"recent_{v}_{hash(tuple(ids))}"
    edited = st.data_editor(
        recent.assign(delete=False), key=key, hide_index=True, width="stretch",
        num_rows="fixed", disabled=["id", "auto"],
        column_config={
            "id": "Id",
            "spent_at": st.column_config.DatetimeColumn("Time", format="YYYY-MM-DD HH:mm",
                                                        required=True),
            "item": st.column_config.TextColumn("Item", max_chars=80, required=True),
            "amount_inr": st.column_config.NumberColumn("Amount (₹)", required=True),
            "category": st.column_config.SelectboxColumn("Category", options=CATEGORIES,
                                                         required=True),
            "payment": st.column_config.SelectboxColumn(
                "Paid with", options=list(read("payment_options"))),
            "counts_d2d": st.column_config.SelectboxColumn(
                "Day-to-day", options=["default", "yes", "no"], required=True,
                help="Counts toward the day-to-day budget. Default follows the category."),
            "auto": st.column_config.CheckboxColumn("Auto", help="Posted by a subscription"),
            "delete": st.column_config.CheckboxColumn("Delete"),
        })
    changes = {ids[int(i)]: {k: val for k, val in ch.items() if k != "delete"}
               for i, ch in st.session_state[key]["edited_rows"].items()}
    changes = {i: ch for i, ch in changes.items() if ch}
    picked = edited.loc[edited["delete"], "id"].astype(int).tolist()

    c1, c2 = st.columns(2)
    if changes and c1.button(f"Save {len(changes)} change(s)"):
        st.session_state.pop("undo", None)
        errors = core.apply_edits(changes)
        if not errors:
            st.session_state.editor_v = v + 1
            _after_write(f"Saved {len(changes)} change(s).")
        st.cache_data.clear()  # valid rows were saved; the bad ones stay in the editor
        items = dict(zip(ids, recent["item"], strict=True))
        for eid, err in errors.items():
            st.error(f"#{eid} {items[eid]}: {err} Not saved.")
    if picked and c2.button(f"Delete {len(picked)} selected"):
        st.session_state.confirm_delete = picked
    pending = [i for i in st.session_state.get("confirm_delete", []) if i in ids]
    if pending:
        items = recent.set_index("id").loc[pending, "item"]
        st.warning(f"Delete {', '.join(f'#{i} {n}' for i, n in items.items())}? "
                   "This cannot be undone.")
        yes, no = st.columns(2)
        if yes.button("Yes, delete", type="primary", key="yes_delete_expenses"):
            for i in pending:
                core.delete_expense(i)
            del st.session_state.confirm_delete
            st.session_state.pop("undo", None)
            st.session_state.editor_v = v + 1
            _after_write(f"Deleted {len(pending)} entr{'y' if len(pending) == 1 else 'ies'}.")
        if no.button("Cancel", key="cancel_delete_expenses"):
            del st.session_state.confirm_delete
            st.session_state.editor_v = v + 1  # untick the boxes
            st.rerun()


def render_analytics():
    df_all = read("expenses")
    if df_all.empty:
        st.info("Log some expenses in the Chat tab and your analytics will appear here.")
        return

    today = date.today()
    preset = st.radio("Period", ["This month", "Last 30 days", "Last 90 days",
                                 "All time", "Custom"], horizontal=True,
                      key="period", persist_state="session")  # kept while another view shows
    if preset == "This month":
        start, end = today.replace(day=1), today
    elif preset == "Last 30 days":
        start, end = today - timedelta(days=29), today
    elif preset == "Last 90 days":
        start, end = today - timedelta(days=89), today
    elif preset == "All time":
        start, end = df_all["date"].min().date(), max(df_all["date"].max().date(), today)
    else:
        picked = st.date_input("Date range", value=(today - timedelta(days=29), today),
                               key="period_range", persist_state="session")
        if not (isinstance(picked, (tuple, list)) and len(picked) == 2):
            st.info("Pick both a start and an end date.")
            return
        start, end = picked

    df = an.filter_range(df_all, start, end)
    if df.empty:
        st.warning("No expenses in this period.")
        return

    # --- headline numbers
    k = an.kpis(df, start, end)
    mc = an.month_comparison(df_all, today)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total spent", inr(k["total"]))
    c2.metric("Average per day", inr(round(k["avg_per_day"])))
    c3.metric("Purchases", k["transactions"])
    c4.metric("Top category", k["top_category"], inr(k["top_category_amount"]),
              delta_color="off")
    c1, c2 = st.columns(2)
    if mc["has_prev"]:
        diff = mc["this"] - mc["prev_same_days"]
        c1.metric("This month so far vs same days last month",
                  inr(mc["this"]), ("+" if diff > 0 else "") + inr(diff),
                  delta_color="inverse")
    c2.metric("Projected month-end", inr(round(an.month_projection(df_all, today))),
              help="Spending pace so far this month (subscriptions excluded), plus "
                   "subscriptions logged and still due this month.")

    # --- budgets (always this month, whatever the period above)
    st.subheader("Budgets this month")
    budgets = read("budget_progress")
    if budgets.empty:
        st.caption("No budgets yet. Set them in the Plan tab or say \"food budget 6000\" in Chat.")
    else:
        st.altair_chart(budget_chart(budgets), width="stretch", theme=None)

    # --- income and savings (per month, whatever the period above)
    st.subheader("Income and savings")
    s = read("savings", today.strftime("%Y-%m"))
    c1, c2, c3 = st.columns(3)
    c1.metric("Income this month", inr(s["income"]))
    c2.metric("Saved this month", inr(s["net"]))
    c3.metric("Savings rate", "n/a" if s["rate"] is None else f"{s['rate']:.0f}%")
    income = read("income")
    if income.empty:
        st.caption("No income yet. Add it in the Plan tab or say \"got salary 50000\" in Chat.")
    else:
        monthly = an.savings_by_month(df_all, income).tail(12)
        st.altair_chart(glass_line_chart(monthly, "%b %Y"), width="stretch", theme=None)

    # --- daily trend
    st.subheader("Daily spending")
    st.altair_chart(glass_line_chart(an.daily_series(df, start, end)),
                    width="stretch", theme=None)

    left, right = st.columns(2)
    with left:
        st.subheader("Where the money goes")
        st.dataframe(
            _money(an.category_table(df), "total"), hide_index=True, width="stretch",
            column_config={
                "category": "Category",
                "total": "Total (₹)",
                "purchases": "Purchases",
                "share_pct": st.column_config.ProgressColumn(
                    "Share", format="%.0f%%", min_value=0, max_value=100, color=ACCENT),
            })
    with right:
        st.subheader("Monthly totals")
        st.altair_chart(glass_bar_chart(an.monthly_trend(df_all)),
                        width="stretch", theme=None)

    left, right = st.columns(2)
    with left:
        st.subheader("Weekdays vs weekends")
        w = an.weekday_vs_weekend(df, start, end)
        m1, m2 = st.columns(2)
        m1.metric("Weekday avg / day", inr(round(w["weekday_avg"])))
        m2.metric("Weekend avg / day", inr(round(w["weekend_avg"])))
        st.altair_chart(glass_bar_chart(an.by_weekday(df, start, end)),
                        width="stretch", theme=None)
    with right:
        st.subheader("Top items")
        st.dataframe(_money(an.top_items(df), "total"), hide_index=True, width="stretch",
                     column_config={"item": "Item", "total": "Total (₹)", "times": "Times"})
        st.subheader("Biggest single expenses")
        st.dataframe(_money(an.biggest_expenses(df), "amount_inr"), hide_index=True,
                     width="stretch",
                     column_config={"spent_at": "Time", "item": "Item",
                                    "amount_inr": "Amount (₹)", "category": "Category"})

    # --- credit-card spending for the selected period
    st.divider()
    st.subheader("Credit-card spending")

    card_summary, card_transactions = an.credit_card_spending(df)

    if card_summary.empty:
        st.info("No recorded credit-card purchases in this period.")
    else:
        total_card_spend = card_summary["total_spend"].sum()
        st.metric("Total credit-card spending", inr(total_card_spend))

        st.caption("Spending by card")
        st.dataframe(
            _money(card_summary.rename(columns={"card_name": "Credit card",
                                                "total_spend": "Total spent (₹)",
                                                "transactions": "Purchases"}),
                   "Total spent (₹)"),
            hide_index=True,
            width="stretch",
        )

        st.caption("Credit-card transactions")
        transaction_columns = [
            col for col in
            ["spent_at", "item", "amount_inr", "card_name"]
            if col in card_transactions.columns
        ]
        st.dataframe(
            _money(card_transactions[transaction_columns].rename(
                columns={
                    "spent_at": "Date",
                    "item": "Item",
                    "amount_inr": "Amount (₹)",
                    "card_name": "Credit card",
                }
            ), "Amount (₹)"),
            hide_index=True,
            width="stretch",
        )

    st.subheader("Card cycles")
    cards = pd.DataFrame(read("card_status"))
    cards = cards[cards["statement_day"].notna()] if not cards.empty else cards
    if cards.empty:
        st.caption("Set a card's statement day in the Plan tab to see its cycle.")
    else:
        st.dataframe(
            _money(cards[["card", "amount_due", "due_date", "paid", "spent_cycle",
                          "utilisation"]], "amount_due", "spent_cycle"),
            hide_index=True, width="stretch",
            column_config={
                "card": "Card", "paid": "Paid", "due_date": "Due",
                "amount_due": "Amount due (₹)", "spent_cycle": "Spent this cycle (₹)",
                "utilisation": st.column_config.ProgressColumn(
                    "Limit used", format="%.0f%%", min_value=0, max_value=100, color=ACCENT),
            })

    st.download_button(
        "Download this period as CSV",
        df.drop(columns=["date", "month"]).to_csv(index=False),
        file_name=f"expenses_{start}_{end}.csv",
        mime="text/csv",
    )


def render_llm_usage():
    include_eval = st.checkbox("Include evaluation runs", value=False)
    df = read("llm_calls", include_eval)
    if df.empty:
        st.info("No model calls recorded yet. Send a message in the Chat tab.")
        return

    s = an.llm_summary(df)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Calls today", s["calls_today"])
    c2.metric("Tokens today", f"{s['tokens_today']:,}")
    c3.metric("Median latency", f"{s['p50_ms'] / 1000:.1f} s")
    c4.metric("95th percentile", f"{s['p95_ms'] / 1000:.1f} s")
    c5.metric("Success rate", f"{s['success_rate']:.0f}%")
    st.caption(f"Saved without a model call today: {read('local_saves')} message(s). "
               "These are not counted above.")
    backup = (int((df["model"] == core.FALLBACK_MODEL).sum())
              if core.FALLBACK_MODEL and core.FALLBACK_MODEL != core.MODEL else 0)
    st.metric("Backup model calls", backup,
              help=f"Calls answered or tried by {core.FALLBACK_MODEL or 'no backup model'} "
                   f"after {core.MODEL} was busy or out of daily quota.")

    daily = an.llm_daily(df)
    left, right = st.columns(2)
    with left:
        st.subheader("Calls per day")
        st.altair_chart(glass_bar_chart(daily[["Calls"]]), width="stretch", theme=None)
    with right:
        st.subheader("Tokens per day")
        st.altair_chart(glass_bar_chart(daily[["Tokens"]]),
                        width="stretch", theme=None)

    st.subheader("Recent errors")
    errors = (df[df["status"] != "ok"].sort_values("ts", ascending=False).head(10)
              [["ts", "status", "error", "latency_ms"]])
    if errors.empty:
        st.caption("No errors recorded.")
    else:
        st.dataframe(errors, hide_index=True, width="stretch")


# Nav order; None is the raised "+" in the middle. Material Symbols are line icons, not emoji.
NAV = [("Home", ":material/home:"), ("Analytics", ":material/bar_chart:"), None,
       ("Plan", ":material/calendar_month:"), ("Usage", ":material/memory:")]


def _go(view: str):
    st.session_state.view = view


def render_nav():
    """Fixed bottom bar (CSS on .st-key-bottomnav). Without that CSS it is a plain row."""
    active = {"All": "Home"}.get(st.session_state.view, st.session_state.view)
    with st.container(key="bottomnav", horizontal=True, horizontal_alignment="distribute",
                      vertical_alignment="center", gap=None):
        for entry in NAV:
            if entry is None:
                st.button("Add expense", icon=":material/add:", key="nav_add",
                          on_click=_go, args=("Home",))
                continue
            name, icon = entry
            st.button(name, icon=icon, key=f"nav_{name}", on_click=_go, args=(name,),
                      type="primary" if name == active else "tertiary")


st.set_page_config(page_title="QORVIAN", layout="centered")
st.markdown(THEME_CSS, unsafe_allow_html=True)
require_pin()
init_db()
if post_due_recurring():
    st.cache_data.clear()

# Only the selected view runs, so a chat message no longer rebuilds every chart.
VIEWS = {"Home": render_home, "Analytics": render_analytics, "Plan": render_plan,
         "Usage": render_llm_usage, "All": render_all}
st.session_state.setdefault("view", "Home")
render_nav()
VIEWS.get(st.session_state.view, render_home)()
