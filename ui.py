# ruff: noqa: E501  (the CSS block below has long lines on purpose)
"""Look and feel: theme CSS and small HTML builders. No business logic or database code here.

Every piece of user text (item names, categories) goes through html.escape before it is
placed in HTML, because item names come from free-text chat messages.
"""
from datetime import date, datetime
from html import escape

import pandas as pd
import streamlit as st

GREEN = "#7CFF8A"
GREEN_SOFT = "#3fa55a"

CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

html, body, .stApp, [class*="st-"] { font-family: 'Plus Jakarta Sans', sans-serif; }
.stApp {
  background:
    radial-gradient(900px 500px at 15% -8%, rgba(34,197,94,.28), transparent 60%),
    radial-gradient(700px 480px at 100% 8%, rgba(22,163,74,.16), transparent 60%),
    #04110b;
}
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1.6rem; max-width: 1100px; }

/* ---------- page header ---------- */
.app-head { display: flex; align-items: center; gap: 14px; margin-bottom: 1.2rem; }
.app-logo {
  width: 52px; height: 52px; border-radius: 17px; display: grid; place-items: center;
  font-weight: 800; font-size: 1.05rem; color: #9dffa0;
  background: linear-gradient(145deg, #12361f, #07190f);
  border: 1px solid rgba(124,255,138,.35);
  box-shadow: 0 0 28px rgba(124,255,138,.28), inset 0 1px 0 rgba(255,255,255,.12);
}
.app-title { font-size: 1.55rem; font-weight: 800; letter-spacing: -.5px; line-height: 1.1; }
.app-sub { color: #86ad96; font-size: .85rem; margin-top: 3px; }

/* ---------- tabs as pills ---------- */
[data-baseweb="tab-list"] { gap: 8px; border-bottom: none; }
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] { display: none; }
button[data-baseweb="tab"] {
  border-radius: 999px; padding: 8px 20px; height: auto;
  background: rgba(9,32,20,.75); border: 1px solid rgba(124,255,138,.12);
}
button[data-baseweb="tab"] p { color: #bfe0cb; font-weight: 600; }
button[data-baseweb="tab"][aria-selected="true"] {
  background: linear-gradient(135deg, #9dffa0, #5fe383);
  box-shadow: 0 0 24px rgba(124,255,138,.3);
}
button[data-baseweb="tab"][aria-selected="true"] p { color: #052e16; font-weight: 800; }

/* ---------- section titles ---------- */
.section-title { font-size: 1.1rem; font-weight: 700; margin: 1.3rem 0 .7rem; letter-spacing: -.2px; }

/* ---------- hero (balance-style card) ---------- */
.hero {
  background: linear-gradient(135deg, #a8ffab 0%, #6ef08a 48%, #3ec96a 100%);
  color: #052e16; border-radius: 28px; padding: 22px 24px 20px;
  box-shadow: 0 0 70px rgba(110,240,138,.22), inset 0 1px 0 rgba(255,255,255,.5);
  margin-bottom: 1rem;
}
.hero .label { font-size: .88rem; font-weight: 600; opacity: .72; }
.hero .amt { font-size: 2.9rem; font-weight: 800; letter-spacing: -1.5px; line-height: 1.1; margin-top: 2px; }
.hero .pills { display: flex; gap: 12px; margin-top: 18px; flex-wrap: wrap; }
.hero .pill {
  background: rgba(3,16,10,.9); color: #e8fff0; border-radius: 18px;
  padding: 11px 16px; min-width: 140px; font-size: .78rem; color: #9fc4ae;
}
.hero .pill b { display: block; font-size: 1.05rem; color: #9dffa0; margin-top: 2px; }

/* ---------- glass metric cards (st.metric) ---------- */
[data-testid="stMetric"] {
  background: linear-gradient(145deg, rgba(20,64,38,.55), rgba(6,24,15,.7));
  border: 1px solid rgba(124,255,138,.14); border-radius: 22px; padding: 16px 18px;
  box-shadow: 0 10px 36px rgba(0,0,0,.4), inset 0 1px 0 rgba(255,255,255,.06);
  backdrop-filter: blur(14px);
}
[data-testid="stMetricLabel"] p { color: #8db8a0; font-weight: 600; }
[data-testid="stMetricValue"] { font-weight: 800; letter-spacing: -.5px; }

/* ---------- transaction rows ---------- */
.txn {
  display: flex; align-items: center; gap: 14px; padding: 13px 16px; margin-bottom: 10px;
  border-radius: 20px; background: rgba(8,29,18,.72);
  border: 1px solid rgba(124,255,138,.08); box-shadow: 0 6px 20px rgba(0,0,0,.28);
}
.txn .badge {
  width: 42px; height: 42px; border-radius: 14px; flex: 0 0 42px; display: grid;
  place-items: center; font-weight: 800; color: #9dffa0; background: rgba(124,255,138,.12);
  border: 1px solid rgba(124,255,138,.18);
}
.txn .t { font-weight: 700; font-size: .95rem; text-transform: capitalize; }
.txn .s { font-size: .74rem; color: #7fa890; margin-top: 2px; }
.txn .a { margin-left: auto; font-weight: 800; color: #ff6b6b; white-space: nowrap; }

/* ---------- category share bars ---------- */
.share { margin-bottom: 14px; }
.share .row { display: flex; justify-content: space-between; font-size: .85rem; margin-bottom: 6px; }
.share .row span:first-child { font-weight: 700; text-transform: capitalize; }
.share .row span:last-child { color: #8db8a0; }
.share .track { height: 10px; border-radius: 999px; background: rgba(124,255,138,.1); overflow: hidden; }
.share .fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #3ec96a, #9dffa0); }

.empty {
  text-align: center; color: #86ad96; padding: 28px 16px; border-radius: 22px;
  border: 1px dashed rgba(124,255,138,.25); background: rgba(8,29,18,.5);
}

/* ---------- period radio as pills ---------- */
div[role="radiogroup"] { gap: 8px; flex-wrap: wrap; }
div[role="radiogroup"] label {
  background: rgba(9,32,20,.75); border: 1px solid rgba(124,255,138,.14);
  border-radius: 999px; padding: 6px 16px; margin: 0; cursor: pointer;
}
div[role="radiogroup"] label > div:first-child { display: none; }
div[role="radiogroup"] label p { color: #bfe0cb; font-weight: 600; font-size: .85rem; }
div[role="radiogroup"] label:has(input:checked) {
  background: linear-gradient(135deg, #9dffa0, #5fe383); border-color: transparent;
  box-shadow: 0 0 20px rgba(124,255,138,.28);
}
div[role="radiogroup"] label:has(input:checked) p { color: #052e16; font-weight: 800; }

/* ---------- chat ---------- */
[data-testid="stChatInput"] {
  border-radius: 999px; background: rgba(8,29,18,.85);
  border: 1px solid rgba(124,255,138,.3); box-shadow: 0 0 30px rgba(124,255,138,.1);
}
[data-testid="stChatMessage"] {
  background: linear-gradient(145deg, rgba(20,64,38,.5), rgba(6,24,15,.65));
  border: 1px solid rgba(124,255,138,.12); border-radius: 22px; padding: 14px 16px;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
  background: linear-gradient(135deg, #a8ffab, #5fe383); color: #052e16;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) p { color: #052e16; font-weight: 600; }

/* ---------- buttons ---------- */
[data-testid="stDownloadButton"] button, .stButton button {
  border-radius: 999px; border: none; font-weight: 800;
  background: linear-gradient(135deg, #9dffa0, #5fe383);
}
[data-testid="stDownloadButton"] button p, .stButton button p { color: #052e16; font-weight: 800; }

@media (max-width: 640px) {
  .hero .amt { font-size: 2.3rem; }
  .block-container { padding-left: 1rem; padding-right: 1rem; }
}
</style>"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def _html(markup: str):
    # No newlines or indentation: Markdown would treat indented lines as code blocks.
    st.markdown(markup, unsafe_allow_html=True)


def page_header():
    _html('<div class="app-head"><div class="app-logo">Rs</div><div>'
          '<div class="app-title">Expense Tracker</div>'
          '<div class="app-sub">Type what you spent. It handles the rest.</div>'
          '</div></div>')


def section(title: str):
    _html(f'<div class="section-title">{escape(title)}</div>')


def empty_state(message: str):
    _html(f'<div class="empty">{escape(message)}</div>')


def hero_card(label: str, amount: str, pills: list):
    """Big gradient card (the 'Total Balance' card of the reference design)."""
    pill_html = "".join(f'<div class="pill">{escape(k)}<b>{escape(v)}</b></div>'
                        for k, v in pills)
    _html(f'<div class="hero"><div class="label">{escape(label)}</div>'
          f'<div class="amt">{escape(amount)}</div><div class="pills">{pill_html}</div></div>')


def _when_text(value) -> str:
    try:
        when = datetime.strptime(str(value)[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        return str(value)
    days = (date.today() - when.date()).days
    day = "Today" if days == 0 else "Yesterday" if days == 1 else when.strftime("%d %b")
    return f"{day}, {when.strftime('%H:%M')}"


def txn_rows(rows: list):
    """rows: dicts with title, sub, amount (float) and optional badge letter."""
    if not rows:
        return
    parts = []
    for r in rows:
        badge = escape((r.get("badge") or r["title"][:1] or "?")[:1].upper())
        parts.append(
            f'<div class="txn"><div class="badge">{badge}</div><div>'
            f'<div class="t">{escape(str(r["title"]))}</div>'
            f'<div class="s">{escape(str(r["sub"]))}</div></div>'
            f'<div class="a">-Rs {float(r["amount"]):,.0f}</div></div>')
    _html("".join(parts))


def expense_list(df: pd.DataFrame):
    """Rows of the expenses table (spent_at, item, amount_inr, category)."""
    txn_rows([{"title": r["item"], "badge": r["category"],
               "sub": f'{r["category"]} - {_when_text(r["spent_at"])}',
               "amount": r["amount_inr"]} for r in df.to_dict("records")])


def share_bars(df: pd.DataFrame):
    """Category breakdown (columns: category, total, purchases, share_pct)."""
    parts = []
    for r in df.to_dict("records"):
        pct = max(0.0, min(100.0, float(r["share_pct"])))
        parts.append(
            f'<div class="share"><div class="row"><span>{escape(str(r["category"]))}</span>'
            f'<span>Rs {float(r["total"]):,.0f} - {pct:.0f}%</span></div>'
            f'<div class="track"><div class="fill" style="width:{pct:.1f}%"></div></div></div>')
    _html("".join(parts))