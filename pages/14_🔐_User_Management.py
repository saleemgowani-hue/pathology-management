import streamlit as st
from sqlalchemy.exc import IntegrityError

from utils.session import get_db, require_role, current_tenant_id, current_user_id
from utils.auth import hash_password, ROLES
from db.models import User

require_role("admin")
db = get_db()
tid = current_tenant_id()

st.title("🔐 User Management")

ADDABLE_ROLES = [r for r in ROLES if r != "admin"]

tab_list, tab_add = st.tabs(["Staff List", "➕ Add Staff Member"])

with tab_add:
    st.markdown("#### Add a new staff member")
    st.caption("Created accounts are active immediately — no separate approval step needed.")
    with st.form("add_staff_form", clear_on_submit=True):
        full_name = st.text_input("Full Name *")
        col1, col2 = st.columns(2)
        username = col1.text_input("Username *")
        role = col2.selectbox("Role *", ADDABLE_ROLES, format_func=lambda r: r.capitalize())
        col3, col4 = st.columns(2)
        password = col3.text_input("Password *", type="password")
        confirm = col4.text_input("Confirm Password *", type="password")
        mobile = st.text_input("Mobile Number")
        submitted = st.form_submit_button("Add Staff Member", type="primary")
        if submitted:
            if not all([full_name, username, password]):
                st.error("Please fill in all required fields marked *.")
            elif len(password) < 6:
                st.error("Password must be at least 6 characters.")
            elif password != confirm:
                st.error("Password and confirmation do not match.")
            elif db.query(User).filter_by(tenant_id=tid, username=username.strip()).first():
                st.error("That username is already taken at this lab. Please choose another.")
            else:
                db.add(User(
                    tenant_id=tid, username=username.strip(), full_name=full_name.strip(),
                    role=role, mobile=mobile.strip(), active=True,
                    password_hash=hash_password(password),
                ))
                db.commit()
                st.success(f"'{full_name}' added as {role.capitalize()} and can log in now.")
                st.rerun()

with tab_list:
    users = db.query(User).filter_by(tenant_id=tid).order_by(User.id).all()
    pending = [u for u in users if not u.active]
    if pending:
        st.warning(f"{len(pending)} account(s) are waiting for your approval.")

    for u in users:
        status = "🟢 Active" if u.active else "🟡 Pending Approval"
        is_self = u.id == current_user_id()
        with st.expander(f"{u.full_name} — @{u.username} — {u.role.capitalize()} — {status}"):
            col1, col2 = st.columns(2)
            col1.write(f"**Username:** {u.username}")
            col1.write(f"**Role:** {u.role.capitalize()}")
            col2.write(f"**Mobile:** {u.mobile or '-'}")
            col2.write(f"**Status:** {status}")

            if is_self:
                st.caption("This is your own account — manage it from here directly, not through this list.")
            else:
                col_a, col_b = st.columns(2)
                toggle_label = "Deactivate" if u.active else "Approve"
                if col_a.button(toggle_label, key=f"toggle_{u.id}"):
                    u.active = not u.active
                    db.commit()
                    st.rerun()

                if col_b.button("🗑️ Remove", key=f"remove_{u.id}"):
                    st.session_state[f"confirm_remove_{u.id}"] = True

                if st.session_state.get(f"confirm_remove_{u.id}"):
                    st.warning(f"Remove **{u.full_name}** (@{u.username}) permanently? This can't be undone.")
                    col_yes, col_no = st.columns(2)
                    if col_yes.button("Yes, remove", key=f"confirm_yes_{u.id}", type="primary"):
                        try:
                            db.delete(u)
                            db.commit()
                            st.session_state.pop(f"confirm_remove_{u.id}", None)
                            st.success(f"{u.full_name} removed.")
                            st.rerun()
                        except IntegrityError:
                            db.rollback()
                            st.error(
                                "Can't remove this user — they have historical records "
                                "(bills, results, expenses, etc.) tied to their account. "
                                "Deactivate them instead to block their access."
                            )
                    if col_no.button("Cancel", key=f"confirm_no_{u.id}"):
                        st.session_state.pop(f"confirm_remove_{u.id}", None)
                        st.rerun()

            st.divider()
            st.markdown("**Change Password**")
            with st.form(f"pwd_form_{u.id}", clear_on_submit=True):
                new_pwd = st.text_input("New Password", type="password", key=f"new_pwd_{u.id}")
                new_pwd_confirm = st.text_input("Confirm New Password", type="password", key=f"new_pwd_confirm_{u.id}")
                if st.form_submit_button("Update Password"):
                    if len(new_pwd) < 6:
                        st.error("Password must be at least 6 characters.")
                    elif new_pwd != new_pwd_confirm:
                        st.error("Passwords do not match.")
                    else:
                        u.password_hash = hash_password(new_pwd)
                        db.commit()
                        st.success(f"Password updated for {u.full_name}.")
