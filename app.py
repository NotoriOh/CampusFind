import streamlit as st
import hmac
import sqlite3
import base64
import html
from pathlib import Path

from database import (
    add_item,
    add_location,
    delete_item,
    delete_location,
    get_all_items,
    get_claims_for_item,
    get_item_by_id,
    get_locations,
    initialize_database,
    mark_item_returned,
    save_uploaded_photo,
)

from matching import find_matches
from admin_ui import render_admin_page

def show_saved_image(image_path, caption=None):
    path = Path(image_path) if image_path else None

    if path is None or not path.is_file():
        st.caption("Photo unavailable.")
        return

    image_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }

    mime_type = image_types.get(path.suffix.lower())

    if mime_type is None:
        st.caption("Unsupported image format.")
        return

    try:
        encoded = base64.b64encode(
            path.read_bytes()
        ).decode("utf-8")
    except OSError:
        st.caption("Photo could not be loaded.")
        return

    alt_text = html.escape(caption or "Item photo", quote=True)

    st.markdown(
        f"""
        <img
            src="data:{mime_type};base64,{encoded}"
            alt="{alt_text}"
            style="width:100%;height:auto;border-radius:8px;"
        >
        """,
        unsafe_allow_html=True,
    )

    if caption:
        st.caption(caption)
        
def show_matches(lost_item: dict, items: list[dict]) -> None:
    """Display available matches for one lost report."""
    st.markdown("#### Possible Matches")
    st.caption("Scores show item similarity, not proof of ownership.")

    matches = find_matches(lost_item, items)

    if not matches:
        st.info("No available matches scored 50 or higher.")
        return

    for match in matches:
        found_item = match["item"]

        with st.container(border=True):
            st.write(f"**{found_item['item_name']}**")
            st.metric("Match score", f"{match['score']}/100")
            st.caption(f"Found Report #{found_item['id']}")

            st.markdown("**Why this matched**")
            for reason in match["reasons"]:
                st.write(f"- {reason}")

            st.write(f"**Category:** {found_item['category']}")
            st.write(f"**Color:** {found_item['color']}")
            st.write(f"**Location:** {found_item['location']}")
            st.write(f"**Date found:** {found_item['event_date']}")

            if found_item["description"]:
                st.write(found_item["description"])

            photo = found_item.get("image_path")

            if photo:
                show_saved_image(photo)

            if st.button(
                "Claim This Item",
                key=f"match_claim_{lost_item['id']}_{found_item['id']}",
            ):
                st.session_state.selected_item_id = found_item["id"]
                st.switch_page("pages/claiminfo.py")
                
CATEGORIES = (
    "Electronics",
    "Clothing",
    "Bag",
    "School Supplies",
    "Keys",
    "Wallet",
    "Jewelry",
    "Other",
)

st.set_page_config(
    page_title="CampusFind",
    page_icon="🔎",
    layout="centered",
)

initialize_database()

logo_path = Path(__file__).resolve().parent / "logo" / "CampusFind.png"
logo_base64 = base64.b64encode(logo_path.read_bytes()).decode("utf-8")

_, account_column = st.columns([5, 1])

with account_column:
    if st.session_state.get("is_admin", False):
        if st.button(
            "Log out",
            key="header_logout",
            use_container_width=True,
        ):
            st.session_state["is_admin"] = False
            st.session_state["admin_view"] = "Home"
            st.session_state.pop("admin_notice", None)
            st.session_state["next_page"] = "Login"
            st.rerun()
    else:
        if st.button(
            "Admin Login",
            key="header_login",
            type="primary",
            use_container_width=True,
        ):
            st.session_state["next_page"] = "Login"
            st.rerun()

st.markdown(
    f"""
    <div style="display: flex; justify-content: center; margin-bottom: 20px;">
        <img
            src="data:image/png;base64,{logo_base64}"
            alt="CampusFind logo"
            draggable="false"
            style="
                width: 280px;
                max-width: 100%;
                height: auto;
                user-select: none;
                -webkit-user-drag: none;
            "
        >
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("Find your lost belongings. Help someone find theirs.")
st.caption(
    "Report a lost or found item and discover possible matches "
    "with clear explanations."
)

if "is_admin" not in st.session_state:
    st.session_state["is_admin"] = False

menu_options = ["Report an Item", "Browse Reports"]

if st.session_state["is_admin"]:
    menu_options.append("Admin")

if "main_menu" not in st.session_state:
    st.session_state["main_menu"] = "Report an Item"

next_page = st.session_state.pop("next_page", None)

if next_page == "Login":
    st.session_state["main_menu"] = None
elif next_page in menu_options:
    st.session_state["main_menu"] = next_page
elif (
    st.session_state["main_menu"] is not None
    and st.session_state["main_menu"] not in menu_options
):
    st.session_state["main_menu"] = "Report an Item"

selected_page = st.sidebar.radio(
    "Menu",
    menu_options,
    key="main_menu",
)

if selected_page is None:
    selected_page = "Login"

if selected_page == "Report an Item":
    st.subheader("Report an Item")

    report_type = st.radio(
        "Report Type",
        ("Lost", "Found"),
        horizontal=True,
    )

    with st.form("item_report_form", clear_on_submit=True):
        item_name = st.text_input(
            "Item Name",
            placeholder="Example: AirPods Pro",
        )

        category = st.selectbox(
            "Category",
            CATEGORIES,
        )

        color = st.text_input(
            "Color",
            placeholder="Example: White",
        )

        locations = get_locations()

        location = st.selectbox(
            "Location",
            locations,
        )
        
        event_date = st.date_input(
            "Date Lost or Found",
        )

        description = st.text_area(
            "Description",
            placeholder=(
                "Describe identifying features without revealing "
                "private ownership information."
            ),
        )

        uploaded_photo = None

        if report_type == "Found":
            uploaded_photo = st.file_uploader(
                "Upload a photo of the found item (optional)",
                type=["jpg", "jpeg", "png"],
            )
            
        submitted = st.form_submit_button(
            "Submit Report",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        required_fields = (
            item_name,
            color,
            location,
        )

        if any(not field.strip() for field in required_fields):
            st.error("Item name, color, and location are required.")
        else:
            image_path = save_uploaded_photo(uploaded_photo)

            report_id = add_item(
                report_type=report_type.upper(),
                item_name=item_name,
                category=category,
                color=color,
                location=location,
                event_date=event_date,
                description=description,
                image_path=image_path,
            )

            st.session_state["last_report_id"] = report_id

    last_report_id = st.session_state.get("last_report_id")

    if last_report_id is not None:
        saved_item = get_item_by_id(last_report_id)

        if saved_item is None:
            st.warning("The saved report no longer exists.")
            st.session_state.pop("last_report_id", None)
        else:
            st.success(f"Report #{last_report_id} was saved successfully.")

            if saved_item["report_type"] == "LOST" and saved_item["status"] == "Open":
                show_matches(saved_item, get_all_items())


elif selected_page == "Browse Reports":
    st.subheader("Current Reports")

    search_input = st.text_input(
        "Search reports",
        placeholder="Search item name, category, color, or location...",
        key="browse_search",
    ).strip().lower()

    type_column, category_column, status_column = st.columns(3)

    with type_column:
        type_filter = st.selectbox(
            "Report type",
            ("All", "Lost", "Found"),
            key="browse_type",
        )

    with category_column:
        category_filter = st.selectbox(
            "Category",
            ("All",) + CATEGORIES,
            key="browse_category",
        )

    with status_column:
        status_filter = st.selectbox(
            "Status",
            ("All", "Open", "Claim Pending", "Returned"),
            index=1,
            key="browse_status",
        )

    items = get_all_items()
    filtered_items = []

    for item in items:
        if type_filter != "All" and item["report_type"] != type_filter.upper():
            continue

        if category_filter != "All" and item["category"] != category_filter:
            continue

        if status_filter != "All" and item["status"] != status_filter:
            continue

        if search_input and not (
            search_input in item["item_name"].lower()
            or search_input in item["category"].lower()
            or search_input in item["color"].lower()
            or search_input in item["location"].lower()
        ):
            continue

        filtered_items.append(item)

    st.caption(f"Showing {len(filtered_items)} of {len(items)} reports.")

    if not items:
        st.info("No reports have been submitted yet.")
    elif not filtered_items:
        st.info("No reports match your search and filters.")

    for item in filtered_items:
        title = f"{item['report_type']}: {item['item_name']} (Report #{item['id']})"

        with st.expander(title):
            image_path = item.get("image_path")

            if image_path:
                show_saved_image(
                    image_path,
                    caption=item["item_name"],
                )
            else:
                st.caption("No photo uploaded.")

            st.write(f"**Category:** {item['category']}")
            st.write(f"**Color:** {item['color']}")
            st.write(f"**Location:** {item['location']}")
            st.write(f"**Date:** {item['event_date']}")
            st.write(f"**Status:** {item['status']}")

            description = item["description"]

            if description:
                st.write(f"**Description:** {description}")
            else:
                st.write("**Description:** None")

            if item["report_type"] == "FOUND" and item["status"] == "Open":
                if st.button(
                    "Claim This Item",
                    key=f"claim_{item['id']}",
                ):
                    st.session_state.selected_item_id = item["id"]
                    st.switch_page("pages/claiminfo.py")
                    
            if item["report_type"] == "LOST" and item["status"] == "Open":
                show_matches(item, items)

elif selected_page == "Login":
    st.subheader("Administrator Login")
    st.caption("Sign in to manage reports, locations, and returns.")

    try:
        admin_password = st.secrets["admin_password"]
    except (FileNotFoundError, KeyError):
        st.info("The administrator password has not been configured.")
        st.stop()

    if not isinstance(admin_password, str) or not admin_password:
        st.error("Please configure a non-empty administrator password.")
        st.stop()

    with st.form("admin_login_form", clear_on_submit=True):
        entered_password = st.text_input("Password", type="password")
        login_submitted = st.form_submit_button(
            "Log in",
            type="primary",
            use_container_width=True,
        )

    if login_submitted:
        if not entered_password:
            st.error("Please enter your password.")
        elif hmac.compare_digest(
            entered_password.encode("utf-8"),
            admin_password.encode("utf-8"),
        ):
            st.session_state["is_admin"] = True
            st.session_state["admin_view"] = "Home"
            st.session_state["next_page"] = "Admin"
            st.rerun()
        else:
            st.error("Incorrect password.")

elif selected_page == "Admin":
    render_admin_page()
