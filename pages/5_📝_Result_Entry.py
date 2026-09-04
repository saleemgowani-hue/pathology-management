from datetime import datetime
import streamlit as st

from utils.session import get_db, require_login, current_tenant_id
from utils.helpers import log_action
from db.models import Sample, TestOrder, TestResult

require_login()
db = get_db()
tid = current_tenant_id()

FLAGS = ["Normal", "High", "Low", "Critical", "Positive", "Negative", "Abnormal"]

st.title("📝 Result Entry")

pending_samples = db.query(Sample).filter(
    Sample.tenant_id == tid, Sample.status.in_(["Collected", "Received", "Processing"])
).order_by(Sample.id.desc()).all()

if not pending_samples:
    st.info("No samples pending result entry.")

for s in pending_samples:
    orders = db.query(TestOrder).filter_by(tenant_id=tid, sample_id=s.id).all()
    with st.expander(f"{s.sample_number} — {s.patient.name} ({', '.join(o.test.name for o in orders)})"):
        for order in orders:
            st.markdown(f"**{order.test.name}**")
            existing = db.query(TestResult).filter_by(tenant_id=tid, test_order_id=order.id).first()
            col1, col2, col3, col4 = st.columns(4)
            param = col1.text_input("Parameter", value=existing.parameter if existing else order.test.name, key=f"param_{order.id}")
            result = col2.text_input("Result", value=existing.result if existing else "", key=f"result_{order.id}")
            unit = col3.text_input("Unit", value=existing.unit if existing else (order.test.unit or ""), key=f"unit_{order.id}")
            ref_range = col4.text_input("Reference Range", value=existing.reference_range if existing else (order.test.normal_range or ""), key=f"range_{order.id}")
            flag = st.selectbox("Flag", FLAGS, index=FLAGS.index(existing.flag) if existing and existing.flag in FLAGS else 0, key=f"flag_{order.id}")
            st.divider()

        if st.button("Save Results", key=f"save_{s.id}", type="primary"):
            for order in orders:
                db.query(TestResult).filter_by(tenant_id=tid, test_order_id=order.id).delete()
                db.add(TestResult(
                    tenant_id=tid, test_order_id=order.id,
                    parameter=st.session_state[f"param_{order.id}"],
                    result=st.session_state[f"result_{order.id}"],
                    unit=st.session_state[f"unit_{order.id}"],
                    reference_range=st.session_state[f"range_{order.id}"],
                    flag=st.session_state[f"flag_{order.id}"],
                    technician_id=st.session_state["user_id"],
                    result_datetime=datetime.utcnow(),
                ))
                order.status = "Completed"
            s.status = "Completed"
            db.commit()
            log_action(db, tid, st.session_state["user_id"], "Results Entered", s.id, s.sample_number)
            st.success("Results saved. Sample moved to Completed — ready for verification.")
            st.rerun()

        if st.button("Reject Sample", key=f"reject_{s.id}"):
            s.status = "Rejected"
            db.commit()
            log_action(db, tid, st.session_state["user_id"], "Sample Rejected", s.id)
            st.warning("Sample marked as rejected.")
            st.rerun()
