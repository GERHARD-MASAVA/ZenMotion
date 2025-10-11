# app/app.py
import streamlit as st
import pandas as pd
import sqlalchemy as sa
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import datetime
import io
import os

# ---------- config ----------
DB_PATH = os.environ.get("INVENTORY_DB", "inventory.db")
ENGINE = sa.create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
Base = declarative_base()
SessionLocal = sessionmaker(bind=ENGINE)
# ----------------------------

# ---------- models ----------
class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    sku = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, default="")
    unit = Column(String, default="")
    location = Column(String, default="")
    cost = Column(Float, default=0.0)
    qty_on_hand = Column(Integer, default=0)
    reorder_level = Column(Integer, default=0)
    notes = Column(Text, default="")

class StocktakeSession(Base):
    __tablename__ = "stocktake_sessions"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    counts = relationship("StocktakeCount", back_populates="session")

class StocktakeCount(Base):
    __tablename__ = "stocktake_counts"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("stocktake_sessions.id"))
    item_id = Column(Integer, ForeignKey("items.id"))
    counted_qty = Column(Integer, default=0)
    note = Column(Text, default="")
    session = relationship("StocktakeSession", back_populates="counts")
# ----------------------------

# create tables
Base.metadata.create_all(ENGINE)

# ---------- helpers ----------
def get_session():
    return SessionLocal()

def items_df(db):
    items = db.query(Item).order_by(Item.category, Item.name).all()
    rows = []
    for i in items:
        rows.append({
            "id": i.id,
            "sku": i.sku,
            "name": i.name,
            "category": i.category,
            "unit": i.unit,
            "location": i.location,
            "cost": i.cost,
            "qty_on_hand": i.qty_on_hand,
            "reorder_level": i.reorder_level,
            "notes": i.notes
        })
    return pd.DataFrame(rows)

def import_csv_to_db(db, df):
    # expected columns: sku, name, category, unit, location, cost, qty_on_hand, reorder_level, notes
    for _, row in df.iterrows():
        sku = str(row.get("sku", "")).strip()
        if sku == "":
            continue
        existing = db.query(Item).filter(Item.sku == sku).first()
        if existing:
            # update
            existing.name = row.get("name", existing.name)
            existing.category = row.get("category", existing.category)
            existing.unit = row.get("unit", existing.unit)
            existing.location = row.get("location", existing.location)
            existing.cost = float(row.get("cost", existing.cost) or existing.cost)
            existing.qty_on_hand = int(row.get("qty_on_hand", existing.qty_on_hand) or existing.qty_on_hand)
            existing.reorder_level = int(row.get("reorder_level", existing.reorder_level) or existing.reorder_level)
            existing.notes = row.get("notes", existing.notes)
        else:
            itm = Item(
                sku=sku,
                name=row.get("name", ""),
                category=row.get("category", ""),
                unit=row.get("unit", ""),
                location=row.get("location", ""),
                cost=float(row.get("cost", 0.0) or 0.0),
                qty_on_hand=int(row.get("qty_on_hand", 0) or 0),
                reorder_level=int(row.get("reorder_level", 0) or 0),
                notes=row.get("notes", "")
            )
            db.add(itm)
    db.commit()

def export_items_csv(db):
    df = items_df(db)
    return df

# Stocktake helpers
def create_stocktake_session(db, name):
    s = StocktakeSession(name=name)
    db.add(s); db.commit(); db.refresh(s)
    return s

def add_count(db, session_id, item_id, counted_qty, note=""):
    c = StocktakeCount(session_id=session_id, item_id=item_id, counted_qty=counted_qty, note=note)
    db.add(c); db.commit(); db.refresh(c)
    return c
# ----------------------------

# ---------- UI ----------
st.set_page_config(page_title="Events & Supplies Stocktake", layout="wide")
st.title("Events & Supplies — Inventory & Stocktaking")

db = get_session()

menu = st.sidebar.selectbox("Menu", ["Dashboard", "Inventory", "Stocktake", "Import/Export", "Reports", "Settings"])

if menu == "Dashboard":
    st.header("Dashboard")
    df = items_df(db)
    st.metric("Total SKUs", len(df))
    total_items = int(df["qty_on_hand"].sum()) if not df.empty else 0
    st.metric("Total units on hand", total_items)
    low = df[df["qty_on_hand"] <= df["reorder_level"]] if not df.empty else pd.DataFrame() # Ensure 'low' is a DataFrame even if df is empty
    st.subheader("Low stock items")
    if low.empty:
        st.info("No items below reorder level.")
    else:
        st.dataframe(low)

elif menu == "Inventory":
    st.header("Inventory")
    df = items_df(db)
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Add new item")
        with st.form("add_item"):
            sku = st.text_input("SKU")
            name = st.text_input("Name")
            category = st.text_input("Category")
            unit = st.text_input("Unit (e.g., pcs, m, roll)")
            location = st.text_input("Location")
            cost = st.number_input("Cost per unit", min_value=0.0, value=0.0, step=0.1)
            qty_on_hand = st.number_input("Quantity on hand", min_value=0, value=0, step=1)
            reorder_level = st.number_input("Reorder level", min_value=0, value=0, step=1)
            notes = st.text_area("Notes")
            submit = st.form_submit_button("Add / Update")
            if submit:
                existing = db.query(Item).filter(Item.sku == sku).first()
                if existing:
                    existing.name = name
                    existing.category = category
                    existing.unit = unit
                    existing.location = location
                    existing.cost = cost
                    existing.qty_on_hand = int(qty_on_hand)
                    existing.reorder_level = int(reorder_level)
                    existing.notes = notes
                    db.commit()
                    st.success(f"Updated item SKU {sku}")
                else:
                    if sku.strip() == "" or name.strip() == "":
                        st.error("SKU and Name are required.")
                    else:
                        itm = Item(sku=sku, name=name, category=category, unit=unit,
                                   location=location, cost=cost, qty_on_hand=int(qty_on_hand),
                                   reorder_level=int(reorder_level), notes=notes)
                        db.add(itm); db.commit()
                        st.success(f"Added {name} ({sku})")
    with col2:
        st.subheader("Current inventory")
        if df.empty:
            st.write("No items yet.")
        else:
            sel = st.multiselect("Filter categories", options=sorted(df["category"].dropna().unique()), default=sorted(df["category"].dropna().unique()))
            if sel:
                df_view = df[df["category"].isin(sel)]
            else:
                df_view = df
            st.dataframe(df_view.reset_index(drop=True))
            with st.expander("Edit an item"):
                id_to_edit = st.number_input("Item ID", min_value=0, value=0, step=1)
                if id_to_edit:
                    itm = db.query(Item).filter(Item.id == int(id_to_edit)).first()
                    if not itm:
                        st.warning("No item with that ID.")
                    else:
                        name = st.text_input("Name", value=itm.name)
                        sku = st.text_input("SKU", value=itm.sku)
                        category = st.text_input("Category", value=itm.category)
                        unit = st.text_input("Unit", value=itm.unit)
                        location = st.text_input("Location", value=itm.location)
                        cost = st.number_input("Cost per unit", value=float(itm.cost))
                        qty_on_hand = st.number_input("Quantity on hand", value=int(itm.qty_on_hand))
                        reorder_level = st.number_input("Reorder level", value=int(itm.reorder_level))
                        notes = st.text_area("Notes", value=itm.notes)
                        if st.button("Save changes"):
                            itm.name = name; itm.sku=sku; itm.category=category; itm.unit=unit
                            itm.location=location; itm.cost=float(cost); itm.qty_on_hand=int(qty_on_hand)
                            itm.reorder_level=int(reorder_level); itm.notes=notes
                            db.commit()
                            st.success("Saved.")

                        if st.button("Delete item"):
                            db.delete(itm); db.commit()
                            st.success("Deleted item.")

elif menu == "Stocktake":
    st.header("Stocktake")
    st.write("Start a new stocktake session or continue an open one.")
    sessions = db.query(StocktakeSession).order_by(StocktakeSession.created_at.desc()).all()
    session_names = [f"{s.id} — {s.name} ({'completed' if s.completed_at else 'open'})" for s in sessions]
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Create session")
        name = st.text_input("Session name", value=f"Stocktake {datetime.date.today().isoformat()}")
        if st.button("Create session"):
            s = create_stocktake_session(db, name)
            st.success(f"Created session {s.id}")
    with col2:
        st.subheader("Open session")
        if sessions:
            sel = st.selectbox("Choose session", session_names)
            sid = int(sel.split(" — ")[0])
            session = db.query(StocktakeSession).get(sid)
            st.write(f"Session: {session.name} — created {session.created_at}")
            st.markdown("**Record counts**")
            df = items_df(db)
            if df.empty:
                st.info("No items in inventory.")
            else:
                # choose by SKU or ID
                row = st.selectbox("Pick item (SKU - Name)", options=[f"{r.sku} — {r.name} (id:{r.id})" for _, r in df.iterrows()])
                chosen_id = int(row.split("id:")[-1].strip(")"))
                counted = st.number_input("Counted quantity", min_value=0, value=0, step=1)
                note = st.text_input("Note (optional)")
                if st.button("Save count"):
                    add_count(db, session.id, chosen_id, int(counted), note)
                    st.success("Count saved.")
            st.subheader("Session counts")
            counts = db.query(StocktakeCount).filter(StocktakeCount.session_id == session.id).all()
            if counts:
                rows = []
                for c in counts:
                    itm = db.query(Item).get(c.item_id)
                    rows.append({
                        "item_id": itm.id,
                        "sku": itm.sku,
                        "name": itm.name,
                        "qty_on_hand": itm.qty_on_hand,
                        "counted_qty": c.counted_qty,
                        "variance": c.counted_qty - itm.qty_on_hand,
                        "note": c.note
                    })
                st.dataframe(pd.DataFrame(rows))
                if st.button("Apply adjustments (set qty_on_hand = counted)"):
                    for c in counts:
                        itm = db.query(Item).get(c.item_id)
                        itm.qty_on_hand = c.counted_qty
                    session.completed_at = datetime.datetime.utcnow()
                    db.commit()
                    st.success("Adjusted inventory and closed session.")
            else:
                st.write("No counts recorded yet.")
        else:
            st.info("No sessions exist yet. Create one on the left.")

elif menu == "Import/Export":
    st.header("Import / Export")
    st.subheader("Import CSV")
    st.write("CSV expected columns: sku, name, category, unit, location, cost, qty_on_hand, reorder_level, notes")
    uploaded = st.file_uploader("Upload CSV", type=["csv", "xlsx"])
    if uploaded:
        try:
            if uploaded.type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" or uploaded.name.endswith(".xlsx"):
                df = pd.read_excel(uploaded)
            else:
                df = pd.read_csv(uploaded)
            st.dataframe(df.head())
            if st.button("Import into DB"):
                import_csv_to_db(db, df)
                st.success("Imported. Refresh inventory to see changes.")
        except Exception as e:
            st.error(f"Error reading file: {e}")

    st.subheader("Export CSV")
    if st.button("Download inventory CSV"):
        out_df = export_items_csv(db)
        buf = io.StringIO()
        out_df.to_csv(buf, index=False)
        st.download_button("Download CSV", data=buf.getvalue(), file_name="inventory_export.csv", mime="text/csv")

elif menu == "Reports":
    st.header("Reports")
    df = items_df(db)
    if df.empty:
        st.write("No data.")
    else:
        st.subheader("Low stock (qty <= reorder_level)")
        low = df[df["qty_on_hand"] <= df["reorder_level"]]
        st.dataframe(low)
        st.subheader("Stock value by category")
        df["stock_value"] = df["qty_on_hand"] * df["cost"]
        cat = df.groupby("category")["stock_value"].sum().reset_index().sort_values("stock_value", ascending=False)
        st.dataframe(cat)
        st.metric("Total stock value", f"{df['stock_value'].sum():.2f}")

elif menu == "Settings":
    st.header("Settings")
    st.write("DB path:", DB_PATH)
    if st.button("Download sample CSV"):
        sample = pd.DataFrame([{
            "sku":"SKU001","name":"White chair cover","category":"Fabric","unit":"pcs","location":"Warehouse A","cost":2.5,"qty_on_hand":120,"reorder_level":20,"notes":"Polyester"
        },{
            "sku":"SKU002","name":"Fairy lights 5m","category":"Decor","unit":"pcs","location":"Warehouse B","cost":8.0,"qty_on_hand":50,"reorder_level":10,"notes":"Battery"}
        ])
        csv_buf = io.StringIO(); sample.to_csv(csv_buf, index=False)
        st.download_button("Download sample CSV", data=csv_buf.getvalue(), file_name="sample_inventory.csv", mime="text/csv")