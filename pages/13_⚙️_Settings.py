import streamlit as st

from utils.session import get_db, require_role, current_tenant_id
from utils.helpers import get_settings_dict, set_setting

require_role("admin")
db = get_db()
tid = current_tenant_id()

st.title("⚙️ Lab Settings")
st.caption("These details appear on every printed report and receipt.")

current = get_settings_dict(db, tid)

with st.form("settings_form"):
    lab_name = st.text_input("Laboratory Name", value=current.get("lab_name", ""))
    lab_address = st.text_input("Address", value=current.get("lab_address", ""))
    col1, col2 = st.columns(2)
    lab_phone = col1.text_input("Phone", value=current.get("lab_phone", ""))
    lab_email = col2.text_input("Email", value=current.get("lab_email", ""))
    disclaimer = st.text_area("Report Disclaimer / Footer Text", value=current.get(
        "report_disclaimer",
        "This report is generated electronically and is valid for the tests performed on the sample received. "
        "Results should be correlated clinically.",
    ))
    if st.form_submit_button("Save Settings", type="primary"):
        for key, value in [("lab_name", lab_name), ("lab_address", lab_address), ("lab_phone", lab_phone),
                            ("lab_email", lab_email), ("report_disclaimer", disclaimer)]:
            set_setting(db, tid, key, value)
        st.success("Settings saved.")
