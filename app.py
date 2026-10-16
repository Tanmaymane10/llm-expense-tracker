"""Streamlit dashboard.  Run with:  streamlit run app.py"""
import uuid
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import analytics as an
from core import MAX_INPUT_CHARS, chat_turn, get_conn, init_db


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
                "SELECT id, spent_at, item, amount_inr, category FROM expenses "
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
    if mc["has_prev"]:
        diff = mc["this"] - mc["prev_same_days"]
        st.metric("This month so far vs same days last month",
                  f"Rs {mc['this']:,.0f}", f"{diff:+,.0f} Rs", delta_color="inverse")

    # --- daily trend
    st.subheader("Daily spending")
    st.line_chart(an.daily_series(df, start, end))

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
                    "Share", format="%.0f%%", min_value=0, max_value=100),
            })
    with right:
        st.subheader("Monthly totals")
        st.bar_chart(an.monthly_trend(df_all))

    left, right = st.columns(2)
    with left:
        st.subheader("Weekdays vs weekends")
        w = an.weekday_vs_weekend(df, start, end)
        m1, m2 = st.columns(2)
        m1.metric("Weekday avg / day", f"Rs {w['weekday_avg']:,.0f}")
        m2.metric("Weekend avg / day", f"Rs {w['weekend_avg']:,.0f}")
        st.bar_chart(an.by_weekday(df, start, end))
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
        st.bar_chart(daily[["Calls"]])
    with right:
        st.subheader("Tokens per day")
        st.bar_chart(daily[["Tokens"]])

    st.subheader("Recent errors")
    errors = (df[df["status"] != "ok"].sort_values("ts", ascending=False).head(10)
              [["ts", "status", "error", "latency_ms"]])
    if errors.empty:
        st.caption("No errors recorded.")
    else:
        st.dataframe(errors, hide_index=True, width="stretch")


st.set_page_config(page_title="Expense Tracker", layout="wide")
init_db()
st.title("Expense Tracker")

tab_chat, tab_stats, tab_llm = st.tabs(["Chat", "Analytics", "LLM usage"])
with tab_chat:
    render_chat()
with tab_stats:
    render_analytics()
with tab_llm:
    render_llm_usage()