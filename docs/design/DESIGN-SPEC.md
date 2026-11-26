# QORVIAN mobile redesign: design spec

Source of truth for the look: the three mockups in this folder
(`home.dc.html`, `quick-add.dc.html`, `analytics.dc.html`). They are design
mockups, not app code: all styling is inline CSS, and the `<sc-for>` /
`{{...}}` / `renderVals()` parts are only the mockup's templating. Read them for
layout, spacing, colors and copy. All numbers in them are sample data.

## Tokens

| Token | Value | Use |
|---|---|---|
| bg | `#0B0E13` | page background |
| surface | `#151A21` | cards, nav, sheets |
| surface-2 | `#1C222B` | stat tiles, unselected pills |
| inset | `#0F1318` | input wells inside a surface |
| border | `#232A33` (cards), `#2A323D` (pills, inputs) | 1px borders |
| track | `#232A33` | empty part of every progress bar |
| text | `#EEF2F6` | primary text |
| muted | `#8C97A6` | labels, meta lines (passes 4.5:1 on surface) |
| accent | `#C8F25A` | the ONLY accent: tappable things, "on track", selected pills, primary buttons (text on it: `#0B0E13`) |
| warn | `#F5B84B` (fill), `#F7C873` (text) | near limit, due soon |
| danger | `#FF7A7A` (fill), `#FF9A9A` (text) | over limit / over budget |
| credit | `#9BE88A` | refunds (+₹) |
| split colors | day-to-day `#C8F25A`, fixed `#4A5566`, family `#6FB7F2`, invested `#8B7CF6` | total-out bar and legend |

- Font: Inter (400–800), `font-variant-numeric: tabular-nums` on every amount.
- Radius: 24px big cards, 18px list cards and inputs, 14px stat tiles, 999px pills.
- Spacing: 20px page side padding, 22px between home sections, 14–20px card padding.
- Touch targets at least 44px (pills 36–40px tall are fine inside a row with gaps).
- No emoji anywhere. Icons are simple 2px-stroke line icons.

## Status colors (used on every budget bar)

- Day-to-day bar, scale 0 to ₹8,000, markers at ₹5,000 (target, light) and ₹7,000 (limit, red):
  under 5,000 = accent, 5,000–7,000 = warn, over 7,000 = danger.
- Category bars: under 80% = accent, 80–100% = warn, over 100% = danger (bar capped at full width).
- Badge on the hero card: "On track" (accent), "Near limit" (warn), "Over limit" (danger), dark text on all three.

## Screens

### Home (top to bottom)
1. Header: Q logo tile, date + QORVIAN wordmark, lock button (re-locks the PIN gate).
2. Hero card (lime tab peeking above it): "<Month> · day-to-day", status badge, big total,
   "of ₹5,000–7,000", bar with target/limit markers, three tiles (Today, Month-end pace,
   Left to limit), then a warning row per category at 80%+ of its budget (hidden when none).
3. Total out card: month total, 4-part split bar, 2x2 legend (Day-to-day, Fixed, Family, Invested).
4. Cards: one row per credit card with activity this billing cycle or a due date within 7 days:
   mini card tile, name, spent this cycle, thin bar vs limit, "of ₹X limit", due text
   (warn color within 5 days). Then one "UPI & cash this month" row.
5. Quick add: frequent-item pills + dashed "+ Other" pill, then the chat input with a lime send button.
6. Recent: grouped by day ("Today", "Yesterday · Wed 25 Nov", "Sun 22 Nov"), day total on the right,
   rows with a 2-letter category tile, item, "time · payment · category", amount (refunds in credit green with +).
   "View all" opens the full editable list.
7. Bottom nav (fixed): Home, Analytics, raised lime "+" (opens quick add), Plan, Usage.

### Quick add (sheet / dialog)
Item field, big ₹ amount, "Last time: ..." hint, Category pills, Paid with pills (built from real
payment methods and cards), Time row ("Now · 8:14 pm", tap to pick), "Counts toward day-to-day
budget" switch, full-width lime "Save ₹<amount>" button.

### Analytics
Title, 4-way period control (Month / 30 days / 90 days / Custom), daily-spend card (total, change vs
same days last month, lime line + soft fill + dashed grey 7-day average, biggest day caption),
two tiles (average per day, weekend vs weekday per day), "Where it went" category bars vs budget,
"By payment method" list with share %.
