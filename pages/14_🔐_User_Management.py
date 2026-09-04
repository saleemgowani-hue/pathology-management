import streamlit as st

from utils.session import get_db, require_role, current_tenant_id, current_user_id
from db.models import User

require_role("admin")
db = get_db()
tid = current_tenant_id()

st.title("🔐 User Management")

users = db.query(User).filter_by(tenant_id=tid).order_by(User.id).all()
pending = [u for u in users if not u.active]

if pending:
    st.warning(f"{len(pending)} account(s) are waiting for your approval.")

for u in users:
    col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 2])
    col1.write(f"**{u.username}**")
    col2.write(u.full_name)
    col3.write(u.role.capitalize())
    col4.write("🟢 Active" if u.active else "🟡 Pending Approval")
    if u.id != current_user_id():
        label = "Deactivate" if u.active else "Approve"
        if col5.button(label, key=f"toggle_{u.id}"):
            u.active = not u.active
            db.commit()
            st.rerun()
    st.divider()
