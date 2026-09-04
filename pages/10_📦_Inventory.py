from datetime import datetime
import streamlit as st

from utils.session import get_db, require_login, current_tenant_id
from db.models import InventoryItem, InventoryTransaction

require_login()
db = get_db()
tid = current_tenant_id()

st.title("📦 Inventory")

tab_list, tab_add = st.tabs(["Inventory", "Add Item"])

with tab_add:
    with st.form("new_item_form", clear_on_submit=True):
        name = st.text_input("Item Name *")
        col1, col2 = st.columns(2)
        category = col1.text_input("Category")
        unit = col2.text_input("Unit", value="pcs")
        col3, col4 = st.columns(2)
        opening_stock = col3.number_input("Opening Stock", min_value=0.0, step=1.0)
        min_stock = col4.number_input("Minimum Stock Level", min_value=0.0, step=1.0)
        if st.form_submit_button("Add Item", type="primary"):
            if not name.strip():
                st.error("Name is required.")
            else:
                item = InventoryItem(tenant_id=tid, name=name.strip(), category=category, unit=unit,
                                      current_stock=opening_stock, min_stock=min_stock)
                db.add(item)
                db.commit()
                st.success(f"Item '{name}' added.")
                st.rerun()

with tab_list:
    items = db.query(InventoryItem).filter_by(tenant_id=tid).order_by(InventoryItem.name).all()
    low_stock = [i for i in items if i.current_stock <= i.min_stock]
    if low_stock:
        st.warning(f"⚠️ {len(low_stock)} item(s) at or below minimum stock: " + ", ".join(i.name for i in low_stock))

    if not items:
        st.info("No inventory items yet.")
    for item in items:
        badge = "🔴" if item.current_stock <= item.min_stock else "🟢"
        with st.expander(f"{badge} {item.name} — {item.current_stock} {item.unit} (min {item.min_stock})"):
            col1, col2, col3 = st.columns(3)
            txn_type = col1.selectbox("Type", ["IN", "OUT"], key=f"type_{item.id}")
            qty = col2.number_input("Quantity", min_value=0.0, step=1.0, key=f"qty_{item.id}")
            notes = col3.text_input("Notes", key=f"notes_{item.id}")
            if st.button("Update Stock", key=f"upd_{item.id}") and qty > 0:
                if txn_type == "OUT" and qty > item.current_stock:
                    st.error("Cannot remove more than available stock.")
                else:
                    db.add(InventoryTransaction(tenant_id=tid, item_id=item.id, txn_type=txn_type,
                                                 quantity=qty, date=datetime.utcnow(), notes=notes))
                    item.current_stock += qty if txn_type == "IN" else -qty
                    db.commit()
                    st.success("Stock updated.")
                    st.rerun()
