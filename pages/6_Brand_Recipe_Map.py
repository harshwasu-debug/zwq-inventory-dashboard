"""
Brand Recipe Map — Link brand menu items (including modifiers) to recipes.
This is the bridge between Deliverect menus and the recipe/costing system.
"""
import streamlit as st
import pandas as pd
import os, sys
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (load_brand_recipe_map, save_brand_recipe_map, load_brand_menus,
                   load_all_recipes, load_canonical_prices_raw, BASE_DIR, load_json)

st.set_page_config(page_title="Brand Recipe Map", page_icon="🔗", layout="wide")
st.markdown("## Brand Recipe Map")
st.caption("Link brand menu items to recipes for stock depletion and costing")

# ---------------------------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def get_brand_menus():
    return load_brand_menus()

@st.cache_data(ttl=60)
def get_all_recipes():
    return load_all_recipes()

@st.cache_data(ttl=60)
def get_ingredient_list():
    data = load_canonical_prices_raw()
    return sorted([i["ingredient"] for i in data.get("items", [])])

brand_menus = get_brand_menus()
all_recipes = get_all_recipes()
ingredient_list = get_ingredient_list()
brm = load_brand_recipe_map()

# Build recipe name list for dropdowns
recipe_names = ["(none)"] + sorted(set(r["dish_name"] for r in all_recipes))
recipe_lookup = {r["dish_name"]: r for r in all_recipes}

# Build existing mapping index
existing_map = {}  # (brand_lower, item_lower) -> mapping
for m in brm.get("mappings", []):
    key = (m["brand"].strip().lower(), m["menu_item"].strip().lower())
    existing_map[key] = m

# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------

brands = sorted(brand_menus.keys())
total_items = sum(len(b.get("products", [])) for b in brand_menus.values())
mapped_count = len(brm.get("mappings", []))

c1, c2, c3, c4 = st.columns(4)
c1.metric("Brands", len(brands))
c2.metric("Total Menu Items", total_items)
c3.metric("Mapped", mapped_count)
c4.metric("Unmapped", total_items - mapped_count)

# ---------------------------------------------------------------------------
# BRAND SELECTOR
# ---------------------------------------------------------------------------

selected_brand = st.selectbox("Select Brand", ["(choose a brand)"] + brands)

if selected_brand == "(choose a brand)":
    st.info("Select a brand to start mapping menu items to recipes.")

    # Show summary of all brands
    rows = []
    for brand_name in brands:
        products = brand_menus[brand_name].get("products", [])
        mapped = sum(1 for p in products if (brand_name.lower(), p["name"].strip().lower()) in existing_map)
        rows.append({"Brand": brand_name, "Menu Items": len(products), "Mapped": mapped,
                     "Unmapped": len(products) - mapped, "Coverage": f"{mapped/max(len(products),1)*100:.0f}%"})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.stop()

# ---------------------------------------------------------------------------
# BRAND MENU ITEMS
# ---------------------------------------------------------------------------

products = brand_menus[selected_brand].get("products", [])
st.markdown(f"### {selected_brand} — {len(products)} menu items")

# Auto-map button
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("Auto-Map All", type="primary"):
        auto_mapped = 0
        for product in products:
            key = (selected_brand.lower(), product["name"].strip().lower())
            if key in existing_map:
                continue  # Already mapped

            # Fuzzy match product name against recipe names
            best_score, best_recipe = 0, None
            product_lower = product["name"].strip().lower()
            for r in all_recipes:
                recipe_lower = r["dish_name"].strip().lower()
                score = SequenceMatcher(None, product_lower, recipe_lower).ratio()
                if score > best_score:
                    best_score = score
                    best_recipe = r
            if best_score >= 0.5 and best_recipe:
                new_mapping = {
                    "brand": selected_brand,
                    "menu_item": product["name"],
                    "plu": product.get("plu", ""),
                    "recipe_code": best_recipe.get("recipe_code", ""),
                    "recipe_name": best_recipe["dish_name"],
                    "cuisine": best_recipe.get("cuisine", ""),
                    "modifiers": [],
                    "auto_matched": True,
                    "match_score": round(best_score, 3),
                }
                brm["mappings"].append(new_mapping)
                existing_map[key] = new_mapping
                auto_mapped += 1

        if auto_mapped > 0:
            save_brand_recipe_map(brm)
            st.success(f"Auto-mapped {auto_mapped} items. Review and correct below.")
            st.rerun()
        else:
            st.info("All items are already mapped or no matches found above 50% confidence.")

with col2:
    st.caption("Auto-map uses fuzzy name matching. Review results and correct any wrong matches.")

# ---------------------------------------------------------------------------
# ITEM-BY-ITEM MAPPING
# ---------------------------------------------------------------------------

st.divider()

# Track changes
changes_made = False

for i, product in enumerate(products):
    pname = product["name"].strip()
    plu = product.get("plu", "")
    has_mods = product.get("has_customizations", False)
    key = (selected_brand.lower(), pname.lower())
    current_mapping = existing_map.get(key)

    # Current recipe match
    current_recipe = "(none)"
    if current_mapping:
        current_recipe = current_mapping.get("recipe_name", "(none)")

    # Find default index
    if current_recipe in recipe_names:
        default_idx = recipe_names.index(current_recipe)
    else:
        default_idx = 0

    cols = st.columns([4, 4, 1])
    with cols[0]:
        st.text(f"{pname}")
        st.caption(f"PLU: {plu}" + (" | Has modifiers" if has_mods else ""))
    with cols[1]:
        selected_recipe = st.selectbox(
            f"Recipe for {pname}", options=recipe_names, index=default_idx,
            key=f"recipe_{selected_brand}_{i}", label_visibility="collapsed"
        )
    with cols[2]:
        if current_mapping and current_mapping.get("match_score"):
            st.caption(f"{current_mapping['match_score']:.0%}")

    # Handle modifier mapping if item has customizations
    if has_mods and selected_recipe != "(none)" and current_mapping:
        mod_refs = product.get("modifier_group_refs", [])
        if mod_refs:
            with st.expander(f"Modifier ingredients for {pname}", expanded=False):
                current_mods = current_mapping.get("modifiers", [])
                st.caption("Add ingredient adjustments for each modifier (e.g., 'Extra Cheese' adds 30g Cheddar)")

                # Simple modifier form
                num_mods = st.number_input(f"Number of modifiers for {pname}", min_value=0, max_value=20,
                                           value=len(current_mods), key=f"num_mods_{selected_brand}_{i}")
                new_mods = []
                for mi in range(int(num_mods)):
                    existing_mod = current_mods[mi] if mi < len(current_mods) else {}
                    mc = st.columns([3, 3, 1, 1])
                    with mc[0]:
                        mod_name = st.text_input("Modifier", value=existing_mod.get("modifier_name", ""),
                                                 key=f"mod_name_{selected_brand}_{i}_{mi}",
                                                 placeholder="e.g. Extra Cheese", label_visibility="collapsed")
                    with mc[1]:
                        existing_adds = existing_mod.get("additional_ingredients", [])
                        mod_ing = st.selectbox("Ingredient", ["(none)"] + ingredient_list,
                                               index=(ingredient_list.index(existing_adds[0]["ingredient"]) + 1
                                                      if existing_adds and existing_adds[0]["ingredient"] in ingredient_list else 0),
                                               key=f"mod_ing_{selected_brand}_{i}_{mi}", label_visibility="collapsed")
                    with mc[2]:
                        mod_qty = st.number_input("Qty (Kg/L/Pc)", min_value=0.0,
                                                  value=existing_adds[0]["quantity"] if existing_adds else 0.0,
                                                  step=0.01, key=f"mod_qty_{selected_brand}_{i}_{mi}",
                                                  label_visibility="collapsed")
                    with mc[3]:
                        mod_uom = st.selectbox("UOM", ["Kg", "L", "Piece"],
                                               key=f"mod_uom_{selected_brand}_{i}_{mi}", label_visibility="collapsed")
                    if mod_name and mod_ing != "(none)" and mod_qty > 0:
                        new_mods.append({
                            "modifier_name": mod_name,
                            "modifier_plu": "",
                            "additional_ingredients": [{"ingredient": mod_ing, "quantity": mod_qty, "uom": mod_uom}]
                        })

                # Store mods temporarily
                if current_mapping:
                    current_mapping["modifiers"] = new_mods

    # Check if selection changed
    if selected_recipe != current_recipe:
        changes_made = True
        if selected_recipe == "(none)":
            # Remove mapping
            if key in existing_map:
                brm["mappings"] = [m for m in brm["mappings"]
                                   if not (m["brand"].lower() == selected_brand.lower() and
                                           m["menu_item"].strip().lower() == pname.lower())]
                del existing_map[key]
        else:
            # Add/update mapping
            recipe_info = recipe_lookup.get(selected_recipe, {})
            new_mapping = {
                "brand": selected_brand,
                "menu_item": pname,
                "plu": plu,
                "recipe_code": recipe_info.get("recipe_code", ""),
                "recipe_name": selected_recipe,
                "cuisine": recipe_info.get("cuisine", ""),
                "modifiers": current_mapping.get("modifiers", []) if current_mapping else [],
            }
            # Remove old if exists
            brm["mappings"] = [m for m in brm["mappings"]
                               if not (m["brand"].lower() == selected_brand.lower() and
                                       m["menu_item"].strip().lower() == pname.lower())]
            brm["mappings"].append(new_mapping)
            existing_map[key] = new_mapping

# Save button
st.divider()
if st.button("Save All Mappings", type="primary", use_container_width=True):
    save_brand_recipe_map(brm)
    st.success(f"Saved {len(brm['mappings'])} mappings!")
    st.cache_data.clear()
    st.rerun()
