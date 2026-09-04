import streamlit as st
from db.connection import SessionLocal


def get_db():
    """One SQLAlchemy session per Streamlit script run, cleaned up
    automatically. Streamlit re-runs the whole script on every
    interaction, so this is called fresh each time — cheap and safe."""
    return SessionLocal()


def is_logged_in() -> bool:
    return "user_id" in st.session_state and "tenant_id" in st.session_state


def current_tenant_id():
    return st.session_state.get("tenant_id")


def current_user_id():
    return st.session_state.get("user_id")


def current_role():
    return st.session_state.get("role")


def current_full_name():
    return st.session_state.get("full_name")


def login_session(user, tenant):
    st.session_state["user_id"] = user.id
    st.session_state["tenant_id"] = tenant.id
    st.session_state["role"] = user.role
    st.session_state["full_name"] = user.full_name
    st.session_state["username"] = user.username
    st.session_state["lab_name"] = tenant.lab_name
    st.session_state["lab_code"] = tenant.lab_code


def logout_session():
    for key in ["user_id", "tenant_id", "role", "full_name", "username", "lab_name", "lab_code"]:
        st.session_state.pop(key, None)


def require_login():
    """Call at the top of every page. Stops the page from rendering
    further if nobody is logged in."""
    if not is_logged_in():
        st.warning("Please log in from the Home page first.")
        st.stop()


def require_role(*roles):
    require_login()
    if current_role() not in roles:
        st.error("You don't have permission to view this page.")
        st.stop()
