from datetime import date
import streamlit as st

from utils.session import get_db, require_login, current_tenant_id
from db.models import Expense

st.set_page_config(page_title="Expenses", page_icon="💰", layout="wide")
require_login()
db = get_db()
tid = current_tenant_id()

CATEGORIES = ["Electricity", "Rent", "Salary", "Equipment", "Consumables", "Maintenance", "Other"]

st.title("💰 Expenses")

with st.form("new_expense_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    exp_date = col1.date_input("Date", value=date.today())
    category = col2.selectbox("Category", CATEGORIES)
    description = st.text_input("Description")
    col3, col4 = st.columns(2)
    amount = col3.number_input("Amount *", min_value=0.0, step=100.0)
    payment_mode = col4.selectbox("Payment Mode", ["Cash", "UPI", "Card", "Bank Transfer"])
    if st.form_submit_button("Record Expense", type="primary"):
        if amount <= 0:
            st.error("Enter a valid amount.")
        else:
            e = Expense(tenant_id=tid, date=exp_date, category=category, description=description,
                        amount=amount, payment_mode=payment_mode, added_by=st.session_state["user_id"])
            db.add(e)
            db.commit()
            st.success("Expense recorded.")
            st.rerun()

st.divider()
expenses = db.query(Expense).filter_by(tenant_id=tid).order_by(Expense.date.desc()).limit(200).all()
if not expenses:
    st.info("No expenses recorded yet.")
else:
    import pandas as pd
    df = pd.DataFrame([{"Date": e.date, "Category": e.category, "Description": e.description,
                         "Amount": e.amount, "Mode": e.payment_mode} for e in expenses])
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.metric("Total (shown records)", f"₹{sum(e.amount for e in expenses):,.0f}")
