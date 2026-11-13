"""PIN gate for the Streamlit app. Call require_pin() before rendering anything."""
import hmac
import os
import time

import streamlit as st

MAX_FAILS = 5
LOCK_SECONDS = 15 * 60


@st.cache_resource
def _attempts() -> dict:
    """Shared by every browser session, so opening new tabs does not reset the counter."""
    return {"fails": 0, "locked_until": 0.0}


def require_pin() -> None:
    if st.session_state.get("authed"):
        return

    expected = os.environ.get("APP_PIN", "")
    st.title("Expense Tracker")
    if not (expected.isdigit() and len(expected) == 6):  # fail closed
        st.error("The server PIN is not configured.")
        st.stop()

    state = _attempts()
    now = time.time()
    if now < state["locked_until"]:
        minutes = int((state["locked_until"] - now) // 60) + 1
        st.error(f"Too many wrong attempts. Try again in about {minutes} min.")
        st.stop()

    with st.form("pin_form"):
        pin = st.text_input("Enter your 6-digit PIN", type="password", max_chars=6)
        submitted = st.form_submit_button("Unlock")

    if submitted:
        if hmac.compare_digest(pin.encode(), expected.encode()):
            state["fails"] = 0
            st.session_state["authed"] = True
            st.rerun()
        state["fails"] += 1
        if state["fails"] >= MAX_FAILS:
            state["fails"] = 0
            state["locked_until"] = now + LOCK_SECONDS
            st.error("Too many wrong attempts. Locked for 15 minutes.")
        else:
            st.error(f"Wrong PIN. {MAX_FAILS - state['fails']} attempts left.")
    st.stop()