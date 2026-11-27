"""PIN gate for the Streamlit app. Call require_pin() before rendering anything."""
import hmac
import os
import time

import streamlit as st

import ui

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
    st.html(ui.PIN_CSS)  # style-only: Streamlit puts it in the event container, no layout space
    with st.container(key="pin_gate"):  # the glass card; PIN_CSS centers it
        st.html(ui.pin_head())  # static: no data in it
        if not (expected.isdigit() and len(expected) == 6):  # fail closed
            st.error("The server PIN is not configured.")
            st.stop()

        state = _attempts()
        now = time.time()
        if now < state["locked_until"]:
            minutes = int((state["locked_until"] - now) // 60) + 1
            st.html(ui.pin_error(f"Too many wrong attempts. Try again in about {minutes} min."))
            st.stop()

        with st.form("pin_form", border=False):  # a form, so Enter submits
            pin = st.text_input("6-digit PIN", type="password", max_chars=6,
                                placeholder="••••••")
            alert = st.empty()  # the wrong-PIN line sits between the field and the button
            submitted = st.form_submit_button("Unlock", type="primary", width="stretch",
                                              icon=":material/arrow_forward:",
                                              icon_position="right")
        st.html(ui.pin_footer())
    st.html(ui.PIN_KEYPAD_JS, unsafe_allow_javascript=True)

    if submitted:
        if hmac.compare_digest(pin.encode(), expected.encode()):
            state["fails"] = 0
            st.session_state["authed"] = True
            st.rerun()
        state["fails"] += 1
        if state["fails"] >= MAX_FAILS:
            state["fails"] = 0
            state["locked_until"] = now + LOCK_SECONDS
            alert.html(ui.pin_error("Too many wrong attempts. Locked for 15 minutes."))
        else:
            left = MAX_FAILS - state["fails"]
            alert.html(ui.pin_error(f"Wrong PIN. {left} {'try' if left == 1 else 'tries'} left."))
    st.stop()
