from datetime import datetime
import streamlit as st

from utils.session import get_db, require_login, current_tenant_id
from utils.helpers import next_receipt_number, log_action
from db.models import Bill, BillItem, Payment, Patient, TestItem, TestProfile

require_login()
db = get_db()
tid = current_tenant_id()

st.title("🧾 Billing")

tab_list, tab_new = st.tabs(["Bill List", "New Bill"])

with tab_new:
    patients = db.query(Patient).filter_by(tenant_id=tid).order_by(Patient.name).all()
    tests = db.query(TestItem).filter_by(tenant_id=tid, active=True).order_by(TestItem.name).all()
    profiles = db.query(TestProfile).filter_by(tenant_id=tid, active=True).all()

    if not patients:
        st.warning("Register a patient first.")
    else:
        patient_id = st.selectbox("Patient *", [p.id for p in patients],
                                   format_func=lambda x: next(f"{p.patient_code} - {p.name}" for p in patients if p.id == x))
        options = {f"{t.name} — ₹{t.price:.0f}": t.price for t in tests}
        options.update({f"{p.name} (Package) — ₹{p.price:.0f}": p.price for p in profiles})
        selected = st.multiselect("Tests / Packages *", list(options.keys()))
        gross = sum(options[s] for s in selected)
        col1, col2 = st.columns(2)
        discount = col1.number_input("Discount", min_value=0.0, max_value=float(gross) if gross else 0.0, step=10.0)
        net = max(gross - discount, 0)
        col2.metric("Net Amount", f"₹{net:,.0f}")
        col3, col4 = st.columns(2)
        paid_amount = col3.number_input("Paid Amount", min_value=0.0, max_value=float(net) if net else 0.0, step=10.0, value=float(net) if net else 0.0)
        payment_mode = col4.selectbox("Payment Mode", ["Cash", "UPI", "Card", "Bank Transfer"])

        if st.button("Create Bill", type="primary", disabled=not selected):
            receipt_number = next_receipt_number(db, tid)
            bill = Bill(tenant_id=tid, receipt_number=receipt_number, patient_id=patient_id,
                        gross_amount=gross, discount=discount, net_amount=net, paid_amount=paid_amount,
                        due_amount=net - paid_amount, payment_mode=payment_mode,
                        created_by=st.session_state["user_id"], created_at=datetime.utcnow())
            db.add(bill)
            db.flush()
            for s in selected:
                db.add(BillItem(tenant_id=tid, bill_id=bill.id, description=s.split(" — ")[0], price=options[s]))
            if paid_amount > 0:
                db.add(Payment(tenant_id=tid, bill_id=bill.id, amount=paid_amount, mode=payment_mode, date=datetime.utcnow()))
            db.commit()
            log_action(db, tid, st.session_state["user_id"], "Bill Created", bill.id, receipt_number)
            st.success(f"Bill {receipt_number} created.")
            st.rerun()

with tab_list:
    q = st.text_input("Search by patient name")
    query = db.query(Bill).filter_by(tenant_id=tid)
    bills = query.order_by(Bill.id.desc()).limit(200).all()
    if q:
        bills = [b for b in bills if q.lower() in b.patient.name.lower()]

    if not bills:
        st.info("No bills found.")
    for b in bills:
        with st.expander(f"{b.receipt_number} — {b.patient.name} — ₹{b.net_amount:.0f} ({b.status})"):
            st.write(f"**Gross:** ₹{b.gross_amount:.0f} | **Discount:** ₹{b.discount:.0f} | **Net:** ₹{b.net_amount:.0f}")
            st.write(f"**Paid:** ₹{b.paid_amount:.0f} | **Due:** ₹{b.due_amount:.0f}")
            items = db.query(BillItem).filter_by(tenant_id=tid, bill_id=b.id).all()
            for item in items:
                st.write(f"- {item.description}: ₹{item.price:.0f}")

            if b.due_amount > 0 and b.status == "Active":
                pay_amt = st.number_input("Record Payment", min_value=0.0, max_value=float(b.due_amount), step=10.0, key=f"pay_{b.id}")
                pay_mode = st.selectbox("Mode", ["Cash", "UPI", "Card", "Bank Transfer"], key=f"paymode_{b.id}")
                if st.button("Record Payment", key=f"recpay_{b.id}") and pay_amt > 0:
                    db.add(Payment(tenant_id=tid, bill_id=b.id, amount=pay_amt, mode=pay_mode, date=datetime.utcnow()))
                    b.paid_amount += pay_amt
                    b.due_amount -= pay_amt
                    db.commit()
                    st.success("Payment recorded.")
                    st.rerun()

            if b.status == "Active" and st.session_state.get("role") in ("admin", "accountant"):
                if st.button("Cancel Bill", key=f"cancel_{b.id}"):
                    b.status = "Cancelled"
                    db.commit()
                    log_action(db, tid, st.session_state["user_id"], "Bill Cancelled", b.id)
                    st.warning("Bill cancelled.")
                    st.rerun()
