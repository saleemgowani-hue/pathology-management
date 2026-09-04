from datetime import date
import streamlit as st

from utils.session import get_db, require_login, current_tenant_id
from db.models import Staff, Attendance

require_login()
db = get_db()
tid = current_tenant_id()

st.title("👥 Staff & Attendance")

tab_staff, tab_add, tab_att = st.tabs(["Staff List", "Add Staff", "Attendance"])

with tab_add:
    with st.form("new_staff_form", clear_on_submit=True):
        name = st.text_input("Name *")
        col1, col2 = st.columns(2)
        designation = col1.text_input("Designation")
        mobile = col2.text_input("Mobile")
        col3, col4 = st.columns(2)
        joining_date = col3.date_input("Joining Date", value=date.today())
        salary = col4.number_input("Salary", min_value=0.0, step=500.0)
        if st.form_submit_button("Add Staff", type="primary"):
            if not name.strip():
                st.error("Name is required.")
            else:
                count = db.query(Staff).filter_by(tenant_id=tid).count() + 1
                s = Staff(tenant_id=tid, staff_code=f"STF{count:04d}", name=name.strip(), designation=designation,
                          mobile=mobile, joining_date=joining_date, salary=salary, status="Active")
                db.add(s)
                db.commit()
                st.success(f"Staff '{name}' added.")
                st.rerun()

with tab_staff:
    staff_list = db.query(Staff).filter_by(tenant_id=tid).order_by(Staff.name).all()
    if not staff_list:
        st.info("No staff added yet.")
    else:
        import pandas as pd
        df = pd.DataFrame([{"Code": s.staff_code, "Name": s.name, "Designation": s.designation,
                             "Mobile": s.mobile, "Salary": s.salary, "Status": s.status} for s in staff_list])
        st.dataframe(df, use_container_width=True, hide_index=True)

with tab_att:
    staff_list = db.query(Staff).filter_by(tenant_id=tid, status="Active").order_by(Staff.name).all()
    sel_date = st.date_input("Date", value=date.today())
    if not staff_list:
        st.info("No active staff.")
    else:
        existing = {a.staff_id: a.status for a in db.query(Attendance).filter_by(tenant_id=tid, date=sel_date).all()}
        statuses = {}
        for s in staff_list:
            statuses[s.id] = st.radio(s.name, ["Present", "Absent", "Leave", "Half Day"],
                                       index=["Present", "Absent", "Leave", "Half Day"].index(existing.get(s.id, "Present")),
                                       horizontal=True, key=f"att_{s.id}")
        if st.button("Save Attendance", type="primary"):
            for s in staff_list:
                rec = db.query(Attendance).filter_by(tenant_id=tid, staff_id=s.id, date=sel_date).first()
                if rec:
                    rec.status = statuses[s.id]
                else:
                    db.add(Attendance(tenant_id=tid, staff_id=s.id, date=sel_date, status=statuses[s.id]))
            db.commit()
            st.success("Attendance saved.")
