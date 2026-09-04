import streamlit as st

st.set_page_config(page_title="PathoLab Pro Cloud", page_icon="🩺", layout="wide")

from db.init_db import init_db  # noqa: E402
from utils.session import get_db, is_logged_in, login_session, logout_session, current_full_name, current_role, current_tenant_id  # noqa: E402
from utils.auth import authenticate, create_admin_user, join_existing_lab, STAFF_ROLES  # noqa: E402
from utils.license_manager import register_tenant, tenant_status, renew_tenant  # noqa: E402
from db.models import Tenant  # noqa: E402


@st.cache_resource
def _ensure_db():
    init_db()
    return True


_ensure_db()

st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; max-width: 900px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("## 🩺 PathoLab Pro — Cloud")
st.caption("Multi-tenant pathology lab management platform")

if is_logged_in():
    db = get_db()
    tenant = db.query(Tenant).get(current_tenant_id())
    state = tenant_status(tenant)
    db.commit()

    st.success(f"Logged in as **{current_full_name()}** ({current_role().capitalize()}) — {tenant.lab_name}")

    if state["locked"]:
        st.error(
            "Your lab's subscription has expired. "
            + ("Renew below to continue." if current_role() == "admin"
               else "Please ask your administrator to renew it.")
        )
        if current_role() == "admin":
            with st.form("renew_form"):
                renew_key = st.text_input("Enter a new License Key (Monthly or Yearly)")
                if st.form_submit_button("Renew License"):
                    ok, msg = renew_tenant(db, tenant, renew_key)
                    (st.success if ok else st.error)(msg)
                    if ok:
                        st.rerun()
    else:
        st.info(f"Lab Code: **{tenant.lab_code}** · Plan: **{tenant.plan.capitalize()}** · "
                f"{state['remaining_days']} day(s) remaining")
        st.markdown("Use the sidebar to navigate to Dashboard, Patients, Billing, and every other module.")

    if st.button("Log out"):
        logout_session()
        st.rerun()

else:
    tab_login, tab_register, tab_join = st.tabs(["🔑 Log In", "🏥 Register New Lab", "👤 Join Existing Lab"])

    with tab_login:
        st.markdown("#### Log in to your lab")
        with st.form("login_form"):
            lab_code = st.text_input("Lab Code", help="Given to you when your lab registered")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log In", type="primary")
            if submitted:
                db = get_db()
                user, tenant, err = authenticate(db, lab_code, username, password)
                if err:
                    st.error(err)
                else:
                    login_session(user, tenant)
                    st.rerun()

    with tab_register:
        st.markdown("#### Register a new pathology lab")
        st.caption(
            "There is no free trial — a Monthly or Yearly license key is required to register. "
            "Your key came from your software vendor."
        )
        with st.form("register_form"):
            lab_name = st.text_input("Lab / Diagnostic Center Name *")
            full_name = st.text_input("Your Full Name (becomes the Administrator) *")
            reg_username = st.text_input("Choose a Username *")
            reg_password = st.text_input("Choose a Password *", type="password")
            reg_confirm = st.text_input("Confirm Password *", type="password")
            reg_mobile = st.text_input("Mobile Number")
            license_key = st.text_input("License Key *", placeholder="XXXXX-XXXXX-XXXXX-XXXXX")
            submitted = st.form_submit_button("Register Lab", type="primary")
            if submitted:
                if not all([lab_name, full_name, reg_username, reg_password, license_key]):
                    st.error("Please fill in all required fields marked *.")
                elif len(reg_password) < 6:
                    st.error("Password must be at least 6 characters.")
                elif reg_password != reg_confirm:
                    st.error("Password and confirmation do not match.")
                else:
                    db = get_db()
                    tenant, err = register_tenant(db, lab_name, license_key)
                    if err:
                        st.error(err)
                    else:
                        create_admin_user(db, tenant.id, full_name, reg_username, reg_password, reg_mobile)
                        st.success(
                            f"Lab registered! Your **Lab Code** is **{tenant.lab_code}** — "
                            "write this down, you'll need it (with your username and password) to log in."
                        )
                        st.balloons()

    with tab_join:
        st.markdown("#### Join a lab that's already registered")
        st.caption("Your account will need approval from your lab's administrator before you can log in.")
        with st.form("join_form"):
            join_lab_code = st.text_input("Lab Code *")
            join_full_name = st.text_input("Your Full Name *")
            join_username = st.text_input("Choose a Username *")
            join_password = st.text_input("Choose a Password *", type="password")
            join_confirm = st.text_input("Confirm Password *", type="password")
            join_mobile = st.text_input("Mobile Number")
            join_role = st.selectbox("Your Role *", STAFF_ROLES, format_func=lambda r: r.capitalize())
            submitted = st.form_submit_button("Join Lab", type="primary")
            if submitted:
                if not all([join_lab_code, join_full_name, join_username, join_password]):
                    st.error("Please fill in all required fields marked *.")
                elif len(join_password) < 6:
                    st.error("Password must be at least 6 characters.")
                elif join_password != join_confirm:
                    st.error("Password and confirmation do not match.")
                else:
                    db = get_db()
                    tenant = db.query(Tenant).filter_by(lab_code=join_lab_code.strip().upper()).first()
                    if not tenant:
                        st.error("Lab Code not found. Double-check it with your lab administrator.")
                    else:
                        user, err = join_existing_lab(db, tenant.id, join_full_name, join_username,
                                                       join_password, join_role, join_mobile)
                        if err:
                            st.error(err)
                        else:
                            st.success("Account created! Your administrator needs to approve it before you can log in.")
