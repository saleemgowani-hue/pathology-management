import streamlit as st

st.set_page_config(page_title="PathoLab Pro Cloud", page_icon="🩺", layout="wide")

from db.init_db import init_db  # noqa: E402
from db.seed_demo import seed_demo_account, DEMO_LAB_CODE, DEMO_USERNAME, DEMO_PASSWORD  # noqa: E402
from utils.session import get_db, is_logged_in, login_session, logout_session, current_full_name, current_role, current_tenant_id  # noqa: E402
from utils.auth import authenticate, create_admin_user, join_existing_lab, STAFF_ROLES  # noqa: E402
from utils.license_manager import register_tenant, tenant_status, renew_tenant  # noqa: E402
from db.models import Tenant  # noqa: E402


@st.cache_resource
def _ensure_db():
    init_db()
    seed_demo_account(get_db())
    return True


_ensure_db()

st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; }

    /* --- Sidebar: professional, colour-coded navigation --- */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0B2545 0%, #12385F 100%);
    }
    [data-testid="stSidebar"] * { color: #E8EEF7 !important; }
    [data-testid="stSidebarNav"] { padding-top: 0.5rem; }
    [data-testid="stSidebarNav"] li { list-style: none; }
    [data-testid="stSidebarNav"] a,
    [data-testid="stSidebarNav"] span[data-testid="stSidebarNavLink"] {
        border-radius: 8px;
        margin: 3px 10px;
        padding: 0.5rem 0.75rem !important;
        font-weight: 500;
        transition: background 0.15s ease, transform 0.15s ease;
        border-left: 4px solid transparent;
    }
    [data-testid="stSidebarNav"] li:nth-child(6n+1) a { border-left-color: #4FC3F7; }
    [data-testid="stSidebarNav"] li:nth-child(6n+2) a { border-left-color: #66BB6A; }
    [data-testid="stSidebarNav"] li:nth-child(6n+3) a { border-left-color: #FFB74D; }
    [data-testid="stSidebarNav"] li:nth-child(6n+4) a { border-left-color: #BA68C8; }
    [data-testid="stSidebarNav"] li:nth-child(6n+5) a { border-left-color: #EF5350; }
    [data-testid="stSidebarNav"] li:nth-child(6n+6) a { border-left-color: #26C6DA; }
    [data-testid="stSidebarNav"] a:hover {
        background: rgba(255, 255, 255, 0.10);
        transform: translateX(3px);
    }
    [data-testid="stSidebarNav"] a[aria-current="page"] {
        background: rgba(255, 255, 255, 0.16);
        font-weight: 700;
    }
    [data-testid="stSidebarNavSeparator"],
    [data-testid="stSidebarHeader"] { color: #9FB3CC !important; }
    section[data-testid="stSidebar"] .stButton button {
        border-radius: 8px;
        border: 1px solid rgba(255,255,255,0.35);
        background: rgba(255,255,255,0.06);
        color: #E8EEF7;
    }
    section[data-testid="stSidebar"] .stButton button:hover {
        background: rgba(255,255,255,0.18);
        border-color: #4FC3F7;
    }
    [data-testid="stSidebar"] code {
        background: rgba(255, 255, 255, 0.16) !important;
        color: #FFD54F !important;
        padding: 1px 6px;
        border-radius: 4px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def home_page():
    st.markdown("## 🩺 PathoLab Pro — Cloud")
    st.caption("Multi-tenant pathology lab management platform")

    tab_login, tab_register, tab_join = st.tabs(["🔑 Log In", "🏥 Register New Lab", "👤 Join Existing Lab"])

    with tab_login:
        st.markdown("#### Log in to your lab")
        st.info(
            f"👀 **Just want to look around?** A demo lab is pre-filled below — "
            f"click **Log In** as-is.  \n"
            f"Lab Code `{DEMO_LAB_CODE}` · Username `{DEMO_USERNAME}` · Password `{DEMO_PASSWORD}`"
        )
        with st.form("login_form"):
            lab_code = st.text_input("Lab Code", value=DEMO_LAB_CODE, help="Given to you when your lab registered")
            username = st.text_input("Username", value=DEMO_USERNAME)
            password = st.text_input("Password", value=DEMO_PASSWORD, type="password")
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


if not is_logged_in():
    nav = st.navigation([st.Page(home_page, title="Home", icon="🏠", default=True)])
    nav.run()
else:
    db = get_db()
    tenant = db.query(Tenant).get(current_tenant_id())
    state = tenant_status(tenant)
    db.commit()

    with st.sidebar:
        st.markdown(f"### 🩺 {tenant.lab_name}")
        st.caption(f"**{current_full_name()}** · {current_role().capitalize()} · Lab Code `{tenant.lab_code}`")
        if state["locked"]:
            st.error("Subscription expired.")
        else:
            st.caption(f"Plan: **{tenant.plan.capitalize()}** · {state['remaining_days']} day(s) left")
        if st.button("🚪 Log out", use_container_width=True):
            logout_session()
            st.rerun()
        st.divider()

    is_admin = current_role() == "admin"

    pages = {
        "Overview": [
            st.Page("pages/1_📊_Dashboard.py", title="Dashboard", icon="📊", default=True),
        ],
        "Front Desk": [
            st.Page("pages/2_🧑‍🤝‍🧑_Patients.py", title="Patients", icon="🧑‍🤝‍🧑"),
            st.Page("pages/4_🩸_Sample_Collection.py", title="Sample Collection", icon="🩸"),
            st.Page("pages/7_🧾_Billing.py", title="Billing", icon="🧾"),
        ],
        "Laboratory": [
            st.Page("pages/3_🧪_Test_Master.py", title="Test Master", icon="🧪"),
            st.Page("pages/5_📝_Result_Entry.py", title="Result Entry", icon="📝"),
            st.Page("pages/6_✅_Report_Verification.py", title="Report Verification", icon="✅"),
        ],
        "Operations": [
            st.Page("pages/8_👨‍⚕️_Doctors_and_Pathologists.py", title="Doctors & Pathologists", icon="👨‍⚕️"),
            st.Page("pages/9_👥_Staff_and_Attendance.py", title="Staff & Attendance", icon="👥"),
            st.Page("pages/10_📦_Inventory.py", title="Inventory", icon="📦"),
            st.Page("pages/11_💰_Expenses.py", title="Expenses", icon="💰"),
        ],
        "Insights": [
            st.Page("pages/12_📈_Reports.py", title="Reports", icon="📈"),
        ],
    }
    if is_admin:
        pages["Administration"] = [
            st.Page("pages/13_⚙️_Settings.py", title="Settings", icon="⚙️"),
            st.Page("pages/14_🔐_User_Management.py", title="User Management", icon="🔐"),
        ]

    nav = st.navigation(pages)

    if state["locked"]:
        st.error(
            "Your lab's subscription has expired. "
            + ("Renew below to continue." if is_admin else "Please ask your administrator to renew it.")
        )
        if is_admin:
            with st.form("renew_form"):
                renew_key = st.text_input("Enter a new License Key (Monthly or Yearly)")
                if st.form_submit_button("Renew License"):
                    ok, msg = renew_tenant(db, tenant, renew_key)
                    (st.success if ok else st.error)(msg)
                    if ok:
                        st.rerun()
    else:
        nav.run()
