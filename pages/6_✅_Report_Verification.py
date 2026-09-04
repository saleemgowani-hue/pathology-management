from datetime import datetime
import streamlit as st
from sqlalchemy.orm import joinedload, selectinload

from utils.session import get_db, require_login, current_tenant_id
from utils.helpers import log_action
from utils.pdf_report import generate_report_pdf_bytes
from db.models import Sample, Report, Pathologist, TestOrder

require_login()
db = get_db()
tid = current_tenant_id()

st.title("✅ Report Verification")

completed_samples = (
    db.query(Sample)
    .options(
        joinedload(Sample.patient),
        joinedload(Sample.report),
        selectinload(Sample.orders).joinedload(TestOrder.test),
        selectinload(Sample.orders).selectinload(TestOrder.results),
    )
    .filter(Sample.tenant_id == tid, Sample.status == "Completed")
    .order_by(Sample.id.desc()).all()
)
pending = [s for s in completed_samples if s.report and s.report.status != "Locked"]
locked = [s for s in completed_samples if s.report and s.report.status == "Locked"]

pathologists = db.query(Pathologist).filter_by(tenant_id=tid, active=True).all()

tab_pending, tab_locked = st.tabs([f"Pending Verification ({len(pending)})", f"Verified Reports ({len(locked)})"])

with tab_pending:
    if not pending:
        st.info("No reports pending verification.")
    for s in pending:
        with st.expander(f"{s.sample_number} — {s.patient.name}"):
            for order in s.orders:
                st.markdown(f"**{order.test.name}**")
                for r in order.results:
                    flag_color = "🔴" if r.flag in ("High", "Critical") else ("🟡" if r.flag == "Low" else "🟢")
                    st.write(f"{flag_color} {r.parameter}: {r.result} {r.unit} (Ref: {r.reference_range}) — {r.flag}")

            pathologist_id = st.selectbox(
                "Pathologist", [None] + [p.id for p in pathologists],
                format_func=lambda x: "-- Select --" if x is None else next(p.name for p in pathologists if p.id == x),
                key=f"path_{s.id}",
            )
            remarks = st.text_area("Remarks", key=f"remarks_{s.id}")
            col1, col2 = st.columns(2)
            if col1.button("✅ Approve & Lock Report", key=f"approve_{s.id}", type="primary"):
                report = s.report
                report.pathologist_id = pathologist_id
                report.verified_by = st.session_state["user_id"]
                report.verified_at = datetime.utcnow()
                report.remarks = remarks
                report.status = "Locked"
                db.commit()
                log_action(db, tid, st.session_state["user_id"], "Report Verified & Locked", report.id, s.sample_number)
                st.success("Report verified and locked.")
                st.rerun()
            if col2.button("↩️ Reject / Send Back", key=f"rejectrpt_{s.id}"):
                s.status = "Processing"
                db.commit()
                st.warning("Sent back for re-checking.")
                st.rerun()

with tab_locked:
    if not locked:
        st.info("No verified reports yet.")
    for s in locked:
        with st.expander(f"{s.sample_number} — {s.patient.name} (Verified)"):
            # PDF generation is real work (reportlab layout) -- only do it
            # when this specific report is asked for, and cache the bytes
            # for the rest of the session so re-rendering this page doesn't
            # regenerate every locked report's PDF on every rerun.
            cache_key = f"pdf_bytes_{s.id}"
            if cache_key not in st.session_state:
                if st.button("📄 Prepare PDF", key=f"prep_{s.id}"):
                    st.session_state[cache_key] = generate_report_pdf_bytes(db, tid, s)
                    st.rerun()
            else:
                st.download_button("⬇️ Download PDF Report", data=st.session_state[cache_key],
                                    file_name=f"{s.sample_number}_report.pdf", mime="application/pdf",
                                    key=f"dl_{s.id}")
