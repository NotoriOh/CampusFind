"""Authenticated Admin home and its three management screens."""

import sqlite3

import streamlit as st

from database import (
    add_location,
    delete_item,
    delete_location,
    get_all_items,
    get_claims_for_item,
    get_locations,
    mark_item_returned,
)


def _navigate(view: str) -> None:
    st.session_state["admin_view"] = view


def _notify(message: str) -> None:
    st.session_state["admin_notice"] = message
    st.rerun()


def _show_home() -> None:
    items = get_all_items()
    pending = sum(
        item["report_type"] == "FOUND" and item["status"] == "Claim Pending"
        for item in items
    )
    locations = get_locations()
    st.caption("Choose an area to manage.")

    sections = [
        ("Claims & Returns", pending, "Items awaiting return", "Review Claims", "Claims"),
        ("Reports", len(items), "Lost and found reports", "Manage Reports", "Reports"),
        ("Locations", len(locations), "Available campus locations", "Manage Locations", "Locations"),
    ]
    for column, (title, count, caption, button, view) in zip(st.columns(3), sections):
        with column:
            with st.container(border=True):
                st.metric(title, count)
                st.caption(caption)
                st.button(
                    button,
                    key=f"admin_open_{view.lower()}",
                    use_container_width=True,
                    on_click=_navigate,
                    args=(view,),
                )


def _show_reports() -> None:
    st.caption("Review reports. Only Open reports can be deleted.")
    items = get_all_items()
    if not items:
        st.info("No reports have been submitted yet.")
        return

    for item in items:
        with st.expander(
            f"{item['report_type']} - {item['item_name']} (Report #{item['id']})"
        ):
            st.write(f"**Status:** {item['status']}")
            st.write(f"**Location:** {item['location']}")
            if st.button(
                "Delete Report",
                key=f"admin_delete_{item['id']}",
                disabled=item["status"] != "Open",
            ):
                try:
                    delete_item(item["id"])
                except sqlite3.Error:
                    st.error("The report could not be deleted. Please try again.")
                else:
                    _notify(f"Report #{item['id']} deleted.")


def _show_locations() -> None:
    st.caption("Maintain the locations available in report forms.")
    with st.form("admin_add_location_form", clear_on_submit=True):
        new_location = st.text_input("New location")
        submitted = st.form_submit_button("Add Location")
    if submitted:
        try:
            added = add_location(new_location)
        except sqlite3.Error:
            st.error("The location could not be saved. Please try again.")
        else:
            if added:
                _notify(f"{new_location.strip()} added.")
            else:
                st.warning("Enter a valid location that does not already exist.")

    st.divider()
    locations = get_locations()
    if not locations:
        st.info("No locations are available. Add a location above.")
        return

    selected = st.selectbox("Location to remove", locations, key="admin_location_select")
    if len(locations) == 1:
        st.caption("At least one location must remain.")
    if st.button("Delete Location", disabled=len(locations) <= 1):
        try:
            deleted = delete_location(selected)
        except sqlite3.Error:
            st.error("The location could not be deleted. Please try again.")
        else:
            if deleted:
                _notify(f"{selected} deleted.")
            else:
                st.warning("The location could not be removed. At least one location must remain.")


def _show_claims() -> None:
    st.caption("Verify ownership and hand over the item before marking it Returned.")
    items = [
        item for item in get_all_items()
        if item["report_type"] == "FOUND" and item["status"] == "Claim Pending"
    ]
    if not items:
        st.info("No items are waiting to be returned.")
        return

    for item in items:
        with st.expander(f"{item['item_name']} (Report #{item['id']})"):
            st.write(f"**Status:** {item['status']}")
            st.write(f"**Location:** {item['location']}")
            claims = get_claims_for_item(item["id"])
            if not claims:
                st.warning("No claim record was found for this item.")
                continue
            for claim in claims:
                st.text(
                    f"Name: {claim['name']}\n"
                    f"Email: {claim['email']}\n"
                    f"Contact: {claim['contact']}"
                )
            if st.button("Mark as Returned", key=f"admin_return_{item['id']}"):
                try:
                    updated = mark_item_returned(item["id"])
                except sqlite3.Error:
                    st.error("The status could not be saved. Please try again.")
                else:
                    if updated:
                        _notify(f"Report #{item['id']} was marked Returned.")
                    else:
                        st.warning("This item is no longer awaiting return.")


def render_admin_page() -> None:
    # Guard every screen, including direct rendering of a saved admin_view.
    if not st.session_state.get("is_admin", False):
        st.warning("Please log in first.")
        st.stop()

    screens = {
        "Home": ("Admin Dashboard", _show_home),
        "Claims": ("Claims & Returns", _show_claims),
        "Reports": ("Manage Reports", _show_reports),
        "Locations": ("Manage Locations", _show_locations),
    }
    view = st.session_state.get("admin_view", "Home")
    if view not in screens:
        view = "Home"
        st.session_state["admin_view"] = view

    if view != "Home":
        st.button("Back to Admin Home", on_click=_navigate, args=("Home",))
    title, render = screens[view]
    st.subheader(title)
    notice = st.session_state.pop("admin_notice", None)
    if notice:
        st.success(notice)
    render()
