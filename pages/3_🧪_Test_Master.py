import streamlit as st

from utils.session import get_db, require_login, current_tenant_id
from utils.helpers import log_action
from db.models import TestItem, TestProfile, TestProfileItem

require_login()
db = get_db()
tid = current_tenant_id()

CATEGORIES = ["Hematology", "Biochemistry", "Clinical Pathology", "Serology", "Immunology",
              "Microbiology", "Hormones", "Lipid Profile", "Liver Function Test",
              "Kidney Function Test", "Thyroid Profile", "Diabetes Tests"]

st.title("🧪 Test Master")

tab_tests, tab_new, tab_profiles = st.tabs(["Tests", "Add Test", "Packages"])

with tab_new:
    with st.form("new_test_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        test_code = col1.text_input("Test Code *")
        name = col2.text_input("Test Name *")
        col3, col4 = st.columns(2)
        category = col3.selectbox("Category", CATEGORIES)
        sample_type = col4.text_input("Sample Type")
        col5, col6, col7 = st.columns(3)
        normal_range = col5.text_input("Normal Range")
        unit = col6.text_input("Unit")
        price = col7.number_input("Price *", min_value=0.0, step=10.0)
        col8, col9 = st.columns(2)
        department = col8.text_input("Department")
        method = col9.text_input("Method")
        turnaround = st.text_input("Turnaround Time", value="Same day")
        submitted = st.form_submit_button("Add Test", type="primary")
        if submitted:
            if not test_code.strip() or not name.strip():
                st.error("Test code and name are required.")
            elif db.query(TestItem).filter_by(tenant_id=tid, test_code=test_code.strip()).first():
                st.error("A test with this code already exists.")
            else:
                t = TestItem(tenant_id=tid, test_code=test_code.strip(), name=name.strip(), category=category,
                             sample_type=sample_type.strip(), normal_range=normal_range.strip(), unit=unit.strip(),
                             price=price, department=department.strip(), method=method.strip(),
                             turnaround_time=turnaround.strip(), active=True)
                db.add(t)
                db.commit()
                log_action(db, tid, st.session_state["user_id"], "Test Created", t.id, t.name)
                st.success(f"Test '{name}' added.")
                st.rerun()

with tab_tests:
    tests = db.query(TestItem).filter_by(tenant_id=tid).order_by(TestItem.name).all()
    if not tests:
        st.info("No tests yet — add one under the 'Add Test' tab.")
    else:
        import pandas as pd
        df = pd.DataFrame([{
            "Code": t.test_code, "Name": t.name, "Category": t.category, "Price": t.price,
            "Sample": t.sample_type, "TAT": t.turnaround_time, "Active": t.active,
        } for t in tests])
        st.dataframe(df, use_container_width=True, hide_index=True)

with tab_profiles:
    tests = db.query(TestItem).filter_by(tenant_id=tid, active=True).order_by(TestItem.name).all()
    st.markdown("##### Create a Package")
    with st.form("new_profile_form", clear_on_submit=True):
        pname = st.text_input("Package Name *")
        selected = st.multiselect("Included Tests", options=[t.id for t in tests],
                                   format_func=lambda x: next(t.name for t in tests if t.id == x))
        pprice = st.number_input("Package Price *", min_value=0.0, step=10.0)
        submitted = st.form_submit_button("Create Package", type="primary")
        if submitted:
            if not pname.strip() or not selected:
                st.error("Package name and at least one test are required.")
            else:
                prof = TestProfile(tenant_id=tid, name=pname.strip(), price=pprice, active=True)
                db.add(prof)
                db.flush()
                for tid_sel in selected:
                    db.add(TestProfileItem(profile_id=prof.id, test_id=tid_sel))
                db.commit()
                st.success(f"Package '{pname}' created.")
                st.rerun()

    st.markdown("##### Existing Packages")
    profiles = db.query(TestProfile).filter_by(tenant_id=tid).all()
    if profiles:
        # Batch-fetch every package's tests in two queries total instead
        # of two queries per package (was an N+1 pattern).
        profile_ids = [p.id for p in profiles]
        all_items = db.query(TestProfileItem).filter(TestProfileItem.profile_id.in_(profile_ids)).all()
        test_ids = {i.test_id for i in all_items}
        test_names_by_id = {t.id: t.name for t in db.query(TestItem).filter(TestItem.id.in_(test_ids)).all()} if test_ids else {}
        test_ids_by_profile = {}
        for i in all_items:
            test_ids_by_profile.setdefault(i.profile_id, []).append(i.test_id)

        for p in profiles:
            names = [test_names_by_id[t] for t in test_ids_by_profile.get(p.id, []) if t in test_names_by_id]
            st.write(f"**{p.name}** — ₹{p.price:.0f} — {', '.join(names)}")
