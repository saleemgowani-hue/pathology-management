import streamlit as st
from sqlalchemy import func

from utils.session import get_db, require_login, current_tenant_id
from utils.helpers import log_action
from db.models import Doctor, Pathologist, Patient, Bill

st.set_page_config(page_title="Doctors & Pathologists", page_icon="👨‍⚕️", layout="wide")
require_login()
db = get_db()
tid = current_tenant_id()

st.title("👨‍⚕️ Doctors & Pathologists")

tab_doctors, tab_add_doctor, tab_path, tab_add_path = st.tabs(
    ["Doctors", "Add Doctor", "Pathologists", "Add Pathologist"]
)

with tab_add_doctor:
    with st.form("new_doctor_form", clear_on_submit=True):
        name = st.text_input("Doctor Name *")
        col1, col2 = st.columns(2)
        qualification = col1.text_input("Qualification")
        specialization = col2.text_input("Specialization")
        col3, col4 = st.columns(2)
        mobile = col3.text_input("Mobile")
        commission = col4.number_input("Commission %", min_value=0.0, max_value=100.0, step=1.0)
        if st.form_submit_button("Add Doctor", type="primary"):
            if not name.strip():
                st.error("Name is required.")
            else:
                d = Doctor(tenant_id=tid, name=name.strip(), qualification=qualification, specialization=specialization,
                           mobile=mobile, commission_percent=commission, active=True)
                db.add(d)
                db.commit()
                log_action(db, tid, st.session_state["user_id"], "Doctor Added", d.id, d.name)
                st.success(f"Doctor '{name}' added.")
                st.rerun()

with tab_doctors:
    doctors = db.query(Doctor).filter_by(tenant_id=tid).order_by(Doctor.name).all()
    if not doctors:
        st.info("No doctors added yet.")
    for d in doctors:
        patient_count = db.query(Patient).filter_by(tenant_id=tid, referring_doctor_id=d.id).count()
        revenue = db.query(func.sum(Bill.net_amount)).join(Patient).filter(
            Patient.referring_doctor_id == d.id, Bill.status == "Active", Bill.tenant_id == tid
        ).scalar() or 0
        st.write(f"**{d.name}** ({d.specialization or '-'}) — {patient_count} patients — ₹{revenue:.0f} revenue")

with tab_add_path:
    with st.form("new_path_form", clear_on_submit=True):
        pname = st.text_input("Pathologist Name *")
        col1, col2 = st.columns(2)
        pqual = col1.text_input("Qualification")
        preg = col2.text_input("Registration Number")
        pspec = st.text_input("Specialization")
        if st.form_submit_button("Add Pathologist", type="primary"):
            if not pname.strip():
                st.error("Name is required.")
            else:
                p = Pathologist(tenant_id=tid, name=pname.strip(), qualification=pqual,
                                 registration_number=preg, specialization=pspec, active=True)
                db.add(p)
                db.commit()
                st.success(f"Pathologist '{pname}' added.")
                st.rerun()

with tab_path:
    pathologists = db.query(Pathologist).filter_by(tenant_id=tid).order_by(Pathologist.name).all()
    if not pathologists:
        st.info("No pathologists added yet.")
    for p in pathologists:
        st.write(f"**{p.name}** — {p.qualification or '-'} — Reg: {p.registration_number or '-'}")
