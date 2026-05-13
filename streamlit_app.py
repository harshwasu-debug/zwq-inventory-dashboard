"""
ZwQ Inventory & Recipe Dashboard — Streamlit Multi-Page App Entrypoint

Uses st.navigation to organize 15 pages into 5 collapsible groups by workflow.
The actual home dashboard content lives in home_dashboard.py.
"""
import streamlit as st

# ---------------------------------------------------------------------------
# Pages — grouped by workflow (most-used groups listed first)
# ---------------------------------------------------------------------------

home = st.Page("home_dashboard.py", title="Inventory Dashboard", icon="🏠", default=True)

# Procurement workflow — supplier ordering & receiving
procurement_pages = [
    st.Page("pages/1_Invoice_Receiving.py",  title="Invoice Receiving", icon="🧾"),
    st.Page("pages/18_Delivery_Notes.py",    title="Delivery Notes",    icon="📦"),
    st.Page("pages/14_Create_PO.py",         title="Create PO",         icon="📝"),
    st.Page("pages/15_PO_History.py",        title="PO History",        icon="📜"),
    st.Page("pages/13_Suppliers.py",         title="Suppliers",         icon="🏢"),
]

# Inventory workflow — what's on hand, what's leaking, what's being produced
inventory_pages = [
    st.Page("pages/4_Stock_Levels.py",     title="Stock Levels",     icon="📦"),
    st.Page("pages/8_Stock_Count.py",      title="Stock Count",      icon="📋"),
    st.Page("pages/7_Wastage_Tracking.py", title="Wastage Tracking", icon="🗑️"),
    st.Page("pages/16_Production.py",      title="Production",       icon="🍳"),
    st.Page("pages/10_Slow_Moving.py",     title="Slow Moving",      icon="🐢"),
]

# Sales & Recipes — daily sales upload, recipe-to-brand mapping
sales_pages = [
    st.Page("pages/5_Sales_Upload.py",     title="Sales Upload",     icon="📊"),
    st.Page("pages/6_Brand_Recipe_Map.py", title="Brand Recipe Map", icon="🔗"),
    st.Page("pages/9_Variance_Report.py",  title="Variance Report",  icon="📉"),
]

# Pricing & Reports — periodic price hygiene + audit reporting
pricing_pages = [
    st.Page("pages/11_Refresh_Prices.py", title="Refresh Prices", icon="💰"),
    st.Page("pages/12_Price_Review.py",   title="Price Review",   icon="🔍"),
    st.Page("pages/2_Price_History.py",   title="Price History",  icon="📈"),
    st.Page("pages/3_Daily_Summary.py",   title="Daily Summary",  icon="📅"),
]

# Configuration
admin_pages = [
    st.Page("pages/17_Settings.py", title="Settings", icon="⚙️"),
]

# ---------------------------------------------------------------------------
# Build navigation
# ---------------------------------------------------------------------------

pg = st.navigation({
    "Home":                [home],
    "🛒 Procurement":      procurement_pages,
    "📦 Inventory":        inventory_pages,
    "📊 Sales & Recipes":  sales_pages,
    "💰 Pricing & Reports": pricing_pages,
    "⚙️ Admin":            admin_pages,
})

# Single page_config call for the whole app — individual pages may add their own icons
st.set_page_config(
    page_title="ZwQ Inventory & Recipe Dashboard",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

pg.run()
