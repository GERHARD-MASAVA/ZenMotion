%%writefile app.py
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# --- Firebase Setup ---
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# --- App Title ---
st.set_page_config(page_title="Wiro Ventures Stock System", page_icon="📦", layout="wide")
st.title("📦 Wiro Ventures Limited - Stock & Event Management System")

# --- Sidebar Navigation ---
page = st.sidebar.radio("Navigate", ["Add Item", "View Inventory", "Stock In/Out", "Event Tracker", "Reports"])

# --- Add Item Page ---
if page == "Add Item":
    st.header("➕ Add New Stock Item")
    name = st.text_input("Item Name")
    category = st.text_input("Category", "General")
    qty = st.number_input("Initial Quantity", 0, 1000, 1)
    cost = st.number_input("Unit Cost (Ksh)", 0.0, 100000.0, 0.0)

    if st.button("Save Item"):
        if name:
            db.collection("inventory").add({
                "name": name,
                "category": category,
                "qty": qty,
                "cost": cost,
                "timestamp": datetime.now()
            })
            st.success(f"{name} added successfully!")
        else:
            st.warning("Please enter an item name.")

# --- View Inventory ---
elif page == "View Inventory":
    st.header("📋 Current Inventory")
    items = db.collection("inventory").stream()
    data = []
    for i in items:
        item = i.to_dict()
        data.append(item)
    if data:
        st.dataframe(data, use_container_width=True)
    else:
        st.info("No items found in inventory.")

# --- Stock In / Out ---
elif page == "Stock In/Out":
    st.header("🔄 Update Stock Quantity")
    docs = db.collection("inventory").stream()
    choices = {doc.id: doc.to_dict()["name"] for doc in docs}
    if choices:
        selected = st.selectbox("Select Item", list(choices.values()))
        action = st.radio("Action", ["Stock In", "Stock Out"])
        amount = st.number_input("Quantity", 1, 1000, 1)

        # Find selected doc ID
        doc_id = [k for k, v in choices.items() if v == selected][0]
        doc_ref = db.collection("inventory").document(doc_id)
        doc = doc_ref.get().to_dict()

        if st.button("Apply Change"):
            new_qty = doc["qty"] + amount if action == "Stock In" else doc["qty"] - amount
            doc_ref.update({"qty": new_qty})
            db.collection("transactions").add({
                "item": selected,
                "action": action,
                "amount": amount,
                "timestamp": datetime.now()
            })
            st.success(f"{action} successful! New quantity: {new_qty}")
    else:
        st.warning("No items in inventory to update.")

# --- Event Tracker ---
elif page == "Event Tracker":
    st.header("🎉 Event Supplies Tracker")
    event_name = st.text_input("Event Name")
    item = st.text_input("Supplied Item")
    qty_used = st.number_input("Quantity Used", 1, 1000, 1)
    date = st.date_input("Event Date", datetime.now())

    if st.button("Record Event"):
        db.collection("events").add({
            "event_name": event_name,
            "item": item,
            "qty_used": qty_used,
            "date": str(date),
            "timestamp": datetime.now()
        })
        st.success(f"Event '{event_name}' recorded.")

    # View recent events
    st.subheader("Recent Events")
    events = db.collection("events").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(5).stream()
    for e in events:
        ev = e.to_dict()
        st.write(f"📅 {ev['event_name']} — {ev['item']} ({ev['qty_used']} units) on {ev['date']}")

# --- Reports Page ---
elif page == "Reports":
    st.header("📊 Reports Overview")

    total_items = len(list(db.collection("inventory").stream()))
    total_events = len(list(db.collection("events").stream()))
    total_transactions = len(list(db.collection("transactions").stream()))

    st.metric("Total Items", total_items)
    st.metric("Events Tracked", total_events)
    st.metric("Stock Transactions", total_transactions)

    st.info("Coming soon: CSV export and charts.")
