from datetime import datetime
import streamlit as st

from utils.session import get_db, require_login, current_tenant_id, current_full_name
from utils.helpers import next_sample_number, log_action
from db.models import Sample, Patient, TestItem, TestOrder, Report

require_login()
db = get_db()
tid = current_tenant_id()

STATUSES = ["Collected", "Received", "Processing", "Completed", "Rejected"]

st.title("🩸 Sample Collection")

tab_list, tab_new = st.tabs(["Sample List", "Collect New Sample"])

with tab_new:
    patients = db.query(Patient).filter_by(tenant_id=tid).order_by(Patient.name).all()
    tests = db.query(TestItem).filter_by(tenant_id=tid, active=True).order_by(TestItem.name).all()
    if not patients:
        st.warning("Register a patient first.")
    elif not tests:
        st.warning("Add at least one test in Test Master first.")
    else:
        with st.form("new_sample_form", clear_on_submit=True):
            patient_id = st.selectbox("Patient *", [p.id for p in patients],
                                       format_func=lambda x: next(f"{p.patient_code} - {p.name}" for p in patients if p.id == x))
            sample_type = st.text_input("Sample Type", value="Blood (EDTA)")
            selected_tests = st.multiselect("Tests *", [t.id for t in tests],
                                             format_func=lambda x: next(t.name for t in tests if t.id == x))
            submitted = st.form_submit_button("Register Sample", type="primary")
            if submitted:
                if not selected_tests:
                    st.error("Select at least one test.")
                else:
                    sample_number = next_sample_number(db, tid)
                    s = Sample(tenant_id=tid, sample_number=sample_number, patient_id=patient_id,
                               sample_type=sample_type, status="Collected", collected_by=current_full_name(),
                               collection_datetime=datetime.utcnow())
                    db.add(s)
                    db.flush()
                    for test_id in selected_tests:
                        db.add(TestOrder(tenant_id=tid, sample_id=s.id, test_id=test_id))
                    db.add(Report(tenant_id=tid, sample_id=s.id, status="Draft"))
                    db.commit()
                    log_action(db, tid, st.session_state["user_id"], "Sample Collected", s.id, sample_number)
                    st.success(f"Sample {sample_number} registered.")
                    st.rerun()

with tab_list:
    status_filter = st.selectbox("Filter by status", ["All"] + STATUSES)
    query = db.query(Sample).filter_by(tenant_id=tid)
    if status_filter != "All":
        query = query.filter_by(status=status_filter)
    samples = query.order_by(Sample.id.desc()).limit(200).all()

    if not samples:
        st.info("No samples found.")
    for s in samples:
        orders = db.query(TestOrder).filter_by(tenant_id=tid, sample_id=s.id).all()
        test_names = ", ".join(o.test.name for o in orders)
        with st.expander(f"{s.sample_number} — {s.patient.name} — {s.status}"):
            st.write(f"**Tests:** {test_names}")
            st.write(f"**Collected:** {s.collection_datetime.strftime('%d-%b-%Y %H:%M')} by {s.collected_by}")
            new_status = st.selectbox("Update Status", STATUSES, index=STATUSES.index(s.status), key=f"status_{s.id}")
            if st.button("Update", key=f"update_{s.id}"):
                s.status = new_status
                db.commit()
                log_action(db, tid, st.session_state["user_id"], "Sample Status Updated", s.id, new_status)
                st.rerun()
