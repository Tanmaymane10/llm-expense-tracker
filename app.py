"""Streamlit dashboard.  Run with:  streamlit run app.py"""
import uuid
from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st

import analytics as an
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
:root {
  --bg-0: #06150f;
  --bg-1: #0c241c;
  --glass: rgba(255, 255, 255, 0.045);
  --glass-strong: rgba(255, 255, 255, 0.07);
  --edge: rgba(255, 255, 255, 0.09);
  --accent: #6fd9c4;
  --accent-soft: rgba(111, 217, 196, 0.14);
  --mint: var(--accent);  /* old name kept so every rule reads the one accent */
  --text: #dbe9e2;
  --muted: #8aa89c;
  --radius: 14px;
  --pad: 0.85rem 1rem;
}
.stApp {
  background:
    radial-gradient(900px 520px at 10% -10%, rgba(111, 217, 196, 0.08), transparent 65%),
    linear-gradient(165deg, var(--bg-1), var(--bg-0) 75%);
  color: var(--text);
}
[data-testid="stHeader"] { background: transparent; }
h1, h2, h3, h4, label, p, span, div { color: var(--text); }
h1 { letter-spacing: 0.04em; font-weight: 700; }
h2, h3 { font-weight: 600; }
[data-testid="stCaptionContainer"], .stCaption { color: var(--muted) !important; }

/* glass cards */
[data-testid="stMetric"], [data-testid="stDataFrame"],
[data-testid="stChatMessage"], [data-testid="stAlert"],
[data-testid="stForm"] {
  box-sizing: border-box;
  max-width: 100%;
  background: var(--glass);
  border: 1px solid var(--edge);
  border-radius: var(--radius);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  padding: var(--pad);
}
[data-testid="stMetricValue"] { color: var(--text); font-weight: 600; }
[data-testid="stMetricLabel"] p { color: var(--muted); }
[data-testid="stDataFrame"] { padding: 0.35rem; overflow: hidden; }
/* the alert draws its own coloured box; the glass card is just its frame */
[data-testid="stAlert"] { padding: 0; overflow: hidden; }
[data-testid="stAlert"] > div { border-radius: var(--radius); }

/* chart cards */
[data-testid="stVegaLiteChart"], [data-testid="stArrowVegaLiteChart"] {
  box-sizing: border-box;
  max-width: 100%;
  background: var(--glass);
  border: 1px solid var(--edge);
  border-radius: var(--radius);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  padding: var(--pad);
  padding-bottom: 0.4rem;
  overflow: hidden;
}

/* tabs as pills */
.stTabs [data-baseweb="tab-list"],
.stTabs [role="tablist"] {
  gap: 0.5rem !important;
  border-bottom: none !important;
  box-shadow: none !important;
  padding: 0.25rem 0 0.75rem 0 !important;
}
.stTabs [data-baseweb="tab-border"],
.stTabs [data-baseweb="tab-highlight"] {
  display: none !important;
  background: transparent !important;
  height: 0 !important;
}
.stTabs button[role="tab"],
.stTabs [data-baseweb="tab"] {
  background: var(--glass) !important;
  border: 1px solid var(--edge) !important;
  border-radius: 999px !important;
  padding: 0.45rem 1.25rem !important;
  height: auto !important;
  min-height: 0 !important;
  margin: 0 !important;
  color: var(--muted) !important;
  transition: background 0.15s ease, border-color 0.15s ease;
}
.stTabs button[role="tab"] p,
.stTabs [data-baseweb="tab"] p { color: inherit !important; margin: 0 !important; }
.stTabs button[role="tab"]:hover { border-color: var(--mint) !important; }
.stTabs button[role="tab"][aria-selected="true"] {
  background: var(--accent-soft) !important;
  border: 1px solid var(--mint) !important;
  color: var(--mint) !important;
  font-weight: 600;
}

/* period radio as pills */
div[role="radiogroup"] { gap: 0.4rem; flex-wrap: wrap; }
div[role="radiogroup"] label {
  background: var(--glass);
  border: 1px solid var(--edge);
  border-radius: 999px;
  padding: 0.2rem 0.9rem;
}

/* inputs and buttons */
[data-testid="stChatInput"] {
  background: var(--glass-strong);
  border: 1px solid var(--edge);
  border-radius: var(--radius);
}
.stButton > button, .stDownloadButton > button,
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"] {
  background: var(--accent-soft) !important;
  border: 1px solid var(--mint) !important;
  border-radius: 999px !important;
  padding: 0.5rem 1.4rem !important;
  color: var(--mint) !important;
  font-weight: 600 !important;
  transition: background 0.15s ease, color 0.15s ease;
}
.stButton > button *, .stDownloadButton > button *,
[data-testid="stBaseButton-secondary"] *, [data-testid="stBaseButton-primary"] * {
  color: inherit !important;
  font-weight: inherit !important;
}
.stButton > button:hover, .stDownloadButton > button:hover,
[data-testid="stBaseButton-secondary"]:hover, [data-testid="stBaseButton-primary"]:hover {
  background: rgba(111, 217, 196, 0.26) !important;
  color: var(--text) !important;
}
.stButton > button:focus-visible, .stDownloadButton > button:focus-visible {
  outline: 2px solid var(--accent) !important;
  outline-offset: 2px;
}
hr { border-color: var(--edge); }

@media (max-width: 640px) {
  .block-container { padding: 1rem 0.8rem; }
}
</style>
"""


# ---- chart helpers: transparent background, soft grid, the THEME_CSS accent
ACCENT, ACCENT_SOFT = "#6fd9c4", "rgba(111,217,196,0.45)"  # = --accent in THEME_CSS
MUTED, GRID = "#8aa89c", "rgba(255,255,255,0.07)"


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
                     text=[f"Rs {s:,.0f} / {b:,.0f}" for s, b in pairs])
    y = alt.Y("label:N", sort=None, title=None, axis=alt.Axis(grid=False))
    x = alt.X("pct:Q", title=None, axis=alt.Axis(format=".0f", labelExpr="datum.label + '%'",
                                           tickCount=6, labelFlush=True),
              scale=alt.Scale(domain=[0, max(100, float(data["pct"].max()) * 1.15)], nice=False))
    bars = alt.Chart(data).mark_bar(cornerRadiusEnd=6, size=18).encode(
        x=x, y=y,
        color=alt.Color("state:N", legend=None, scale=alt.Scale(
            domain=["ok", "warn", "over"], range=[ACCENT, "#fbbf24", "#f87171"])),
        tooltip=["label", alt.Tooltip("spent:Q", format=",.0f", title="Spent (Rs)"),
                 alt.Tooltip("budget:Q", format=",.0f", title="Budget (Rs)"),
                 alt.Tooltip("pct:Q", format=".0f", title="% used")])
    text = bars.mark_text(align="left", dx=6, color=MUTED).encode(text="text:N")
    limit = alt.Chart(pd.DataFrame({"pct": [100]})).mark_rule(
        color=MUTED, strokeDash=[4, 4]).encode(x="pct:Q")
    # right padding leaves room for the "Rs spent / budget" label past the longest bar
    return _style((bars + text + limit).properties(
        height=40 * len(data) + 20, padding={"left": 5, "top": 5, "bottom": 5, "right": 110}))


def render_subscriptions():
    st.subheader("Subscriptions")
    st.caption("Each payment is logged automatically on its due date. You can also say "
               "\"netflix 649 every month on the 5th\" in Chat.")
    today = date.today()
    subs = subscription_status(today)
    if subs:
        st.dataframe(
            pd.DataFrame(subs)[["item", "amount_inr", "schedule", "next_due", "monthly",
                                "card_name", "status"]].fillna(""),
            hide_index=True, width="stretch",
            column_config={
                "item": "Item", "schedule": "Renews", "next_due": "Next due",
                "card_name": "Card", "status": "Status",
                "amount_inr": st.column_config.NumberColumn("Amount (Rs)", format="%.0f"),
                "monthly": st.column_config.NumberColumn("Per month (Rs)", format="%.0f"),
            })
    names = [r["item"] for r in subs]
    pick = st.selectbox("Add or update", ["New subscription"] + names)
    cur = next((r for r in subs if r["item"] == pick), None)
    with st.form("sub_form"):
        c1, c2, c3 = st.columns(3)
        item = c1.text_input("Item", value=pick if cur else "", disabled=bool(cur), max_chars=80)
        amount = c2.number_input("Amount (Rs)", 0.0, float(MAX_AMOUNT_INR), step=100.0,
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
        cards = ["(remove card)" if has_card else "(none)"] + list_cards()
        card = c4.selectbox("Card", cards,
                            index=cards.index(cur["card_name"]) if has_card else 0)
        if st.form_submit_button("Save subscription"):
            try:
                st.toast(manage_subscription(
                    "update" if cur else "add", pick if cur else item, amount_inr=amount,
                    category=category, frequency=freq,
                    day=day if freq == "monthly" else None,
                    start_date=start.isoformat() if freq != "monthly" else None,
                    card_name=None if card.startswith("(") else card,
                    remove_card=card == "(remove card)"))
                st.rerun()
            except ValueError as e:
                st.error(str(e))
    if not subs:
        return

    target = st.selectbox("Pause, resume or cancel", names)
    rule = next(r for r in subs if r["item"] == target)
    b1, b2 = st.columns(2)
    if b1.button("Pause" if rule["status"] == "active" else "Resume"):
        st.toast(manage_subscription("pause" if rule["status"] == "active" else "resume",
                                     target))
        st.rerun()
    if b2.button("Cancel subscription"):
        st.session_state.confirm_cancel = target
    if st.session_state.get("confirm_cancel") == target:
        st.warning(f"Cancel {target}? No more payments are logged; past ones stay.")
        yes, no = st.columns(2)
        if yes.button("Yes, cancel it", type="primary"):
            del st.session_state.confirm_cancel
            st.toast(manage_subscription("cancel", target))
            st.rerun()
        if no.button("Keep it"):
            del st.session_state.confirm_cancel
            st.rerun()


def render_plan():
    st.subheader("Monthly budgets")
    st.caption("Leave a row at 0 for no budget. You can also say \"food budget 6000\" in Chat.")
    current = {r["category"]: r["budget"] for r in budget_status()}
    table = pd.DataFrame({"category": CATEGORIES + ["overall"]})
    table["budget"] = table["category"].map(current).fillna(0.0)
    edited = st.data_editor(
        table, hide_index=True, width="stretch", key="budgets_editor",
        column_config={
            "category": st.column_config.TextColumn("Category", disabled=True),
            "budget": st.column_config.NumberColumn("Monthly budget (Rs)", min_value=0,
                                                    max_value=MAX_AMOUNT_INR, step=500,
                                                    format="%.0f"),
        })
    if st.button("Save budgets"):
        changed = edited[edited["budget"].fillna(0) != table["budget"]]
        for cat, amount in zip(changed["category"], changed["budget"].fillna(0), strict=True):
            set_budget(cat, float(amount))
        st.toast(f"Saved {len(changed)} budget change(s)." if len(changed) else "No changes.")
        if len(changed):
            st.rerun()  # Analytics renders before this tab, so redraw it with the new budgets

    render_subscriptions()

    st.subheader("Cards")
    st.caption("Statement and due days drive the bill reminders. Leave a field empty to keep it.")
    cards = {c["card"]: c for c in card_status()}
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
            limit = c3.number_input("Credit limit (Rs)", 1.0, float(MAX_AMOUNT_INR),
                                    value=c["limit"], step=5000.0, format="%.0f",
                                    help="Total limit, not available limit")
            if st.form_submit_button("Save card"):
                try:
                    st.toast(register_card(name, sday, dday, limit))
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
        if c["paid"] is False:
            bill = (f"{c['prev_start']:%d %b}-{c['prev_end']:%d %b} "
                    f"(Rs {c['amount_due']:,.0f})")
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
                    st.toast(register_card(name, bill_paid=True))
                    st.rerun()
                if no.button("Cancel", key="cancel_paid"):
                    del st.session_state.confirm_paid
                    st.rerun()
        undo = st.session_state.get("undo_paid")
        if undo and undo[0] == name and st.button("Undo paid"):
            set_paid_through(undo[1], undo[2])
            del st.session_state.undo_paid
            st.toast(f"{name}: bill marked unpaid again.")
            st.rerun()

    st.subheader("Income")
    st.caption("Salary, freelance or other money received. Refunds and cashback are not income.")
    with st.form("income_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        amount = c1.number_input("Amount (Rs)", min_value=0.0, max_value=float(MAX_AMOUNT_INR),
                                 step=1000.0, format="%.0f")
        source = c2.selectbox("Source", INCOME_SOURCES)
        received = c3.date_input("Received on", value=date.today(), max_value=date.today())
        note = st.text_input("Note (optional)", max_chars=80)
        if st.form_submit_button("Add income"):
            try:
                st.toast(add_income(amount, source, received.isoformat(), note, "plan tab"))
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    rows = an.load_income().head(10)
    if rows.empty:
        return
    st.caption("Last 10 entries")
    st.dataframe(rows.drop(columns="month").fillna({"note": ""}), hide_index=True,
                 width="stretch",
                 column_config={"id": "Id", "source": "Source", "note": "Note",
                                "received_at": st.column_config.DatetimeColumn(
                                    "Received", format="YYYY-MM-DD"),
                                "amount_inr": st.column_config.NumberColumn(
                                    "Amount (Rs)", format="%.0f")})
    labels = {int(r.id): f"#{r.id} {r.received_at:%Y-%m-%d} {r.source} Rs {r.amount_inr:,.0f}"
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
            st.toast("Income entry deleted.")
            st.rerun()
        if no.button("Cancel"):
            del st.session_state.confirm_income
            st.rerun()


def render_chat():
    if "history" not in st.session_state:
        st.session_state.history = []  # plain-text turns only
    if "sid" not in st.session_state:
        st.session_state.sid = uuid.uuid4().hex  # key for the per-user rate limit

    chat_col, data_col = st.columns(2)

    with chat_col:
        # The input box comes FIRST so it stays at the top of the chat.
        prompt = st.chat_input("e.g. bought vada pav for 30 and auto for 120",
                               max_chars=MAX_INPUT_CHARS)
        if prompt:
            with st.spinner("Working on it..."):
                try:
                    reply = chat_turn(st.session_state.history, prompt, st.session_state.sid)
                except Exception:  # model or network failure: show a clean message, not a trace
                    reply = "The AI service is unavailable right now. Please try again shortly."
            st.session_state.history += [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": reply},
            ]

        # Newest exchange first, so the latest reply sits right under the input box.
        history = st.session_state.history
        pairs = [history[i:i + 2] for i in range(0, len(history), 2)]
        for pair in reversed(pairs):
            for m in pair:
                with st.chat_message(m["role"]):
                    st.write(m["content"])

    with data_col:
        with get_conn() as conn:
            recent = pd.read_sql_query(
                "SELECT id, spent_at, item || CASE WHEN recurring_id IS NOT NULL "
                "THEN ' (auto)' ELSE '' END AS item, amount_inr, category FROM expenses "
                "ORDER BY id DESC LIMIT 50", conn)
        if recent.empty:
            st.info("No expenses yet.")
        else:
            st.caption("Last 50 entries logged")
            st.dataframe(recent, width="stretch", hide_index=True)


def render_analytics():
    df_all = an.load_expenses()  # loaded after the chat block so new entries show up at once
    if df_all.empty:
        st.info("Log some expenses in the Chat tab and your analytics will appear here.")
        return

    today = date.today()
    preset = st.radio("Period", ["This month", "Last 30 days", "Last 90 days",
                                 "All time", "Custom"], horizontal=True)
    if preset == "This month":
        start, end = today.replace(day=1), today
    elif preset == "Last 30 days":
        start, end = today - timedelta(days=29), today
    elif preset == "Last 90 days":
        start, end = today - timedelta(days=89), today
    elif preset == "All time":
        start, end = df_all["date"].min().date(), max(df_all["date"].max().date(), today)
    else:
        picked = st.date_input("Date range", value=(today - timedelta(days=29), today))
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
    c1.metric("Total spent", f"Rs {k['total']:,.0f}")
    c2.metric("Average per day", f"Rs {k['avg_per_day']:,.0f}")
    c3.metric("Purchases", k["transactions"])
    c4.metric("Top category", k["top_category"], f"Rs {k['top_category_amount']:,.0f}",
              delta_color="off")
    c1, c2 = st.columns(2)
    if mc["has_prev"]:
        diff = mc["this"] - mc["prev_same_days"]
        c1.metric("This month so far vs same days last month",
                  f"Rs {mc['this']:,.0f}", f"{diff:+,.0f} Rs", delta_color="inverse")
    c2.metric("Projected month-end", f"Rs {an.month_projection(df_all, today):,.0f}",
              help="Spending pace so far this month (subscriptions excluded), plus "
                   "subscriptions logged and still due this month.")

    # --- budgets (always this month, whatever the period above)
    st.subheader("Budgets this month")
    budgets = an.budget_progress()
    if budgets.empty:
        st.caption("No budgets yet. Set them in the Plan tab or say \"food budget 6000\" in Chat.")
    else:
        st.altair_chart(budget_chart(budgets), width="stretch", theme=None)

    # --- income and savings (per month, whatever the period above)
    st.subheader("Income and savings")
    s = savings(today.strftime("%Y-%m"))
    c1, c2, c3 = st.columns(3)
    c1.metric("Income this month", f"Rs {s['income']:,.0f}")
    c2.metric("Saved this month", f"Rs {s['net']:,.0f}")
    c3.metric("Savings rate", "n/a" if s["rate"] is None else f"{s['rate']:.0f}%")
    income = an.load_income()
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
            an.category_table(df), hide_index=True, width="stretch",
            column_config={
                "category": "Category",
                "total": st.column_config.NumberColumn("Total (Rs)", format="%.0f"),
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
        m1.metric("Weekday avg / day", f"Rs {w['weekday_avg']:,.0f}")
        m2.metric("Weekend avg / day", f"Rs {w['weekend_avg']:,.0f}")
        st.altair_chart(glass_bar_chart(an.by_weekday(df, start, end)),
                        width="stretch", theme=None)
    with right:
        st.subheader("Top items")
        st.dataframe(an.top_items(df), hide_index=True, width="stretch")
        st.subheader("Biggest single expenses")
        st.dataframe(an.biggest_expenses(df), hide_index=True, width="stretch")

    # --- credit-card spending for the selected period
    st.divider()
    st.subheader("Credit-card spending")

    card_summary, card_transactions = an.credit_card_spending(df)

    if card_summary.empty:
        st.info("No recorded credit-card purchases in this period.")
    else:
        total_card_spend = card_summary["total_spend"].sum()
        st.metric("Total credit-card spending", f"Rs {total_card_spend:,.0f}")

        st.caption("Spending by card")
        st.dataframe(
            card_summary.rename(
                columns={
                    "card_name": "Credit card",
                    "total_spend": "Total spent (Rs)",
                    "transactions": "Purchases",
                }
            ),
            hide_index=True,
            width="stretch",
            column_config={
                "Total spent (Rs)": st.column_config.NumberColumn(
                    "Total spent (Rs)", format="%.2f"
                ),
            },
        )

        st.caption("Credit-card transactions")
        transaction_columns = [
            col for col in
            ["spent_at", "item", "amount_inr", "card_name"]
            if col in card_transactions.columns
        ]
        st.dataframe(
            card_transactions[transaction_columns].rename(
                columns={
                    "spent_at": "Date",
                    "item": "Item",
                    "amount_inr": "Amount (Rs)",
                    "card_name": "Credit card",
                }
            ),
            hide_index=True,
            width="stretch",
        )

    st.subheader("Card cycles")
    cards = pd.DataFrame(card_status())
    cards = cards[cards["statement_day"].notna()] if not cards.empty else cards
    if cards.empty:
        st.caption("Set a card's statement day in the Plan tab to see its cycle.")
    else:
        st.dataframe(
            cards[["card", "amount_due", "due_date", "paid", "spent_cycle", "utilisation"]],
            hide_index=True, width="stretch",
            column_config={
                "card": "Card", "paid": "Paid", "due_date": "Due",
                "amount_due": st.column_config.NumberColumn("Amount due (Rs)", format="%.0f"),
                "spent_cycle": st.column_config.NumberColumn("Spent this cycle (Rs)",
                                                             format="%.0f"),
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
    df = an.load_llm_calls(include_eval)
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


st.set_page_config(page_title="QORVIAN", layout="wide")
st.markdown(THEME_CSS, unsafe_allow_html=True)
require_pin()
init_db()
post_due_recurring()
st.title("QORVIAN")
for _card in card_status():
    if _line := due_line(_card, date.today()):
        st.warning(_line)

tab_chat, tab_stats, tab_plan, tab_llm = st.tabs(["Chat", "Analytics", "Plan", "LLM usage"])
with tab_chat:
    render_chat()
with tab_stats:
    render_analytics()
with tab_plan:
    render_plan()
with tab_llm:
    render_llm_usage()