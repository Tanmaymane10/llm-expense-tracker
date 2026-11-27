"""Display-only HTML for the Home and Analytics cards. Pure functions, no Streamlit.

SECURITY: every value that comes from data (item, card name, category, payment label, raw text)
goes through e() before it is put in HTML. Item names come from the user and from the model.
"""
import html
from datetime import date, timedelta
from urllib.parse import quote

from core import inr

ACCENT, WARN, WARN_INK, DANGER, DANGER_INK = "#C8F25A", "#F5B84B", "#F7C873", "#FF7A7A", "#FF9A9A"
MUTED, TRACK, CREDIT = "#8C97A6", "#232A33", "#9BE88A"
GROUP_COLORS = {"day-to-day": ACCENT, "fixed": "#4A5566", "family": "#6FB7F2",
                "invested": "#8B7CF6"}
GROUP_LABELS = {"day-to-day": "Day-to-day", "fixed": "Fixed", "family": "Family",
                "invested": "Invested"}
STATUS = {"on track": ("On track", ACCENT), "near limit": ("Near limit", WARN),
          "over limit": ("Over limit", DANGER)}
# category tile: (background tint, ink)
TINTS = {"food": ("#1F2A1A", ACCENT), "groceries": ("#1F2A1A", ACCENT),
         "transport": ("#1D2A3A", "#6FB7F2"), "family": ("#1D2A3A", "#6FB7F2"),
         "shopping": ("#2D2616", WARN_INK), "bills": ("#232A33", "#C3CCD8"),
         "health": ("#2E1C22", DANGER_INK), "investment": ("#2A2140", "#B3A6FF"),
         "entertainment": ("#2A2140", "#B3A6FF")}
CARD_ART = {  # by lower-cased card name; never the lime accent
    "sbi cashback": "linear-gradient(135deg, #7B5CD6, #4A3590)",
    "swiggy hdfc": "linear-gradient(135deg, #F08A3C, #2F6FD0)",
    "hdfc moneyback": "linear-gradient(135deg, #8CC8F5, #4E97D6)",
    "slice": "linear-gradient(135deg, #F07FB4, #B8487F)",
    "slice upi": "linear-gradient(135deg, #F07FB4, #B8487F)",  # the name the seed data stores
}
CARD_ART_OTHER = "linear-gradient(135deg, #3A4352, #1F252E)"
CARD = "background:#151A21;border:1px solid #232A33;border-radius:24px"
WARN_SVG = ('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            '<path d="M12 9v4M12 17h.01"></path><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 '
            '2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"></path></svg>')
FONT = "font-family:Inter,system-ui,sans-serif;color:#EEF2F6"


def e(value) -> str:
    return html.escape(str(value), quote=True)


def money(x) -> str:
    return e(inr(x))


def pct(part, whole) -> float:
    """Bar width in %, 0..100."""
    return max(0.0, min(100.0, 100 * part / whole)) if whole else 0.0


def _k(x: float) -> str:
    return f"₹{x / 1000:g}k" if x % 100 == 0 and x >= 1000 else inr(x)


def clock(t) -> str:
    return f"{(t.hour % 12) or 12}:{t.minute:02d} {'am' if t.hour < 12 else 'pm'}"


# ---- PIN gate (docs/design/login-phone.dc.html, login-desktop.dc.html). No data in any of it.
_LOGIN_DEFS = (
    '<linearGradient id="g1" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#C8F25A" '
    'stop-opacity="0"/><stop offset="0.45" stop-color="#C8F25A"/><stop offset="1" '
    'stop-color="#2FD6B5"/></linearGradient>'
    '<linearGradient id="g2" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#2FD6B5" '
    'stop-opacity="0"/><stop offset="0.5" stop-color="#6FB7F2"/><stop offset="1" '
    'stop-color="#4C7DFF" stop-opacity="0.2"/></linearGradient>'
    '<linearGradient id="g3" x1="1" y1="0" x2="0" y2="0"><stop offset="0" stop-color="#4C7DFF" '
    'stop-opacity="0.1"/><stop offset="0.5" stop-color="#6FB7F2"/><stop offset="1" '
    'stop-color="#8B7CF6" stop-opacity="0"/></linearGradient>')


def _login_art(w, h, soft, glow, blobs, paths) -> str:
    """The light-streak background as an SVG data URI. paths: (d, gradient, width, opacity,
    glow?)."""
    circles = "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}" opacity="{o}" '
                      'filter="url(#soft)"/>' for x, y, r, c, o in blobs)
    strokes = "".join(f'<path d="{d}" stroke="url(#{g})" stroke-width="{sw}" opacity="{o}"'
                      + (' filter="url(#glow)"' if gl else "") + "/>"
                      for d, g, sw, o, gl in paths)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
           'preserveAspectRatio="xMidYMid slice"><defs>'
           '<filter id="soft" x="-50%" y="-50%" width="200%" height="200%">'
           f'<feGaussianBlur stdDeviation="{soft}"/></filter>'
           '<filter id="glow" x="-20%" y="-20%" width="140%" height="140%">'
           f'<feGaussianBlur stdDeviation="{glow}"/></filter>{_LOGIN_DEFS}</defs>{circles}'
           f'<g fill="none" stroke-linecap="round">{strokes}</g></svg>')
    return "data:image/svg+xml," + quote(svg)


_ART_PHONE = _login_art(390, 844, 38, 7, [
    (40, 720, 150, "#C8F25A", 0.22), (370, 150, 170, "#4C7DFF", 0.30),
    (320, 800, 130, "#8B7CF6", 0.22), (20, 210, 110, "#2FD6B5", 0.16)], [
    ("M -60 640 C 80 530, 210 720, 470 380", "g1", 18, 0.45, True),
    ("M -60 640 C 80 530, 210 720, 470 380", "g1", 4, 1, False),
    ("M -40 712 C 120 610, 270 770, 470 500", "g2", 2, 1, False),
    ("M 460 110 C 300 220, 250 30, -40 250", "g3", 22, 0.4, True),
    ("M 460 110 C 300 220, 250 30, -40 250", "g3", 5, 1, False),
    ("M 470 196 C 320 300, 230 150, -30 330", "g2", 1.5, 0.8, False),
    ("M 110 920 C 180 770, 330 830, 430 640", "g1", 26, 0.18, True)])
_ART_DESKTOP = _login_art(1280, 800, 70, 10, [
    (180, 650, 270, "#C8F25A", 0.18), (1100, 150, 300, "#4C7DFF", 0.28),
    (1000, 720, 230, "#8B7CF6", 0.20), (140, 150, 190, "#2FD6B5", 0.14)], [
    ("M -100 610 C 300 470, 620 780, 1380 290", "g1", 26, 0.4, True),
    ("M -100 610 C 300 470, 620 780, 1380 290", "g1", 5, 1, False),
    ("M -80 690 C 360 560, 700 830, 1400 420", "g2", 2, 1, False),
    ("M 1380 70 C 900 230, 700 -10, -100 250", "g3", 30, 0.36, True),
    ("M 1380 70 C 900 230, 700 -10, -100 250", "g3", 6, 1, False),
    ("M 1380 170 C 960 300, 640 120, -80 340", "g2", 1.5, 0.8, False),
    ("M 200 900 C 500 690, 1000 830, 1320 590", "g1", 34, 0.16, True)])

# Only rendered by the PIN gate, so none of it ships after login. Everything is scoped to
# .st-key-pin_gate (the card) or to the page while it holds the card.
PIN_CSS = """<style>
/* the art is the app background: decorative, never focusable or clickable, covers the viewport */
.stApp:has(.st-key-pin_gate) {
  background: radial-gradient(ellipse at 50% 50%, rgba(7,9,13,0.15) 0%, rgba(7,9,13,0.65) 75%),
    url("ART_PHONE") center / cover no-repeat, #07090D;
}
[data-testid="stMainBlockContainer"]:has(.st-key-pin_gate) {
  min-height: 100vh;
  min-height: 100dvh;
  box-sizing: border-box;
  padding: 24px 16px !important;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
/* zero-height siblings (style, script) must not add flex gaps that push the card off center */
[data-testid="stMainBlockContainer"]:has(.st-key-pin_gate) > [data-testid="stVerticalBlock"] {
  gap: 0;
  justify-content: center;  /* this block grows to the full height, so center inside it */
}
.st-key-pin_gate {
  width: 100%;
  max-width: 342px;
  margin: 0 auto;
  box-sizing: border-box;
  padding: 28px 24px 24px;
  gap: 22px;
  border-radius: 28px;
  background: rgba(21,26,33,0.58);
  border: 1px solid rgba(255,255,255,0.12);
  -webkit-backdrop-filter: blur(24px) saturate(140%);
  backdrop-filter: blur(24px) saturate(140%);
  box-shadow: 0 30px 80px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.08);
}
.st-key-pin_gate h1 {
  margin: 0; padding: 0 !important; font-size: 32px !important; font-weight: 700 !important;
  letter-spacing: -0.02em; line-height: 1.1;
}
.st-key-pin_gate [data-testid="stForm"] {
  background: transparent; border: 0; border-radius: 0; padding: 0;
}
.st-key-pin_gate [data-testid="stForm"] [data-testid="stVerticalBlock"] { gap: 8px; }
.st-key-pin_gate [data-testid="stWidgetLabel"] p { font-size: 13px; color: #A9B3C1; }
.st-key-pin_gate [data-testid="InputInstructions"] { display: none; }
.st-key-pin_gate [data-testid="stTextInputRootElement"] {
  height: 56px;
  border-radius: 16px !important;
  background: rgba(11,14,19,0.6) !important;
  border: 1px solid rgba(255,255,255,0.14) !important;
  padding-right: 6px;
}
.st-key-pin_gate [data-testid="stTextInputRootElement"]:focus-within {
  border-color: rgba(200,242,90,0.55) !important;
  box-shadow: 0 0 0 4px rgba(200,242,90,0.10);
}
.st-key-pin_gate input {
  padding-left: 18px; color: #EEF2F6; font-size: 22px; letter-spacing: 0.5em;
}
.st-key-pin_gate .stFormSubmitButton { margin-top: 14px; }
.st-key-pin_gate [data-testid="stBaseButton-primaryFormSubmit"] {
  min-height: 54px;
  border-radius: 16px;
  font-size: 16px;
  font-weight: 700;
  box-shadow: 0 10px 30px rgba(200,242,90,0.22);
}
.st-key-pin_gate [data-testid="stBaseButton-primaryFormSubmit"] p {
  font-size: 16px; font-weight: 700;
}
@media (min-width: 641px) {
  .stApp:has(.st-key-pin_gate) {
    background: radial-gradient(ellipse at 50% 50%, rgba(7,9,13,0.2) 0%, rgba(7,9,13,0.7) 70%),
      url("ART_DESKTOP") center / cover no-repeat, #07090D;
  }
  .st-key-pin_gate { max-width: 400px; padding: 34px 32px 28px; gap: 24px; }
  .st-key-pin_gate h1 { font-size: 34px !important; }
}
</style>""".replace("ART_PHONE", _ART_PHONE).replace("ART_DESKTOP", _ART_DESKTOP)

# phones: digit keypad and a "Go" key. Streamlit has no API for these attributes.
PIN_KEYPAD_JS = """<script>
(() => {
  let tries = 0;
  const set = () => {
    const i = document.querySelector(".st-key-pin_gate input");
    if (!i) return ++tries < 100 && requestAnimationFrame(set);
    i.setAttribute("inputmode", "numeric");
    i.setAttribute("enterkeyhint", "go");
  };
  set();
})();
</script>"""


def pin_head() -> str:
    """Q tile + wordmark, then the greeting."""
    return (f'<div style="display:flex;flex-direction:column;gap:22px;{FONT}">'
            '<div style="display:flex;align-items:center;gap:10px">'
            '<div style="width:40px;height:40px;border-radius:12px;background:#C8F25A;'
            'color:#0B0E13;display:flex;align-items:center;justify-content:center;'
            'font-weight:800;font-size:19px">Q</div><span style="font-size:16px;'
            'font-weight:700;letter-spacing:0.12em">QORVIAN</span></div>'
            '<div style="display:flex;flex-direction:column;gap:6px">'
            '<h1 style="color:#E2FF8F">Welcome back</h1>'
            '<p style="margin:0;font-size:14px;color:#A9B3C1;line-height:1.45">'
            'Enter your PIN to open your expenses.</p></div></div>')


def _icon(shapes: str, color: str) -> str:
    """14px line icon. st.html strips inline <svg>, so it goes in as an image."""
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
           f'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
           f'{shapes}</svg>')
    return f'<img src="data:image/svg+xml,{quote(svg)}" width="14" height="14" alt="">'


def pin_error(message: str) -> str:
    """The red line under the PIN field."""
    return ('<p role="alert" style="margin:0;font-family:Inter,system-ui,sans-serif;'
            f'font-size:13px;color:{DANGER_INK};display:flex;align-items:center;gap:6px">'
            + _icon('<circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/>', DANGER_INK)
            + f'{e(message)}</p>')


def pin_footer() -> str:
    return ('<div style="display:flex;align-items:center;gap:8px;font-family:Inter,system-ui,'
            f'sans-serif;font-size:12px;color:{MUTED};border-top:1px solid '
            'rgba(255,255,255,0.08);padding-top:16px">'
            + _icon('<rect x="4" y="11" width="16" height="10" rx="2"/>'
                    '<path d="M8 11V7a4 4 0 0 1 8 0v4"/>', MUTED)
            + '<span>Private to you. Locks again when you close the app.</span></div>')


def header(today: date) -> str:
    return (f'<div style="display:flex;align-items:center;gap:10px;{FONT}">'
            '<div style="width:34px;height:34px;border-radius:11px;background:#C8F25A;'
            'color:#0B0E13;display:flex;align-items:center;justify-content:center;'
            'font-weight:800;font-size:17px">Q</div><div style="display:flex;'
            f'flex-direction:column"><span style="font-size:12px;color:{MUTED}">'
            f'{today:%A}, {today.day} {today:%b}</span><span style="font-size:17px;'
            'font-weight:700;letter-spacing:0.08em">QORVIAN</span></div></div>')


def _tile(label, value, color="#EEF2F6") -> str:
    return ('<div style="background:#1C222B;border-radius:14px;padding:10px 12px;display:flex;'
            f'flex-direction:column;gap:2px;min-width:0"><span style="font-size:11px;'
            f'color:{MUTED}">{e(label)}</span><span class="num" style="font-size:16px;'
            f'font-weight:600;color:{color};font-variant-numeric:tabular-nums">{e(value)}'
            '</span></div>')


def _alert_row(text_html: str, over: bool) -> str:
    fill, ink = (DANGER, DANGER_INK) if over else (WARN, WARN_INK)
    rgb = "255,122,122" if over else "245,184,75"
    return (f'<div style="display:flex;align-items:center;gap:8px;background:rgba({rgb},0.12);'
            f'border:1px solid rgba({rgb},0.35);border-radius:12px;padding:9px 12px;'
            f'font-size:13px;color:{ink}" data-fill="{fill}">{WARN_SVG}<span>{text_html}'
            '</span></div>')


def hero(fig: dict, today: date) -> str:
    """Day-to-day card: badge, total, bar with target/limit markers, 3 tiles, category alerts."""
    label, badge = STATUS[fig["status"]]
    target, limit, spent = fig["target"], fig["limit"], fig["d2d"]
    scale = limit * 8 / 7  # the mockup's 0..8000 for a 7000 limit
    bar = {"on track": ACCENT, "near limit": WARN, "over limit": DANGER}[fig["status"]]
    t, lim = pct(target, scale), pct(limit, scale)
    pace = fig["pace"]
    pace_ink = DANGER_INK if pace > limit else WARN_INK if pace >= target else "#EEF2F6"
    left = (("Left to limit", inr(fig["left"])) if fig["left"] >= 0
            else ("Over limit by", inr(-fig["left"])))
    alerts = "".join(
        _alert_row(f'{e(b["category"].capitalize())} is at <b class="num">{money(b["spent"])}'
                   f'</b> of {money(b["budget"])} ({b["pct"]:.0f}%)', b["pct"] > 100)
        for b in fig["near"])
    return (
        f'<section aria-label="This month" style="position:relative;padding-top:10px;{FONT}">'
        '<div style="position:absolute;top:0;left:22px;right:22px;height:22px;'
        'border-radius:14px 14px 0 0;background:#C8F25A"></div>'
        f'<div style="position:relative;{CARD};padding:20px;display:flex;flex-direction:column;'
        'gap:14px"><div style="display:flex;justify-content:space-between;align-items:center">'
        f'<span style="font-size:13px;color:{MUTED}">{today:%B} · day-to-day</span>'
        '<span style="font-size:12px;font-weight:600;color:#0B0E13;'
        f'background:{badge};border-radius:999px;padding:4px 10px">{label}</span></div>'
        '<div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap">'
        '<span class="num" style="font-size:44px;font-weight:700;letter-spacing:-0.02em;'
        f'font-variant-numeric:tabular-nums">{money(spent)}</span>'
        f'<span style="font-size:13px;color:{MUTED}">of {money(target)}–{money(limit)}</span>'
        '</div><div style="display:flex;flex-direction:column;gap:6px">'
        '<div role="img" aria-label="Day-to-day spending against the target and limit" '
        f'style="position:relative;height:12px;border-radius:999px;background:{TRACK}">'
        f'<div style="position:absolute;left:0;top:0;bottom:0;width:{pct(spent, scale):.1f}%;'
        f'border-radius:999px;background:{bar}"></div>'
        f'<div style="position:absolute;left:{t:.1f}%;top:-4px;bottom:-4px;width:2px;'
        'background:#EEF2F6;opacity:0.55"></div>'
        f'<div style="position:absolute;left:{lim:.1f}%;top:-4px;bottom:-4px;width:2px;'
        f'background:{DANGER}"></div></div>'
        f'<div style="position:relative;height:14px;font-size:11px;color:{MUTED}">'
        f'<span style="position:absolute;left:{t:.1f}%;transform:translateX(-50%);'
        f'white-space:nowrap">{e(_k(target))} target</span>'
        f'<span style="position:absolute;left:{lim:.1f}%;transform:translateX(-50%);'
        f'white-space:nowrap;color:{DANGER_INK}">{e(_k(limit))} limit</span></div></div>'
        '<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px">'
        f'{_tile("Today", inr(fig["today"]))}{_tile("Month-end pace", inr(round(pace)), pace_ink)}'
        f'{_tile(*left)}</div>{alerts}</div></section>')


def total_out(fig: dict) -> str:
    groups = fig["groups"]
    whole = sum(max(v, 0) for v in groups.values())
    bar = "".join(f'<div style="width:{pct(max(v, 0), whole):.1f}%;background:{GROUP_COLORS[g]}">'
                  '</div>' for g, v in groups.items() if v > 0)
    legend = "".join(
        f'<div style="display:flex;align-items:center;gap:8px"><span style="width:9px;'
        f'height:9px;border-radius:3px;background:{GROUP_COLORS[g]};flex-shrink:0"></span>'
        f'<span style="color:{MUTED};flex-grow:1">{GROUP_LABELS[g]}</span>'
        f'<span class="num">{money(v)}</span></div>' for g, v in groups.items())
    return (f'<section aria-label="Total money out" style="{CARD};padding:18px 20px;display:flex;'
            f'flex-direction:column;gap:12px;{FONT}"><div style="display:flex;'
            'justify-content:space-between;align-items:baseline">'
            f'<span style="font-size:13px;color:{MUTED}">Total out this month</span>'
            '<span class="num" style="font-size:22px;font-weight:700">'
            f'{money(fig["total_out"])}</span></div>'
            '<div style="display:flex;height:10px;border-radius:999px;overflow:hidden;gap:2px;'
            f'background:{TRACK}">{bar}</div>'
            '<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));'
            f'gap:8px 14px;font-size:13px">{legend}</div></section>')


def due_text(days):
    """(text, color, weight) for a card's next due date."""
    if days is None:
        return "", MUTED, 400
    if days < 0:
        return f"Overdue {-days} day{'s' if days < -1 else ''}", DANGER_INK, 600
    if days == 0:
        return "Due today", WARN_INK, 600
    return f"Due in {days} day{'s' if days > 1 else ''}", WARN_INK if days <= 5 else MUTED, \
        600 if days <= 5 else 400


def card_art(name: str) -> str:
    return CARD_ART.get((name or "").strip().lower(), CARD_ART_OTHER)


def has_dates(c: dict) -> bool:
    """A statement day is enough: without a due day the bill is paid by month-end."""
    return bool(c["statement_day"])


def bill_upcoming(c: dict) -> bool:
    """Spend this cycle, or a closed bill still unpaid."""
    return bool(c["spent_cycle"]) or (c["paid"] is False and bool(c["amount_due"]))


def sort_cards(rows: list) -> list:
    """Soonest due first (no bill = last), then spend this cycle high to low, then name."""
    def key(c):
        due = c["days_to_due"] if bill_upcoming(c) and c["days_to_due"] is not None else 10**6
        return due, -(c["spent_cycle"] or 0), (c["card"] or "").lower()
    return sorted(rows, key=key)


def card_row(c: dict) -> str:
    """One Home card row: name and due countdown, a bar of statement due + unbilled against
    the limit, then the two figures. A card without a statement day leaves the due slot to
    the app's "Set billing dates in Plan" button."""
    quiet = not bill_upcoming(c)
    if not has_dates(c):
        text, color, weight = "", MUTED, 400
    elif quiet:
        text, color, weight = "No bill due", MUTED, 400
    else:
        text, color, weight = due_text(c["days_to_due"])
    if c["limit"]:
        used = c["utilisation"] or 0.0  # unbilled plus any unpaid statement
        caption = f"of {money(c['limit'])} limit"
        bar = (f'<div style="height:5px;border-radius:999px;background:{TRACK}"><div '
               f'style="height:5px;border-radius:999px;width:{min(used, 100):.1f}%;'
               f'background:{DANGER if used > 100 else WARN if used >= 80 else ACCENT}">'
               '</div></div>')
    else:
        caption, bar = "no limit set", ""
    lines = ""
    if c["paid"] is False and c["amount_due"]:
        lines += (f'<div class="num" style="font-size:13px;font-weight:600">Statement due '
                  f'{money(c["amount_due"])} · pay by {c["due_date"].day} '
                  f'{c["due_date"]:%b}</div>')
    unbilled = ""
    if has_dates(c):
        bill_day = c["prev_end"] + timedelta(days=1)  # the current cycle's first day
        unbilled = f'Unbilled {money(c["spent_cycle"])} since {bill_day.day} {bill_day:%b}'
    ink = f"color:{MUTED};" if quiet else ""
    return (
        '<div style="display:flex;align-items:center;gap:12px;background:#151A21;'
        f'border:1px solid #232A33;border-radius:18px;padding:12px 14px;{FONT}">'
        f'<div style="width:46px;height:30px;border-radius:6px;'
        f'background:{card_art(c["card"])};position:relative;flex-shrink:0">'
        '<span style="position:absolute;left:6px;bottom:5px;width:9px;height:6px;'
        'border-radius:2px;background:rgba(11,14,19,0.45)"></span></div>'
        '<div style="flex-grow:1;min-width:0;display:flex;flex-direction:column;gap:6px">'
        '<div style="display:flex;justify-content:space-between;gap:8px;min-height:20px">'
        '<span style="font-size:14px;font-weight:600;overflow:hidden;text-overflow:ellipsis;'
        f'white-space:nowrap;{ink}">{e(c["card"])}</span>'
        f'<span style="font-size:12px;color:{color};font-weight:{weight};white-space:nowrap">'
        f'{text}</span></div>{bar}{lines}'
        '<div style="display:flex;justify-content:space-between;gap:8px;font-size:12px">'
        f'<span class="num" style="{ink}">{unbilled}</span>'
        f'<span style="color:{MUTED};white-space:nowrap">{caption}</span>'
        '</div></div></div>')


def non_card_row(amount: float) -> str:
    return ('<div style="display:flex;justify-content:space-between;align-items:center;'
            'background:#151A21;border:1px solid #232A33;border-radius:18px;'
            f'padding:12px 14px;font-size:14px;{FONT}"><span style="color:{MUTED}">Non-card '
            'spending this month</span><span class="num" style="font-weight:600">'
            f'{money(amount)}</span></div>')


def day_label(d: date, today: date) -> str:
    if d == today:
        return "Today"
    short = f"{d:%a} {d.day} {d:%b}"
    return f"Yesterday · {short}" if d == today - timedelta(days=1) else short


def recent(df, today: date) -> str:
    """Rows of the cached 'recent' read (newest first), grouped by day."""
    if df.empty:
        return (f'<div style="{FONT};color:{MUTED};font-size:14px;padding:8px 4px">'
                'No expenses yet. Add one with Quick add.</div>')
    df = df.dropna(subset=["spent_at"]).sort_values("spent_at", ascending=False)
    days = []
    for d, rows in df.groupby(df["spent_at"].dt.date, sort=False):
        items = []
        for n, r in enumerate(rows.itertuples()):
            ink_bg, ink = TINTS.get(r.category, ("#2A2140", "#B3A6FF"))
            meta = " · ".join(str(x) for x in ("auto" if r.auto else clock(r.spent_at),
                                                r.payment, r.category) if x)
            refund = r.amount_inr < 0
            amt = f"+{inr(-r.amount_inr)}" if refund else inr(r.amount_inr)
            sep = "0" if n == len(rows) - 1 else f"1px solid {TRACK}"
            items.append(
                f'<div style="display:flex;align-items:center;gap:12px;padding:10px 0;'
                f'border-bottom:{sep}"><div aria-hidden="true" style="width:38px;height:38px;'
                f'border-radius:12px;background:{ink_bg};color:{ink};display:flex;'
                'align-items:center;justify-content:center;font-size:13px;font-weight:700;'
                f'flex-shrink:0">{e(str(r.item)[:2].capitalize())}</div>'
                '<div style="flex-grow:1;min-width:0;display:flex;flex-direction:column;gap:2px">'
                '<span style="font-size:14px;font-weight:500;overflow-wrap:anywhere">'
                f'{e(r.item)}</span><span style="font-size:12px;color:{MUTED}">{e(meta)}</span>'
                '</div><span class="num" style="font-size:14px;font-weight:600;white-space:nowrap;'
                f'color:{CREDIT if refund else "#EEF2F6"}">{e(amt)}</span></div>')
        days.append(
            '<div style="display:flex;flex-direction:column;gap:6px">'
            f'<div style="display:flex;justify-content:space-between;font-size:12px;'
            f'color:{MUTED};padding:4px 4px 0"><span>{e(day_label(d, today))}</span>'
            f'<span class="num">{money(rows["amount_inr"].sum())}</span></div>'
            '<div style="background:#151A21;border:1px solid #232A33;border-radius:18px;'
            f'padding:4px 14px">{"".join(items)}</div></div>')
    return (f'<div style="display:flex;flex-direction:column;gap:10px;{FONT}">'
            + "".join(days) + "</div>")


def span_label(start: date, end: date) -> str:
    if (start.year, start.month) == (end.year, end.month):
        return f"{start.day}–{end.day} {end:%b}"
    return f"{start.day} {start:%b} – {end.day} {end:%b}"


def daily_head(total: float, prev: float, prev_label: str, start: date, end: date) -> str:
    diff = total - prev
    ink = DANGER_INK if diff > 0 else CREDIT
    change = (f'<span class="num" style="font-size:13px;color:{ink}">'
              f'{"▲" if diff > 0 else "▼"} {money(abs(diff))} vs {e(prev_label)}</span>'
              if prev else "")
    return (f'<div style="display:flex;flex-direction:column;gap:6px;{FONT}">'
            f'<span style="font-size:13px;color:{MUTED}">Day-to-day, '
            f'{span_label(start, end)}</span>'
            '<div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap">'
            f'<span class="num" style="font-size:32px;font-weight:700">{money(total)}</span>'
            f'{change}</div></div>')


def daily_foot(start: date, end: date, biggest) -> str:
    """biggest: (date, amount) or None."""
    mid = f"Biggest day: {biggest[0]:%a} {biggest[0].day}, {inr(biggest[1])}" if biggest else ""
    return (f'<div style="display:flex;justify-content:space-between;gap:8px;font-size:11px;'
            f'color:{MUTED};{FONT.split(";")[0]}"><span>{start.day} {start:%b}</span>'
            f'<span>{e(mid)}</span><span>{end.day} {end:%b}</span></div>')


def bars(title: str, note: str, rows: list, footer: str = "") -> str:
    """rows: dicts with name, spent, of (text), pct (0..100 bar width), state ok/near/over."""
    color = {"ok": ACCENT, "near": WARN, "over": DANGER}
    items = "".join(
        '<div style="display:flex;flex-direction:column;gap:6px">'
        '<div style="display:flex;justify-content:space-between;gap:8px;font-size:14px">'
        f'<span style="font-weight:500">{e(r["name"])}</span><span class="num"><b style="color:'
        f'{DANGER_INK if r["state"] == "over" else "#EEF2F6"}">{money(r["spent"])}</b> '
        f'<span style="color:{MUTED}">{e(r["of"])}</span></span></div>'
        f'<div style="height:8px;border-radius:999px;background:{TRACK}"><div style="height:8px;'
        f'border-radius:999px;width:{max(0, min(r["pct"], 100)):.1f}%;'
        f'background:{color[r["state"]]}"></div></div></div>' for r in rows)
    foot = (f'<div style="font-size:13px;color:{MUTED};border-top:1px solid {TRACK};'
            f'padding-top:10px">{footer}</div>' if footer else "")
    return (f'<section aria-label="{e(title)}" style="{CARD};padding:18px;display:flex;'
            f'flex-direction:column;gap:14px;{FONT}"><div style="display:flex;'
            'justify-content:space-between;align-items:center"><h2 style="margin:0;'
            f'font-size:17px;font-weight:600">{e(title)}</h2><span style="font-size:12px;'
            f'color:{MUTED}">{e(note)}</span></div>{items}{foot}</section>')


PAY_COLORS = [ACCENT, "#6FB7F2", "#8B7CF6", "#4A5566", WARN, "#B3A6FF", "#C3CCD8"]


def by_payment(rows: list) -> str:
    """rows: (label, amount, share %) sorted by amount."""
    items = "".join(
        '<div style="display:flex;align-items:center;gap:10px;font-size:14px">'
        f'<span style="width:10px;height:10px;border-radius:3px;flex-shrink:0;'
        f'background:{PAY_COLORS[i % len(PAY_COLORS)]}"></span>'
        f'<span style="flex-grow:1;min-width:0;overflow-wrap:anywhere">{e(name)}</span>'
        f'<span class="num" style="color:{MUTED};font-size:12px">{share:.0f}%</span>'
        f'<span class="num" style="font-weight:600;min-width:64px;text-align:right">'
        f'{money(amount)}</span></div>' for i, (name, amount, share) in enumerate(rows))
    return (f'<section aria-label="By payment method" style="{CARD};padding:18px;display:flex;'
            f'flex-direction:column;gap:12px;{FONT}"><h2 style="margin:0;font-size:17px;'
            f'font-weight:600">By payment method</h2>{items}</section>')
