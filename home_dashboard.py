"""
Home Dashboard — 6-tab inventory & recipe analytics dashboard.
Loaded as the home page by streamlit_app.py via st.navigation.
"""
import streamlit as st
import pandas as pd
from utils import compute_dashboard_data

# ---------------------------------------------------------------------------
# LOAD DATA (cached)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def load_data():
    return compute_dashboard_data()

data = load_data()
ingredients = data["ingredient_list"]
recipes = data["recipe_data"]
cross_util = data["cross_util"]
cuisine_ingredients = data["cuisine_ingredients"]
supplier_analysis = data["supplier_analysis"]
cuisines = sorted(set(r["cuisine"] for r in recipes))

CUISINE_COLORS = {"American": "#ef4444", "Korean": "#f97316", "Indian": "#eab308",
                  "Chinese": "#22c55e", "Japanese": "#06b6d4", "Mexican": "#3b82f6", "Poke": "#a855f7"}

# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------

st.markdown("## ZwQ Inventory & Recipe Dashboard")
st.caption("35 Brands | 9 Cuisines | Powered by AI Teams")

# ---------------------------------------------------------------------------
# TABS
# ---------------------------------------------------------------------------

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Ingredient Master", "Recipe Management", "Food Costing & Margins",
    "Cross-Utilization", "Supplier Intelligence", "Analytics Dashboard"
])

# ==================== TAB 1: INGREDIENT MASTER ====================
with tab1:
    df_ing = pd.DataFrame(ingredients)
    cogs_count = len(df_ing[df_ing["affects_cogs"] == "Yes"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Ingredients", len(df_ing))
    c2.metric("Unique Suppliers", df_ing["supplier"].nunique())
    c3.metric("COGS Ingredients", cogs_count)
    c4.metric("Non-COGS Items", len(df_ing) - cogs_count)

    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
    with col1: search = st.text_input("Search", placeholder="Search ingredients...", key="ing_search", label_visibility="collapsed")
    with col2: cat_filter = st.selectbox("Category", ["All"] + sorted(df_ing["category"].dropna().unique().tolist()), key="ing_cat", label_visibility="collapsed")
    with col3: sup_filter = st.selectbox("Supplier", ["All"] + sorted(df_ing["supplier"].dropna().unique().tolist()), key="ing_sup", label_visibility="collapsed")
    with col4: cogs_filter = st.selectbox("COGS", ["All", "Yes", "No"], key="ing_cogs", label_visibility="collapsed")

    filtered = df_ing.copy()
    if search: filtered = filtered[filtered["ingredient"].str.contains(search, case=False, na=False)]
    if cat_filter != "All": filtered = filtered[filtered["category"] == cat_filter]
    if sup_filter != "All": filtered = filtered[filtered["supplier"] == sup_filter]
    if cogs_filter != "All": filtered = filtered[filtered["affects_cogs"] == cogs_filter]

    st.dataframe(filtered[["ingredient", "category", "sub_category", "uom", "price_per_unit", "supplier", "affects_cogs"]].rename(
        columns={"ingredient": "Ingredient", "category": "Category", "sub_category": "Sub-Category",
                 "uom": "UOM", "price_per_unit": "Price/Unit (AED)", "supplier": "Supplier", "affects_cogs": "COGS"}
    ), use_container_width=True, hide_index=True, height=500)

# ==================== TAB 2: RECIPE MANAGEMENT ====================
with tab2:
    total_sf = sum(1 for r in recipes if r["type"] == "semi_finished")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Recipes", len(recipes))
    c2.metric("Semi-Finished", total_sf)
    c3.metric("Finished Dishes", len(recipes) - total_sf)
    c4.metric("Cuisines", len(cuisines))

    col1, col2, col3 = st.columns([3, 2, 2])
    with col1: r_search = st.text_input("Search", placeholder="Search recipes...", key="r_search", label_visibility="collapsed")
    with col2: r_cuisine = st.selectbox("Cuisine", ["All"] + cuisines, key="r_cuisine", label_visibility="collapsed")
    with col3: r_type = st.selectbox("Type", ["All", "semi_finished", "finished"], key="r_type", label_visibility="collapsed")

    filtered_recipes = recipes
    if r_search: filtered_recipes = [r for r in filtered_recipes if r_search.lower() in r["dish_name"].lower()]
    if r_cuisine != "All": filtered_recipes = [r for r in filtered_recipes if r["cuisine"] == r_cuisine]
    if r_type != "All": filtered_recipes = [r for r in filtered_recipes if r["type"] == r_type]

    # Cuisine pills
    cuisine_counts = {}
    for r in recipes:
        cuisine_counts[r["cuisine"]] = cuisine_counts.get(r["cuisine"], 0) + 1
    st.markdown(" | ".join([f"**{c}**: {cuisine_counts.get(c, 0)}" for c in cuisines]))

    for r in filtered_recipes[:100]:
        badge = "SF" if r["type"] == "semi_finished" else "Finished"
        cogs_txt = f"COGS: AED {r['theoretical_cogs']:.2f}" if r["theoretical_cogs"] > 0 else ""
        cm_txt = f" | CM: {r['waterfall']['cm_pct']}%" if r.get("waterfall") else ""
        with st.expander(f"**{r['dish_name']}** [{badge}] — {r['cuisine']} / {r['category']} — {r['ingredient_count']} ing. {cogs_txt}{cm_txt}"):
            df_ings = pd.DataFrame(r["ingredients"])
            if not df_ings.empty:
                st.dataframe(df_ings[["ingredient", "quantity", "uom", "wastage_pct"]].rename(
                    columns={"ingredient": "Ingredient", "quantity": "Qty", "uom": "UOM", "wastage_pct": "Wastage %"}
                ), use_container_width=True, hide_index=True)
            if r["theoretical_cogs"] > 0:
                info = f"Theoretical COGS: **AED {r['theoretical_cogs']:.2f}**"
                if r["recorded_cogs"] > 0: info += f" | Recorded: AED {r['recorded_cogs']:.2f} | Variance: {r['variance_pct']}%"
                if r["sell_price"] > 0: info += f" | Sell: AED {r['sell_price']}"
                st.caption(info)

    if len(filtered_recipes) > 100:
        st.info(f"Showing first 100 of {len(filtered_recipes)} recipes. Use filters to narrow down.")

# ==================== TAB 3: FOOD COSTING & MARGINS ====================
with tab3:
    recipes_with_sell = [r for r in recipes if r["sell_price"] > 0 and r.get("waterfall")]
    food_costs = [(r["theoretical_cogs"] / r["sell_price"] * 100) for r in recipes_with_sell if r["sell_price"] > 0]
    avg_fc = round(sum(food_costs) / len(food_costs), 1) if food_costs else 0
    cms = [r["waterfall"]["cm_pct"] for r in recipes_with_sell]
    avg_cm = round(sum(cms) / len(cms), 1) if cms else 0
    below_target = sum(1 for c in cms if c < 20)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Avg Food Cost %", f"{avg_fc}%")
    c2.metric("Avg CM%", f"{avg_cm}%")
    c3.metric("Below 20% CM", below_target)
    c4.metric("Priced Dishes", len(recipes_with_sell))

    col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
    with col1: c_search = st.text_input("Search", placeholder="Search dishes...", key="c_search", label_visibility="collapsed")
    with col2: c_cuisine = st.selectbox("Cuisine", ["All"] + cuisines, key="c_cuisine", label_visibility="collapsed")
    with col3: c_cm = st.selectbox("CM%", ["All", ">=20% (On Target)", "15-20% (Watch)", "<15% (Critical)"], key="c_cm", label_visibility="collapsed")
    with col4: c_var = st.selectbox("Variance", ["All", ">5% (Flag)"], key="c_var", label_visibility="collapsed")

    filtered_costing = recipes_with_sell
    if c_search: filtered_costing = [r for r in filtered_costing if c_search.lower() in r["dish_name"].lower()]
    if c_cuisine != "All": filtered_costing = [r for r in filtered_costing if r["cuisine"] == c_cuisine]
    if c_cm == ">=20% (On Target)": filtered_costing = [r for r in filtered_costing if r["waterfall"]["cm_pct"] >= 20]
    elif c_cm == "15-20% (Watch)": filtered_costing = [r for r in filtered_costing if 15 <= r["waterfall"]["cm_pct"] < 20]
    elif c_cm == "<15% (Critical)": filtered_costing = [r for r in filtered_costing if r["waterfall"]["cm_pct"] < 15]
    if c_var == ">5% (Flag)": filtered_costing = [r for r in filtered_costing if r["variance_pct"] > 5]

    rows = []
    for r in filtered_costing:
        w = r["waterfall"]
        rows.append({
            "Dish": r["dish_name"], "Cuisine": r["cuisine"],
            "Menu Price": w["menu_price"], "Discount": w["discount"],
            "Net Income": w["net_income"], "COGS (Calc)": r["theoretical_cogs"],
            "COGS (Rec)": r["recorded_cogs"] if r["recorded_cogs"] > 0 else None,
            "CM": w["cm"], "CM%": w["cm_pct"], "Variance%": r["variance_pct"] if r["variance_pct"] > 0 else None,
        })
    if rows:
        df_cost = pd.DataFrame(rows)
        st.dataframe(df_cost, use_container_width=True, hide_index=True, height=500)
    else:
        st.info("No dishes match the current filters.")

# ==================== TAB 4: CROSS-UTILIZATION ====================
with tab4:
    shared_all = sum(1 for c in cross_util if c["cuisine_count"] >= len(cuisines))
    multi = sum(1 for c in cross_util if c["cuisine_count"] >= 3)
    single = sum(1 for c in cross_util if c["cuisine_count"] == 1)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Shared Across All", shared_all)
    c2.metric("Multi-Cuisine (3+)", multi)
    c3.metric("Single-Cuisine", single)
    c4.metric("Total Unique", len(cross_util))

    left, right = st.columns(2)
    with left:
        st.subheader("Top Shared Ingredients (3+ cuisines)")
        shared = [c for c in cross_util if c["cuisine_count"] >= 3][:50]
        df_shared = pd.DataFrame(shared)
        if not df_shared.empty:
            df_shared["cuisines"] = df_shared["cuisines"].apply(lambda x: ", ".join(x))
            st.dataframe(df_shared[["ingredient", "cuisines", "recipe_count"]].rename(
                columns={"ingredient": "Ingredient", "cuisines": "Cuisines", "recipe_count": "Recipes"}
            ), use_container_width=True, hide_index=True, height=400)

    with right:
        st.subheader("Ingredients per Cuisine")
        cuisine_ing_counts = {c: len(ings) for c, ings in cuisine_ingredients.items()}
        df_ci = pd.DataFrame(list(cuisine_ing_counts.items()), columns=["Cuisine", "Ingredients"]).sort_values("Ingredients", ascending=False)
        st.bar_chart(df_ci.set_index("Cuisine"), height=300)

    st.subheader("Ingredient-Cuisine Matrix")
    matrix_search = st.text_input("Filter matrix", placeholder="Search ingredient...", key="matrix_search")
    matrix_data = cross_util[:100] if not matrix_search else [c for c in cross_util if matrix_search.lower() in c["ingredient"]]
    rows = []
    for c in matrix_data[:100]:
        row = {"Ingredient": c["ingredient"]}
        for cuisine in cuisines:
            row[cuisine] = "Y" if cuisine in c["cuisines"] else ""
        row["Total"] = c["cuisine_count"]
        rows.append(row)
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=400)

# ==================== TAB 5: SUPPLIER INTELLIGENCE ====================
with tab5:
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Suppliers", len(supplier_analysis))
    if supplier_analysis:
        c2.metric("Top Supplier", supplier_analysis[0]["supplier"][:30])
    avg_items = round(sum(s["ingredient_count"] for s in supplier_analysis) / max(len(supplier_analysis), 1), 1)
    c3.metric("Avg Items/Supplier", avg_items)

    left, right = st.columns(2)
    with left:
        st.subheader("Supplier Concentration (Top 15)")
        top15 = supplier_analysis[:15]
        df_sup = pd.DataFrame(top15)
        st.bar_chart(df_sup.set_index("supplier")["ingredient_count"], height=400)

    with right:
        st.subheader("Category Coverage")
        rows = [{"Supplier": s["supplier"], "Items": s["ingredient_count"],
                 "Categories": ", ".join(s["categories"])} for s in supplier_analysis]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=400)

# ==================== TAB 6: ANALYTICS DASHBOARD ====================
with tab6:
    recipes_with_wf = [r for r in recipes if r.get("waterfall")]
    food_costs_all = [(r["theoretical_cogs"] / r["sell_price"] * 100) for r in recipes_with_wf if r["sell_price"] > 0]
    avg_fc_all = round(sum(food_costs_all) / len(food_costs_all), 1) if food_costs_all else 0
    cms_all = [r["waterfall"]["cm_pct"] for r in recipes_with_wf]
    avg_cm_all = round(sum(cms_all) / len(cms_all), 1) if cms_all else 0
    below_all = sum(1 for c in cms_all if c < 20)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Recipes", len(recipes))
    c2.metric("Total Ingredients", len(ingredients))
    c3.metric("Avg Food Cost %", f"{avg_fc_all}%")
    c4.metric("Avg CM%", f"{avg_cm_all}%")
    c5.metric("Below Target", below_all)

    left, right = st.columns(2)
    with left:
        st.subheader("Recipes by Cuisine")
        cuisine_recipe_counts = {}
        for r in recipes:
            cuisine_recipe_counts[r["cuisine"]] = cuisine_recipe_counts.get(r["cuisine"], 0) + 1
        df_rc = pd.DataFrame(list(cuisine_recipe_counts.items()), columns=["Cuisine", "Recipes"]).sort_values("Recipes", ascending=False)
        st.bar_chart(df_rc.set_index("Cuisine"), height=300)

    with right:
        st.subheader("Avg CM% by Cuisine")
        cuisine_cms = {}
        for r in recipes_with_wf:
            cuisine_cms.setdefault(r["cuisine"], []).append(r["waterfall"]["cm_pct"])
        df_cm = pd.DataFrame([{"Cuisine": c, "Avg CM%": round(sum(v)/len(v), 1)} for c, v in cuisine_cms.items() if v])
        if not df_cm.empty:
            st.bar_chart(df_cm.set_index("Cuisine"), height=300)

    left, right = st.columns(2)
    with left:
        st.subheader("Top 10 Highest Margin Dishes")
        sorted_wf = sorted(recipes_with_wf, key=lambda x: x["waterfall"]["cm_pct"], reverse=True)
        top10 = [{"Dish": r["dish_name"], "Cuisine": r["cuisine"], "CM%": r["waterfall"]["cm_pct"],
                  "CM (AED)": r["waterfall"]["cm"]} for r in sorted_wf[:10]]
        st.dataframe(pd.DataFrame(top10), use_container_width=True, hide_index=True)

    with right:
        st.subheader("Bottom 10 Lowest Margin Dishes")
        bottom10 = [{"Dish": r["dish_name"], "Cuisine": r["cuisine"], "CM%": r["waterfall"]["cm_pct"],
                     "CM (AED)": r["waterfall"]["cm"]} for r in sorted_wf[-10:]]
        st.dataframe(pd.DataFrame(bottom10), use_container_width=True, hide_index=True)

    st.subheader("Food Cost Distribution")
    buckets = {"<15%": 0, "15-20%": 0, "20-25%": 0, "25-30%": 0, "30-35%": 0, ">35%": 0}
    for r in recipes_with_wf:
        if r["sell_price"] <= 0: continue
        fc = r["theoretical_cogs"] / r["sell_price"] * 100
        if fc < 15: buckets["<15%"] += 1
        elif fc < 20: buckets["15-20%"] += 1
        elif fc < 25: buckets["20-25%"] += 1
        elif fc < 30: buckets["25-30%"] += 1
        elif fc < 35: buckets["30-35%"] += 1
        else: buckets[">35%"] += 1
    df_fc = pd.DataFrame(list(buckets.items()), columns=["Range", "Dishes"])
    st.bar_chart(df_fc.set_index("Range"), height=300)
