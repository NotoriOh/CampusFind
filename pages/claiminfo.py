import re
import sqlite3

import streamlit as st

from database import (
    get_item_by_id,
    initialize_database,
    save_claim_info,
)


initialize_database()

st.title("Claim This Item")
st.page_link("app.py", label="Back to CampusFind")

item_id = st.session_state.get("selected_item_id")

if item_id is None:
    st.info("Please select a Found item from Browse Reports first.")
    st.stop()

item = get_item_by_id(item_id)

if item is None:
    st.warning("This report no longer exists.")
    st.stop()

if item["report_type"] != "FOUND" or item["status"] != "Open":
    st.warning("This item is not available for claiming.")
    st.stop()

st.subheader(item["item_name"])
st.caption(f"Report #{item_id}")
st.write(f"**Location:** {item['location']}")

with st.form(f"claim_form_{item_id}"):
    name = st.text_input("Your Name")
    email = st.text_input("Your Email")
    contact = st.text_input("Your Contact Number")

    submitted = st.form_submit_button("Submit Claim")

if submitted:
    name = name.strip()
    email = email.strip()
    contact = contact.strip()

    phone_digits = re.sub(r"[^0-9]", "", contact)

    if not name or not email or not contact:
        st.error("Please fill in all the fields.")

    elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        st.error("Please enter a valid email, such as student@example.com.")

    elif (
        not re.fullmatch(r"\+?[0-9 ()-]+", contact) or not 7 <= len(phone_digits) <= 15
    ):
        st.error("Please enter a phone number containing 7–15 digits.")

    else:
        try:
            saved = save_claim_info(
                item_id=item_id,
                name=name,
                email=email,
                contact=contact,
            )
        except sqlite3.Error:
            st.error("Your claim could not be saved. Please try again.")
        else:
            if saved:
                st.session_state.pop("selected_item_id", None)
                st.success("Your claim has been submitted and is pending verification.")
            else:
                st.warning("This item is no longer available for claiming.")
