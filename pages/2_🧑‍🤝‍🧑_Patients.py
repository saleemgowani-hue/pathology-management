from datetime import date
import streamlit as st

from utils.session import get_db, require_login, current_tenant_id
from utils.helpers import next_patient_code, log_action
from db.models import Patient, Doctor, Sample, Bill

st.set_page_config(page_title="Patients", page_icon="🧑‍🤝‍🧑", layout="wide")
require_login()
db = get_db()
tid = current_tenant_id()

st.title("🧑‍🤝‍🧑 Patients")

tab_list, tab_new = st.tabs(["Patient List", "Register New Patient"])

with tab_new:
    doctors = db.query(Doctor).filter_by(tenant_id=tid, active=True).order_by(Doctor.name).all()
    with st.form("new_patient_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        name = col1.text_input("Full Name *")
        age = col2.number_input("Age", min_value=0, max_value=120, value=30)
        gender = col3.selectbox("Gender", ["Male", "Female", "Other"])
        col4, col5 = st.columns(2)
        mobile = col4.text_input("Mobile Number")
        email = col5.text_input("Email")
        address = st.text_input("Address")
        col6, col7 = st.columns(2)
        doctor_id = col6.selectbox("Referring Doctor", [None] + [d.id for d in doctors],
                                    format_func=lambda x: "-- None --" if x is None else next(d.name for d in doctors if d.id == x))
        patient_type = col7.selectbox("Patient Type", ["New", "Existing"])
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Register Patient", type="primary")
        if submitted:
            if not name.strip():
                st.error("Patient name is required.")
            else:
                code = next_patient_code(db, tid)
                p = Patient(tenant_id=tid, patient_code=code, name=name.strip(), age=age, gender=gender,
                            mobile=mobile.strip(), email=email.strip(), address=address.strip(),
                            referring_doctor_id=doctor_id, patient_type=patient_type,
                            registration_date=date.today(), notes=notes.strip())
                db.add(p)
                db.commit()
                log_action(db, tid, st.session_state["user_id"], "Patient Created", p.id, p.name)
                st.success(f"Patient registered — ID: {code}")
                st.rerun()

with tab_list:
    q = st.text_input("Search by name, mobile, or patient ID", key="patient_search")
    query = db.query(Patient).filter(Patient.tenant_id == tid)
    if q:
        like = f"%{q}%"
        query = query.filter((Patient.name.ilike(like)) | (Patient.mobile.ilike(like)) | (Patient.patient_code.ilike(like)))
    patients = query.order_by(Patient.id.desc()).limit(300).all()

    if not patients:
        st.info("No patients found.")
    for p in patients:
        with st.expander(f"{p.patient_code} — {p.name} ({p.age}/{p.gender})"):
            col1, col2 = st.columns(2)
            col1.write(f"**Mobile:** {p.mobile or '-'}")
            col1.write(f"**Doctor:** {p.referring_doctor.name if p.referring_doctor else '-'}")
            col1.write(f"**Type:** {p.patient_type}")
            col2.write(f"**Registered:** {p.registration_date}")
            col2.write(f"**Address:** {p.address or '-'}")
            if p.notes:
                st.write(f"**Notes:** {p.notes}")

            samples = db.query(Sample).filter_by(tenant_id=tid, patient_id=p.id).order_by(Sample.id.desc()).all()
            bills = db.query(Bill).filter_by(tenant_id=tid, patient_id=p.id).order_by(Bill.id.desc()).all()
            if samples:
                st.write("**Samples:**", ", ".join(f"{s.sample_number} ({s.status})" for s in samples))
            if bills:
                st.write("**Bills:**", ", ".join(f"{b.receipt_number} (₹{b.net_amount:.0f}, due ₹{b.due_amount:.0f})" for b in bills))
