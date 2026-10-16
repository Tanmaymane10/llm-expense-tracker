"""Spending analytics. Pure pandas functions: easy to test, no Streamlit or LLM code in here."""
from datetime import date

import pandas as pd

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]



def load_expenses() -> pd.DataFrame:
    """Read expenses and optional payment/card details from SQLite."""
    from core import get_conn

    with get_conn() as conn:
        df = pd.read_sql_query(
            """
            SELECT
                e.id,
                e.spent_at,
                e.item,
                e.amount_inr,
                e.category,
                e.payment_method,
                e.card_id,
                cc.card_name
            FROM expenses AS e
            LEFT JOIN credit_cards AS cc
                ON e.card_id = cc.id
            """,
            conn,
        )

    if df.empty:
        return df

    df["spent_at"] = pd.to_datetime(df["spent_at"], errors="coerce")
    df = df.dropna(subset=["spent_at"]).copy()
    df["date"] = df["spent_at"].dt.normalize()
    df["month"] = df["spent_at"].dt.strftime("%Y-%m")
    return df



def filter_range(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    mask = (df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))
    return df[mask]


def daily_series(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """Spend per calendar day (days with no spending count as 0) plus a 7-day average."""
    idx = pd.date_range(start, end, freq="D")
    daily = df.groupby("date")["amount_inr"].sum().reindex(idx, fill_value=0.0)
    out = pd.DataFrame({"Daily": daily})
    out["7-day avg"] = daily.rolling(7, min_periods=1).mean()
    return out


def kpis(df: pd.DataFrame, start: date, end: date) -> dict:
    days = (pd.Timestamp(end) - pd.Timestamp(start)).days + 1
    total = float(df["amount_inr"].sum())
    by_cat = df.groupby("category")["amount_inr"].sum()
    return {
        "total": total,
        "transactions": int(len(df)),
        "avg_per_day": total / days if days > 0 else 0.0,
        "top_category": by_cat.idxmax() if len(by_cat) else "-",
        "top_category_amount": float(by_cat.max()) if len(by_cat) else 0.0,
    }


def month_comparison(df_all: pd.DataFrame, today: date) -> dict:
    """This month so far vs the SAME NUMBER OF DAYS of last month (a fair comparison)."""
    this_month = today.strftime("%Y-%m")
    prev_month = str(pd.Period(this_month, "M") - 1)
    this_total = df_all.loc[df_all["month"] == this_month, "amount_inr"].sum()
    prev = df_all[(df_all["month"] == prev_month)
                  & (df_all["spent_at"].dt.day <= today.day)]
    return {"this": float(this_total), "prev_same_days": float(prev["amount_inr"].sum()),
            "has_prev": not prev.empty}


def monthly_trend(df_all: pd.DataFrame) -> pd.DataFrame:
    return df_all.groupby("month")["amount_inr"].sum().rename("Total spent").to_frame()


def category_table(df: pd.DataFrame) -> pd.DataFrame:
    t = (df.groupby("category")["amount_inr"].agg(total="sum", purchases="size")
         .sort_values("total", ascending=False).reset_index())
    t["share_pct"] = 100 * t["total"] / t["total"].sum() if len(t) else 0.0
    return t


def weekday_vs_weekend(df: pd.DataFrame, start: date, end: date) -> dict:
    daily = daily_series(df, start, end)["Daily"]
    weekend = daily.index.dayofweek >= 5
    return {
        "weekday_avg": float(daily[~weekend].mean()) if (~weekend).any() else 0.0,
        "weekend_avg": float(daily[weekend].mean()) if weekend.any() else 0.0,
    }


def by_weekday(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """Average spend per day of the week (numbered labels keep charts in Mon..Sun order)."""
    daily = daily_series(df, start, end)["Daily"]
    avg = daily.groupby(daily.index.dayofweek).mean().reindex(range(7), fill_value=0.0)
    avg.index = [f"{i + 1} {WEEKDAYS[i]}" for i in range(7)]
    return avg.rename("Avg spend").to_frame()


def top_items(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    return (df.groupby("item")["amount_inr"].agg(total="sum", times="size")
            .sort_values("total", ascending=False).head(n).reset_index())


def biggest_expenses(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    cols = ["spent_at", "item", "amount_inr", "category"]
    return df.sort_values("amount_inr", ascending=False).head(n)[cols]


# ------------------------------------------------------------------ LLM usage (observability)
def load_llm_calls(include_eval: bool = False) -> pd.DataFrame:
    """Every recorded model call. Evaluation runs are hidden unless asked for."""
    from core import get_conn

    with get_conn() as conn:
        try:
            df = pd.read_sql_query("SELECT * FROM llm_calls", conn)
        except Exception:  # table not created yet
            return pd.DataFrame()
    if df.empty:
        return df
    df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
    df = df.dropna(subset=["ts"]).copy()
    df["date"] = df["ts"].dt.normalize()
    return df if include_eval else df[df["purpose"] != "eval"]


def llm_summary(df: pd.DataFrame) -> dict:
    zero = {"calls": 0, "calls_today": 0, "tokens_today": 0, "success_rate": 0.0,
            "p50_ms": 0, "p95_ms": 0, "avg_tokens_per_call": 0}
    if df.empty:
        return zero
    ok = df[df["status"] == "ok"]
    today = df[df["date"] == pd.Timestamp.now().normalize()]
    return {
        "calls": int(len(df)),
        "calls_today": int(len(today)),
        "tokens_today": int(today["total_tokens"].fillna(0).sum()),
        "success_rate": round(100 * len(ok) / len(df), 1),
        "p50_ms": int(ok["latency_ms"].quantile(0.5)) if len(ok) else 0,
        "p95_ms": int(ok["latency_ms"].quantile(0.95)) if len(ok) else 0,
        "avg_tokens_per_call": int(ok["total_tokens"].fillna(0).mean()) if len(ok) else 0,
    }


def llm_daily(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame({"Calls": [], "Tokens": []}, index=pd.DatetimeIndex([], name="date"))
    return df.groupby("date").agg(Calls=("id", "size"), Tokens=("total_tokens", "sum"))

    
def credit_card_spending(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return spending totals by card and individual credit-card purchases."""
    required = {"amount_inr", "payment_method", "card_name"}

    if df.empty or not required.issubset(df.columns):
        empty_summary = pd.DataFrame(columns=["card_name", "total_spend", "transactions"])
        empty_transactions = df.iloc[0:0].copy()
        return empty_summary, empty_transactions

    # Only count purchases explicitly recorded as credit-card transactions.
    card_df = df.loc[
        df["payment_method"].eq("credit_card") & df["card_name"].notna()
    ].copy()

    if card_df.empty:
        empty_summary = pd.DataFrame(columns=["card_name", "total_spend", "transactions"])
        return empty_summary, card_df

    summary = (
        card_df.groupby("card_name", as_index=False)
        .agg(
            total_spend=("amount_inr", "sum"),
            transactions=("id", "count"),
        )
        .sort_values("total_spend", ascending=False)
        .reset_index(drop=True)
    )

    return summary, card_df.sort_values("spent_at", ascending=False)
