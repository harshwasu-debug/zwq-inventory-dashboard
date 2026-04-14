#!/usr/bin/env python3
"""
Build Inventory & Recipe Dashboard for ZwQ Cloud Kitchen Group
Reads all recipe, ingredient, and costing JSON files, normalizes data,
calculates metrics, and generates a self-contained HTML dashboard.
"""

import json
import os
import math
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COSTING_DIR = os.path.join(BASE_DIR, "Dish_Costing")
OUTPUT_FILE = os.path.join(BASE_DIR, "Inventory_Recipe_Dashboard.html")

# ---------------------------------------------------------------------------
# 1. LOAD DATA
# ---------------------------------------------------------------------------

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_canonical_prices():
    data = load_json(os.path.join(COSTING_DIR, "canonical_price_list.json"))
    prices = {}
    for item in data["items"]:
        prices[item["ingredient"].strip().lower()] = {
            "ingredient": item["ingredient"].strip(),
            "category": item.get("category", ""),
            "sub_category": item.get("sub_category", ""),
            "uom": item.get("uom", ""),
            "price_per_unit": item.get("price_per_unit", 0),
            "supplier": item.get("supplier", ""),
            "supplier_code": item.get("supplier_code", ""),
            "affects_cogs": item.get("affects_cogs", "Yes"),
        }
    return prices


def load_complete_costing():
    data = load_json(os.path.join(COSTING_DIR, "complete_dish_costing_final.json"))
    costing = {}
    cuisine_map = {
        "Korean Menu": "Korean", "American Menu": "American",
        "Mexican Menu": "Mexican", "Indian Menu": "Indian",
        "Japanese Menu": "Japanese", "Poke Menu": "Poke",
        "Chinese Menu": "Chinese", "Chinese Recipes": "Chinese",
    }
    for key, items in data.items():
        cuisine = cuisine_map.get(key, key)
        if not isinstance(items, list):
            continue
        for item in items:
            name = item.get("Dish Name", "").strip()
            if not name:
                continue
            cost = item.get("Cost (AED)", 0)
            sell = item.get("Sell Price (AED)", 0)
            if cost is None or (isinstance(cost, float) and math.isnan(cost)):
                cost = 0
            if sell is None or (isinstance(sell, float) and math.isnan(sell)):
                sell = 0
            costing[name.lower()] = {
                "dish": name,
                "cuisine": cuisine,
                "category": item.get("Category", ""),
                "recorded_cogs": round(float(cost), 2),
                "sell_price": round(float(sell), 2),
            }
    return costing


# ---------------------------------------------------------------------------
# 2. NORMALIZE RECIPES
# ---------------------------------------------------------------------------

def normalize_qty(qty, uom):
    """Convert quantity to Kg/L/Piece based on UOM."""
    uom_lower = str(uom).lower().strip()
    qty = float(qty) if qty else 0
    if uom_lower in ("g", "gm", "gms", "gram", "grams"):
        return qty / 1000.0, "Kg"
    elif uom_lower in ("ml", "millilitre"):
        return qty / 1000.0, "L"
    elif uom_lower in ("kg", "kgs"):
        return qty, "Kg"
    elif uom_lower in ("l", "ltr", "litre"):
        return qty, "L"
    elif uom_lower in ("piece", "pcs", "pc", "pieces", "nos", "each"):
        return qty, "Piece"
    else:
        return qty, uom


def parse_ingredients(raw_ingredients):
    """Normalize a list of ingredient dicts from any cuisine format."""
    result = []
    for ing in raw_ingredients:
        name = ing.get("ingredient", "").strip()
        if not name:
            continue
        # Try converted values first (Indian/Mexican have these)
        qty = ing.get("quantity_ep_converted") or ing.get("quantity_converted")
        uom = ing.get("uom_converted")
        if qty and uom:
            qty = float(qty)
        else:
            qty = ing.get("quantity_ep") or ing.get("ep_qty") or ing.get("quantity", 0)
            uom = ing.get("uom", "")
            qty, uom = normalize_qty(qty, uom)
        wastage = float(ing.get("wastage_pct", 0) or 0)
        is_sf = ing.get("is_semi_finished_ref", False)
        result.append({
            "ingredient": name,
            "quantity": round(qty, 4),
            "uom": uom,
            "wastage_pct": wastage,
            "is_semi_finished_ref": is_sf,
        })
    return result


def load_american_recipes():
    data = load_json(os.path.join(COSTING_DIR, "american_recipes.json"))
    recipes = {"semi_finished": [], "finished": []}
    for r in data.get("semi_finished_recipes", []):
        recipes["semi_finished"].append({
            "dish_name": r["dish_name"],
            "recipe_code": r.get("recipe_code", ""),
            "category": "Semi-Finished",
            "cuisine": "American",
            "type": "semi_finished",
            "ingredients": parse_ingredients(r.get("ingredients", [])),
        })
    for cat_name, dishes in data.get("finished_dishes_by_category", {}).items():
        for d in dishes:
            recipes["finished"].append({
                "dish_name": d["dish_name"],
                "recipe_code": d.get("recipe_code", ""),
                "category": cat_name,
                "cuisine": "American",
                "type": "finished",
                "ingredients": parse_ingredients(d.get("ingredients", [])),
            })
    return recipes


def load_korean_recipes():
    data = load_json(os.path.join(COSTING_DIR, "korean_recipes.json"))
    recipes = {"semi_finished": [], "finished": []}
    for r in data.get("semi_finished_recipes", []):
        recipes["semi_finished"].append({
            "dish_name": r["dish_name"],
            "recipe_code": r.get("recipe_code", ""),
            "category": "Semi-Finished",
            "cuisine": "Korean",
            "type": "semi_finished",
            "ingredients": parse_ingredients(r.get("ingredients", [])),
        })
    for r in data.get("finished_recipes", []):
        recipes["finished"].append({
            "dish_name": r["dish_name"],
            "recipe_code": r.get("recipe_code", ""),
            "category": r.get("category", ""),
            "cuisine": "Korean",
            "type": "finished",
            "ingredients": parse_ingredients(r.get("ingredients", [])),
        })
    return recipes


def load_indian_recipes():
    data = load_json(os.path.join(COSTING_DIR, "indian_recipes.json"))
    recipes = {"semi_finished": [], "finished": []}
    for r in data.get("semi_finished_recipes", []):
        recipes["semi_finished"].append({
            "dish_name": r["dish_name"],
            "recipe_code": r.get("recipe_code", ""),
            "category": "Semi-Finished",
            "cuisine": "Indian",
            "type": "semi_finished",
            "ingredients": parse_ingredients(r.get("ingredients", [])),
        })
    for r in data.get("finished_recipes", []):
        recipes["finished"].append({
            "dish_name": r["dish_name"],
            "recipe_code": r.get("recipe_code", ""),
            "category": r.get("category", ""),
            "cuisine": "Indian",
            "type": "finished",
            "ingredients": parse_ingredients(r.get("ingredients", [])),
        })
    return recipes


def load_chinese_recipes():
    data = load_json(os.path.join(COSTING_DIR, "chinese_recipes.json"))
    recipes = {"semi_finished": [], "finished": []}
    for cat in data.get("categories", []):
        cat_name = cat.get("category", "")
        for d in cat.get("dishes", []):
            recipes["finished"].append({
                "dish_name": d.get("dish", "").strip(),
                "recipe_code": d.get("recipe_code", ""),
                "category": cat_name,
                "cuisine": "Chinese",
                "type": "finished",
                "ingredients": parse_ingredients(d.get("ingredients", [])),
            })
    return recipes


def load_japanese_recipes():
    data = load_json(os.path.join(COSTING_DIR, "japanese_recipes.json"))
    recipes = {"semi_finished": [], "finished": []}
    for sheet_name, sheet in data.get("sheets", {}).items():
        if not isinstance(sheet, dict):
            continue
        dishes = sheet.get("dishes", [])
        is_sf = "semi" in sheet_name.lower()
        for d in dishes:
            rtype = "semi_finished" if is_sf else "finished"
            recipes[rtype].append({
                "dish_name": d.get("dish_name", ""),
                "recipe_code": d.get("recipe_code", ""),
                "category": d.get("category", sheet_name),
                "cuisine": "Japanese",
                "type": rtype,
                "ingredients": parse_ingredients(d.get("ingredients", [])),
            })
    return recipes


def load_mexican_recipes():
    data = load_json(os.path.join(COSTING_DIR, "mexican_recipes.json"))
    recipes = {"semi_finished": [], "finished": []}
    for r in data.get("semi_finished_recipes", []):
        recipes["semi_finished"].append({
            "dish_name": r["dish_name"],
            "recipe_code": r.get("recipe_code", ""),
            "category": "Semi-Finished",
            "cuisine": "Mexican",
            "type": "semi_finished",
            "ingredients": parse_ingredients(r.get("ingredients", [])),
        })
    # Mexican uses finished_recipes_by_category (dict of category -> dishes)
    for cat_name, dishes in data.get("finished_recipes_by_category", {}).items():
        for d in dishes:
            recipes["finished"].append({
                "dish_name": d.get("dish_name", ""),
                "recipe_code": d.get("recipe_code", ""),
                "category": cat_name,
                "cuisine": "Mexican",
                "type": "finished",
                "ingredients": parse_ingredients(d.get("ingredients", [])),
            })
    # Also try flat finished_dishes list as fallback
    for r in data.get("finished_dishes", []):
        recipes["finished"].append({
            "dish_name": r.get("dish_name", ""),
            "recipe_code": r.get("recipe_code", ""),
            "category": r.get("category", ""),
            "cuisine": "Mexican",
            "type": "finished",
            "ingredients": parse_ingredients(r.get("ingredients", [])),
        })
    return recipes


def load_poke_recipes():
    data = load_json(os.path.join(COSTING_DIR, "poke_recipes.json"))
    recipes = {"semi_finished": [], "finished": []}
    for sheet_name, sheet in data.get("sheets", {}).items():
        if not isinstance(sheet, dict):
            continue
        recs = sheet.get("recipes", [])
        is_sf = "semi" in sheet_name.lower() or "draft" in sheet_name.lower()
        for d in recs:
            rtype = "semi_finished" if is_sf else "finished"
            recipes[rtype].append({
                "dish_name": d.get("dish_name", ""),
                "recipe_code": d.get("recipe_code", ""),
                "category": d.get("category", sheet_name),
                "cuisine": "Poke",
                "type": rtype,
                "ingredients": parse_ingredients(d.get("ingredients", [])),
            })
    return recipes


def load_all_recipes():
    loaders = [
        load_american_recipes, load_korean_recipes, load_indian_recipes,
        load_chinese_recipes, load_japanese_recipes, load_mexican_recipes,
        load_poke_recipes,
    ]
    all_recipes = []
    for loader in loaders:
        data = loader()
        all_recipes.extend(data["semi_finished"])
        all_recipes.extend(data["finished"])
    return all_recipes


# ---------------------------------------------------------------------------
# 3. CALCULATE COGS & WATERFALL
# ---------------------------------------------------------------------------

def build_sf_cost_index(all_recipes, canonical_prices):
    """Pre-compute COGS for all semi-finished recipes so finished dishes can reference them."""
    sf_costs = {}
    for r in all_recipes:
        if r["type"] == "semi_finished":
            total = 0
            for ing in r["ingredients"]:
                name_key = ing["ingredient"].strip().lower()
                price_info = canonical_prices.get(name_key)
                if not price_info:
                    clean = name_key.replace("-sf", "").replace("- sf", "").strip()
                    price_info = canonical_prices.get(clean)
                if price_info and price_info["affects_cogs"] == "Yes":
                    qty = ing["quantity"]
                    wastage = ing["wastage_pct"]
                    effective_qty = qty * (1 + wastage / 100.0) if wastage > 0 else qty
                    total += effective_qty * price_info["price_per_unit"]
            sf_costs[r["dish_name"].strip().lower()] = round(total, 2)
    return sf_costs


def calc_recipe_cogs(recipe, canonical_prices, sf_costs=None):
    """Calculate theoretical COGS for a recipe using canonical prices and SF sub-recipe costs."""
    if sf_costs is None:
        sf_costs = {}
    total = 0
    matched = 0
    unmatched = []
    for ing in recipe["ingredients"]:
        name_key = ing["ingredient"].strip().lower()
        # Check if this ingredient is a semi-finished sub-recipe reference
        is_sf_ref = ing.get("is_semi_finished_ref", False) or name_key.endswith("- sf") or name_key.endswith("-sf") or " sf" in name_key
        # Try canonical price first
        price_info = canonical_prices.get(name_key)
        if not price_info:
            clean = name_key.replace("-sf", "").replace("- sf", "").strip()
            price_info = canonical_prices.get(clean)
        if price_info and price_info["affects_cogs"] == "Yes":
            qty = ing["quantity"]
            wastage = ing["wastage_pct"]
            effective_qty = qty * (1 + wastage / 100.0) if wastage > 0 else qty
            cost = effective_qty * price_info["price_per_unit"]
            total += cost
            matched += 1
        elif price_info and price_info["affects_cogs"] == "No":
            matched += 1
        elif is_sf_ref:
            # Look up SF sub-recipe cost — use quantity as a portion multiplier
            sf_key = name_key
            sf_cost = sf_costs.get(sf_key)
            if not sf_cost:
                # Try matching by partial name
                for sk, sv in sf_costs.items():
                    if name_key in sk or sk in name_key:
                        sf_cost = sv
                        break
            if sf_cost:
                # For SF refs, qty is typically a portion fraction of the batch
                qty = ing["quantity"]
                total += sf_cost * qty
                matched += 1
            else:
                unmatched.append(ing["ingredient"])
        else:
            unmatched.append(ing["ingredient"])
    return round(total, 2), matched, unmatched


def waterfall(menu_price, cogs):
    """ZwQ Commercial Pricing Model waterfall."""
    if menu_price <= 0:
        return {"menu_price": 0, "discount": 0, "net_after_discount": 0,
                "delivery": 0, "net_after_delivery": 0, "commission": 0,
                "net_income": 0, "cogs": cogs, "cm": -cogs, "cm_pct": 0}
    discount = min(menu_price / 2, 30)
    net_after_discount = menu_price - discount
    delivery = 4
    net_after_delivery = net_after_discount - delivery
    commission = net_after_delivery * 0.30
    net_income = net_after_delivery * 0.70
    cm = net_income - cogs
    cm_pct = (cm / menu_price * 100) if menu_price > 0 else 0
    return {
        "menu_price": round(menu_price, 2),
        "discount": round(discount, 2),
        "net_after_discount": round(net_after_discount, 2),
        "delivery": delivery,
        "net_after_delivery": round(net_after_delivery, 2),
        "commission": round(commission, 2),
        "net_income": round(net_income, 2),
        "cogs": round(cogs, 2),
        "cm": round(cm, 2),
        "cm_pct": round(cm_pct, 1),
    }


# ---------------------------------------------------------------------------
# 4. BUILD CROSS-UTILIZATION MATRIX
# ---------------------------------------------------------------------------

def build_cross_utilization(all_recipes):
    """Map ingredients to cuisines they appear in."""
    ing_cuisines = defaultdict(set)
    ing_recipe_count = defaultdict(int)
    ing_total_qty = defaultdict(float)
    cuisine_ingredients = defaultdict(set)
    for r in all_recipes:
        cuisine = r["cuisine"]
        for ing in r["ingredients"]:
            name = ing["ingredient"].strip()
            name_lower = name.lower()
            ing_cuisines[name_lower].add(cuisine)
            ing_recipe_count[name_lower] += 1
            ing_total_qty[name_lower] += ing["quantity"]
            cuisine_ingredients[cuisine].add(name_lower)
    cross_util = []
    for name_lower, cuisines in ing_cuisines.items():
        cross_util.append({
            "ingredient": name_lower,
            "cuisine_count": len(cuisines),
            "cuisines": sorted(cuisines),
            "recipe_count": ing_recipe_count[name_lower],
        })
    cross_util.sort(key=lambda x: (-x["cuisine_count"], -x["recipe_count"]))
    return cross_util, dict(cuisine_ingredients)


# ---------------------------------------------------------------------------
# 5. BUILD SUPPLIER ANALYSIS
# ---------------------------------------------------------------------------

def build_supplier_analysis(canonical_prices):
    suppliers = defaultdict(lambda: {"ingredients": [], "categories": set(), "total_count": 0})
    single_source = []
    for key, info in canonical_prices.items():
        supplier = info["supplier"]
        suppliers[supplier]["ingredients"].append(info["ingredient"])
        suppliers[supplier]["categories"].add(info["category"])
        suppliers[supplier]["total_count"] += 1
    # Check single-source ingredients (would need multi-supplier data - for now all are single)
    supplier_list = []
    for name, data in sorted(suppliers.items(), key=lambda x: -x[1]["total_count"]):
        supplier_list.append({
            "supplier": name,
            "ingredient_count": data["total_count"],
            "categories": sorted(data["categories"]),
        })
    return supplier_list


# ---------------------------------------------------------------------------
# 6. GENERATE HTML
# ---------------------------------------------------------------------------

def generate_html(canonical_prices, all_recipes, complete_costing, cross_util,
                  cuisine_ingredients, supplier_analysis):
    # Pre-compute SF costs for sub-recipe resolution
    sf_costs = build_sf_cost_index(all_recipes, canonical_prices)

    # Pre-compute recipe data with COGS
    recipe_data = []
    for r in all_recipes:
        cogs, matched, unmatched = calc_recipe_cogs(r, canonical_prices, sf_costs)
        # Look up recorded costing
        recorded = complete_costing.get(r["dish_name"].lower(), {})
        recorded_cogs = recorded.get("recorded_cogs", 0)
        sell_price = recorded.get("sell_price", 0)
        wf = waterfall(sell_price, cogs) if sell_price > 0 else None
        variance = 0
        if recorded_cogs > 0 and cogs > 0:
            variance = round(abs(cogs - recorded_cogs) / recorded_cogs * 100, 1)
        recipe_data.append({
            "dish_name": r["dish_name"],
            "cuisine": r["cuisine"],
            "category": r["category"],
            "type": r["type"],
            "ingredients": r["ingredients"],
            "ingredient_count": len(r["ingredients"]),
            "theoretical_cogs": cogs,
            "recorded_cogs": recorded_cogs,
            "sell_price": sell_price,
            "waterfall": wf,
            "variance_pct": variance,
            "unmatched_ingredients": unmatched,
        })

    # Compute summary stats
    cuisines = sorted(set(r["cuisine"] for r in recipe_data))
    total_recipes = len(recipe_data)
    total_sf = sum(1 for r in recipe_data if r["type"] == "semi_finished")
    total_finished = total_recipes - total_sf
    recipes_with_sell = [r for r in recipe_data if r["sell_price"] > 0 and r["waterfall"]]
    avg_food_cost = 0
    avg_cm = 0
    below_target = 0
    if recipes_with_sell:
        food_costs = [(r["theoretical_cogs"] / r["sell_price"] * 100) for r in recipes_with_sell if r["sell_price"] > 0]
        avg_food_cost = round(sum(food_costs) / len(food_costs), 1) if food_costs else 0
        cms = [r["waterfall"]["cm_pct"] for r in recipes_with_sell]
        avg_cm = round(sum(cms) / len(cms), 1) if cms else 0
        below_target = sum(1 for c in cms if c < 20)

    # Build ingredient list for JSON embedding
    ingredient_list = []
    for key, info in sorted(canonical_prices.items(), key=lambda x: x[1]["ingredient"]):
        ingredient_list.append(info)

    # Cuisine summary
    cuisine_summary = []
    for c in cuisines:
        c_recipes = [r for r in recipe_data if r["cuisine"] == c]
        c_with_sell = [r for r in c_recipes if r["sell_price"] > 0 and r["waterfall"]]
        avg_cm_c = 0
        if c_with_sell:
            avg_cm_c = round(sum(r["waterfall"]["cm_pct"] for r in c_with_sell) / len(c_with_sell), 1)
        cuisine_summary.append({
            "cuisine": c,
            "total_recipes": len(c_recipes),
            "semi_finished": sum(1 for r in c_recipes if r["type"] == "semi_finished"),
            "finished": sum(1 for r in c_recipes if r["type"] == "finished"),
            "avg_cm_pct": avg_cm_c,
            "unique_ingredients": len(cuisine_ingredients.get(c, set())),
        })

    # Serialize data for embedding
    json_ingredients = json.dumps(ingredient_list, ensure_ascii=False)
    json_recipes = json.dumps(recipe_data, ensure_ascii=False, default=str)
    json_cross_util = json.dumps(cross_util[:200], ensure_ascii=False)
    json_suppliers = json.dumps(supplier_analysis, ensure_ascii=False)
    json_cuisine_summary = json.dumps(cuisine_summary, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ZwQ Inventory & Recipe Dashboard</title>
<style>
:root {{
    --bg: #0f1117;
    --card: #1a1d27;
    --card-hover: #22263a;
    --border: #2a2e3f;
    --text: #e4e6eb;
    --text-dim: #8b8fa3;
    --accent: #6366f1;
    --accent-light: #818cf8;
    --green: #22c55e;
    --yellow: #eab308;
    --red: #ef4444;
    --orange: #f97316;
    --blue: #3b82f6;
    --purple: #a855f7;
    --cyan: #06b6d4;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
}}
.header {{
    background: linear-gradient(135deg, #1a1d27 0%, #1e2235 100%);
    border-bottom: 1px solid var(--border);
    padding: 20px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}}
.header h1 {{
    font-size: 22px;
    font-weight: 700;
    background: linear-gradient(135deg, var(--accent-light), var(--cyan));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}}
.header .subtitle {{ color: var(--text-dim); font-size: 13px; margin-top: 2px; }}
.tabs {{
    display: flex;
    gap: 4px;
    padding: 12px 32px;
    background: var(--card);
    border-bottom: 1px solid var(--border);
    overflow-x: auto;
}}
.tab {{
    padding: 10px 20px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    color: var(--text-dim);
    transition: all 0.2s;
    white-space: nowrap;
    border: 1px solid transparent;
}}
.tab:hover {{ background: var(--card-hover); color: var(--text); }}
.tab.active {{
    background: var(--accent);
    color: white;
    border-color: var(--accent-light);
}}
.content {{ padding: 24px 32px; }}
.panel {{ display: none; }}
.panel.active {{ display: block; }}
.kpi-row {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
}}
.kpi-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
}}
.kpi-card .label {{ font-size: 12px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.5px; }}
.kpi-card .value {{ font-size: 28px; font-weight: 700; margin-top: 4px; }}
.kpi-card .sub {{ font-size: 12px; color: var(--text-dim); margin-top: 4px; }}
.search-bar {{
    display: flex;
    gap: 12px;
    margin-bottom: 20px;
    flex-wrap: wrap;
    align-items: center;
}}
.search-bar input, .search-bar select {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 14px;
    color: var(--text);
    font-size: 13px;
    outline: none;
}}
.search-bar input {{ min-width: 250px; }}
.search-bar input:focus, .search-bar select:focus {{ border-color: var(--accent); }}
.search-bar select {{ min-width: 150px; }}
table {{
    width: 100%;
    border-collapse: collapse;
    background: var(--card);
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid var(--border);
    font-size: 13px;
}}
th {{
    background: #1e2235;
    padding: 12px 14px;
    text-align: left;
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-dim);
    position: sticky;
    top: 0;
    cursor: pointer;
}}
th:hover {{ color: var(--accent-light); }}
td {{
    padding: 10px 14px;
    border-top: 1px solid var(--border);
}}
tr:hover td {{ background: var(--card-hover); }}
.badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
}}
.badge-green {{ background: rgba(34,197,94,0.15); color: var(--green); }}
.badge-yellow {{ background: rgba(234,179,8,0.15); color: var(--yellow); }}
.badge-red {{ background: rgba(239,68,68,0.15); color: var(--red); }}
.badge-blue {{ background: rgba(59,130,246,0.15); color: var(--blue); }}
.badge-purple {{ background: rgba(168,85,247,0.15); color: var(--purple); }}
.section-title {{ font-size: 16px; font-weight: 600; margin-bottom: 16px; }}
.grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
.grid-3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; }}
@media (max-width: 900px) {{ .grid-2, .grid-3 {{ grid-template-columns: 1fr; }} }}
.chart-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
}}
.chart-card h3 {{ font-size: 14px; font-weight: 600; margin-bottom: 16px; }}
.bar-chart {{ display: flex; flex-direction: column; gap: 8px; }}
.bar-row {{ display: flex; align-items: center; gap: 12px; }}
.bar-label {{ width: 120px; font-size: 12px; color: var(--text-dim); text-align: right; flex-shrink: 0; }}
.bar-track {{ flex: 1; height: 24px; background: #1e2235; border-radius: 4px; overflow: hidden; position: relative; }}
.bar-fill {{ height: 100%; border-radius: 4px; transition: width 0.3s; display: flex; align-items: center; padding-left: 8px; font-size: 11px; font-weight: 600; }}
.bar-value {{ font-size: 12px; color: var(--text-dim); width: 60px; text-align: right; flex-shrink: 0; }}
.recipe-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    margin-bottom: 12px;
    overflow: hidden;
}}
.recipe-header {{
    padding: 14px 20px;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    transition: background 0.2s;
}}
.recipe-header:hover {{ background: var(--card-hover); }}
.recipe-header .name {{ font-weight: 600; font-size: 14px; }}
.recipe-header .meta {{ display: flex; gap: 12px; align-items: center; font-size: 12px; color: var(--text-dim); }}
.recipe-body {{ display: none; padding: 0 20px 16px; border-top: 1px solid var(--border); }}
.recipe-body.open {{ display: block; }}
.recipe-body table {{ margin-top: 12px; font-size: 12px; }}
.heatmap {{ display: grid; gap: 2px; }}
.heatmap-cell {{
    width: 100%;
    aspect-ratio: 1;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    font-weight: 600;
}}
.table-wrapper {{
    max-height: 600px;
    overflow-y: auto;
    border-radius: 12px;
}}
.table-wrapper::-webkit-scrollbar {{ width: 6px; }}
.table-wrapper::-webkit-scrollbar-track {{ background: var(--card); }}
.table-wrapper::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 3px; }}
.pill {{ display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 20px; font-size: 11px; cursor: pointer; border: 1px solid var(--border); background: var(--card); color: var(--text-dim); transition: all 0.2s; }}
.pill.active {{ border-color: var(--accent); color: var(--accent-light); background: rgba(99,102,241,0.1); }}
.pill:hover {{ border-color: var(--accent); }}
.stat-highlight {{ font-size: 32px; font-weight: 800; }}
.cm-green {{ color: var(--green); }}
.cm-yellow {{ color: var(--yellow); }}
.cm-red {{ color: var(--red); }}
.pagination {{ display: flex; gap: 8px; margin-top: 16px; justify-content: center; align-items: center; }}
.pagination button {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 6px 12px;
    color: var(--text);
    cursor: pointer;
    font-size: 12px;
}}
.pagination button:hover {{ border-color: var(--accent); }}
.pagination button:disabled {{ opacity: 0.3; cursor: default; }}
.pagination .page-info {{ font-size: 12px; color: var(--text-dim); }}
.variance-flag {{ color: var(--red); font-weight: 600; }}
</style>
</head>
<body>

<div class="header">
    <div>
        <h1>ZwQ Inventory & Recipe Dashboard</h1>
        <div class="subtitle">35 Brands | 9 Cuisines | Powered by AI Teams</div>
    </div>
    <div style="display:flex;align-items:center;gap:16px">
        <a href="/invoices" style="color:var(--text-dim);text-decoration:none;font-size:13px;padding:8px 16px;border:1px solid var(--border);border-radius:8px;transition:all 0.2s;display:flex;align-items:center;gap:6px" onmouseover="this.style.borderColor='var(--accent)';this.style.color='var(--accent-light)'" onmouseout="this.style.borderColor='var(--border)';this.style.color='var(--text-dim)'">&#128451; Invoice Receiving</a>
        <div style="text-align:right">
            <div style="font-size:12px;color:var(--text-dim)">Last Updated</div>
            <div style="font-size:14px;font-weight:600">{__import__('datetime').date.today().strftime('%d %b %Y')}</div>
        </div>
    </div>
</div>

<div class="tabs">
    <div class="tab active" onclick="switchTab(0)">Ingredient Master</div>
    <div class="tab" onclick="switchTab(1)">Recipe Management</div>
    <div class="tab" onclick="switchTab(2)">Food Costing & Margins</div>
    <div class="tab" onclick="switchTab(3)">Cross-Utilization</div>
    <div class="tab" onclick="switchTab(4)">Supplier Intelligence</div>
    <div class="tab" onclick="switchTab(5)">Analytics Dashboard</div>
</div>

<div class="content">

<!-- ========== TAB 0: INGREDIENT MASTER ========== -->
<div class="panel active" id="panel-0">
    <div class="kpi-row">
        <div class="kpi-card">
            <div class="label">Total Ingredients</div>
            <div class="value">{len(ingredient_list)}</div>
        </div>
        <div class="kpi-card">
            <div class="label">Unique Suppliers</div>
            <div class="value">{len(set(i['supplier'] for i in ingredient_list))}</div>
        </div>
        <div class="kpi-card">
            <div class="label">COGS Ingredients</div>
            <div class="value" style="color:var(--green)">{sum(1 for i in ingredient_list if i['affects_cogs']=='Yes')}</div>
            <div class="sub">Affect food cost</div>
        </div>
        <div class="kpi-card">
            <div class="label">Non-COGS Items</div>
            <div class="value" style="color:var(--text-dim)">{sum(1 for i in ingredient_list if i['affects_cogs']!='Yes')}</div>
            <div class="sub">Packaging, equipment</div>
        </div>
    </div>
    <div class="search-bar">
        <input type="text" id="ing-search" placeholder="Search ingredients..." oninput="filterIngredients()">
        <select id="ing-cat-filter" onchange="filterIngredients()"><option value="">All Categories</option></select>
        <select id="ing-supplier-filter" onchange="filterIngredients()"><option value="">All Suppliers</option></select>
        <select id="ing-cogs-filter" onchange="filterIngredients()">
            <option value="">All Items</option>
            <option value="Yes">COGS Only</option>
            <option value="No">Non-COGS Only</option>
        </select>
    </div>
    <div class="table-wrapper">
        <table id="ing-table">
            <thead>
                <tr>
                    <th onclick="sortIngTable(0)">Ingredient</th>
                    <th onclick="sortIngTable(1)">Category</th>
                    <th onclick="sortIngTable(2)">Sub-Category</th>
                    <th onclick="sortIngTable(3)">UOM</th>
                    <th onclick="sortIngTable(4)">Price/Unit (AED)</th>
                    <th onclick="sortIngTable(5)">Supplier</th>
                    <th onclick="sortIngTable(6)">COGS</th>
                </tr>
            </thead>
            <tbody id="ing-tbody"></tbody>
        </table>
    </div>
    <div class="pagination" id="ing-pagination"></div>
</div>

<!-- ========== TAB 1: RECIPE MANAGEMENT ========== -->
<div class="panel" id="panel-1">
    <div class="kpi-row">
        <div class="kpi-card">
            <div class="label">Total Recipes</div>
            <div class="value">{total_recipes}</div>
        </div>
        <div class="kpi-card">
            <div class="label">Semi-Finished</div>
            <div class="value" style="color:var(--purple)">{total_sf}</div>
            <div class="sub">Base preps & sauces</div>
        </div>
        <div class="kpi-card">
            <div class="label">Finished Dishes</div>
            <div class="value" style="color:var(--cyan)">{total_finished}</div>
            <div class="sub">Plated menu items</div>
        </div>
        <div class="kpi-card">
            <div class="label">Cuisines</div>
            <div class="value">{len(cuisines)}</div>
        </div>
    </div>
    <div class="search-bar">
        <input type="text" id="recipe-search" placeholder="Search recipes..." oninput="filterRecipes()">
        <select id="recipe-cuisine-filter" onchange="filterRecipes()"><option value="">All Cuisines</option></select>
        <select id="recipe-type-filter" onchange="filterRecipes()">
            <option value="">All Types</option>
            <option value="semi_finished">Semi-Finished</option>
            <option value="finished">Finished</option>
        </select>
    </div>
    <!-- Cuisine summary pills -->
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px" id="cuisine-pills"></div>
    <div id="recipe-list"></div>
    <div class="pagination" id="recipe-pagination"></div>
</div>

<!-- ========== TAB 2: FOOD COSTING & MARGINS ========== -->
<div class="panel" id="panel-2">
    <div class="kpi-row">
        <div class="kpi-card">
            <div class="label">Avg Food Cost %</div>
            <div class="value" style="color:{'var(--green)' if avg_food_cost < 30 else 'var(--yellow)'}">{avg_food_cost}%</div>
            <div class="sub">Target: 25-35%</div>
        </div>
        <div class="kpi-card">
            <div class="label">Avg CM%</div>
            <div class="value" style="color:{'var(--green)' if avg_cm >= 20 else 'var(--yellow)'}">{avg_cm}%</div>
            <div class="sub">Target: 20-25%</div>
        </div>
        <div class="kpi-card">
            <div class="label">Below 20% CM</div>
            <div class="value" style="color:var(--red)">{below_target}</div>
            <div class="sub">Need attention</div>
        </div>
        <div class="kpi-card">
            <div class="label">Priced Dishes</div>
            <div class="value">{len(recipes_with_sell)}</div>
            <div class="sub">With sell price</div>
        </div>
    </div>
    <div class="search-bar">
        <input type="text" id="costing-search" placeholder="Search dishes..." oninput="filterCosting()">
        <select id="costing-cuisine" onchange="filterCosting()"><option value="">All Cuisines</option></select>
        <select id="costing-cm" onchange="filterCosting()">
            <option value="">All CM%</option>
            <option value="green">CM >= 20% (On Target)</option>
            <option value="yellow">CM 15-20% (Watch)</option>
            <option value="red">CM < 15% (Critical)</option>
        </select>
        <select id="costing-variance" onchange="filterCosting()">
            <option value="">All Variance</option>
            <option value="flag">Variance > 5%</option>
        </select>
    </div>
    <div class="table-wrapper">
        <table id="costing-table">
            <thead>
                <tr>
                    <th onclick="sortCostingTable(0)">Dish</th>
                    <th onclick="sortCostingTable(1)">Cuisine</th>
                    <th onclick="sortCostingTable(2)">Menu Price</th>
                    <th onclick="sortCostingTable(3)">Discount</th>
                    <th onclick="sortCostingTable(4)">Net Income</th>
                    <th onclick="sortCostingTable(5)">COGS (Calc)</th>
                    <th onclick="sortCostingTable(6)">COGS (Rec)</th>
                    <th onclick="sortCostingTable(7)">CM</th>
                    <th onclick="sortCostingTable(8)">CM%</th>
                    <th onclick="sortCostingTable(9)">Variance</th>
                </tr>
            </thead>
            <tbody id="costing-tbody"></tbody>
        </table>
    </div>
    <div class="pagination" id="costing-pagination"></div>
</div>

<!-- ========== TAB 3: CROSS-UTILIZATION ========== -->
<div class="panel" id="panel-3">
    <div class="kpi-row">
        <div class="kpi-card">
            <div class="label">Shared Across All</div>
            <div class="value" style="color:var(--green)">{sum(1 for c in cross_util if c['cuisine_count'] >= len(cuisines))}</div>
            <div class="sub">Used in all {len(cuisines)} cuisines</div>
        </div>
        <div class="kpi-card">
            <div class="label">Multi-Cuisine</div>
            <div class="value" style="color:var(--blue)">{sum(1 for c in cross_util if c['cuisine_count'] >= 3)}</div>
            <div class="sub">Used in 3+ cuisines</div>
        </div>
        <div class="kpi-card">
            <div class="label">Single-Cuisine</div>
            <div class="value" style="color:var(--orange)">{sum(1 for c in cross_util if c['cuisine_count'] == 1)}</div>
            <div class="sub">Unique to one cuisine</div>
        </div>
        <div class="kpi-card">
            <div class="label">Total Unique</div>
            <div class="value">{len(cross_util)}</div>
            <div class="sub">Ingredients in recipes</div>
        </div>
    </div>
    <div class="grid-2">
        <div class="chart-card">
            <h3>Top Shared Ingredients (3+ cuisines)</h3>
            <div class="table-wrapper" style="max-height:400px">
                <table>
                    <thead><tr><th>Ingredient</th><th>Cuisines</th><th>Recipes</th></tr></thead>
                    <tbody id="shared-ing-tbody"></tbody>
                </table>
            </div>
        </div>
        <div class="chart-card">
            <h3>Ingredients per Cuisine</h3>
            <div class="bar-chart" id="cuisine-ing-chart"></div>
        </div>
    </div>
    <div class="chart-card">
        <h3>Ingredient-Cuisine Matrix</h3>
        <div class="search-bar">
            <input type="text" id="matrix-search" placeholder="Search ingredient in matrix..." oninput="filterMatrix()">
        </div>
        <div class="table-wrapper" style="max-height:500px">
            <table id="matrix-table">
                <thead><tr><th>Ingredient</th><th>Recipes</th></tr></thead>
                <tbody id="matrix-tbody"></tbody>
            </table>
        </div>
    </div>
</div>

<!-- ========== TAB 4: SUPPLIER INTELLIGENCE ========== -->
<div class="panel" id="panel-4">
    <div class="kpi-row">
        <div class="kpi-card">
            <div class="label">Total Suppliers</div>
            <div class="value">{len(supplier_analysis)}</div>
        </div>
        <div class="kpi-card">
            <div class="label">Top Supplier</div>
            <div class="value" style="font-size:16px">{supplier_analysis[0]['supplier'][:25] if supplier_analysis else 'N/A'}</div>
            <div class="sub">{supplier_analysis[0]['ingredient_count'] if supplier_analysis else 0} ingredients</div>
        </div>
        <div class="kpi-card">
            <div class="label">Avg Items/Supplier</div>
            <div class="value">{round(sum(s['ingredient_count'] for s in supplier_analysis)/max(len(supplier_analysis),1),1)}</div>
        </div>
    </div>
    <div class="grid-2">
        <div class="chart-card">
            <h3>Supplier Concentration (Top 15)</h3>
            <div class="bar-chart" id="supplier-chart"></div>
        </div>
        <div class="chart-card">
            <h3>Category Coverage</h3>
            <div class="table-wrapper" style="max-height:400px">
                <table>
                    <thead><tr><th>Supplier</th><th>Items</th><th>Categories</th></tr></thead>
                    <tbody id="supplier-cat-tbody"></tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<!-- ========== TAB 5: ANALYTICS DASHBOARD ========== -->
<div class="panel" id="panel-5">
    <div class="kpi-row">
        <div class="kpi-card">
            <div class="label">Total Recipes</div>
            <div class="value">{total_recipes}</div>
        </div>
        <div class="kpi-card">
            <div class="label">Total Ingredients</div>
            <div class="value">{len(ingredient_list)}</div>
        </div>
        <div class="kpi-card">
            <div class="label">Avg Food Cost %</div>
            <div class="value" style="color:var(--green)">{avg_food_cost}%</div>
        </div>
        <div class="kpi-card">
            <div class="label">Avg CM%</div>
            <div class="value" style="color:var(--accent-light)">{avg_cm}%</div>
        </div>
        <div class="kpi-card">
            <div class="label">Below Target</div>
            <div class="value" style="color:var(--red)">{below_target}</div>
            <div class="sub">CM% < 20%</div>
        </div>
    </div>

    <div class="grid-2">
        <div class="chart-card">
            <h3>Recipes by Cuisine</h3>
            <div class="bar-chart" id="analytics-cuisine-chart"></div>
        </div>
        <div class="chart-card">
            <h3>Avg CM% by Cuisine</h3>
            <div class="bar-chart" id="analytics-cm-chart"></div>
        </div>
    </div>

    <div class="grid-2">
        <div class="chart-card">
            <h3>Top 10 Highest Margin Dishes</h3>
            <div class="table-wrapper" style="max-height:350px">
                <table>
                    <thead><tr><th>Dish</th><th>Cuisine</th><th>CM%</th><th>CM (AED)</th></tr></thead>
                    <tbody id="top10-tbody"></tbody>
                </table>
            </div>
        </div>
        <div class="chart-card">
            <h3>Bottom 10 Lowest Margin Dishes</h3>
            <div class="table-wrapper" style="max-height:350px">
                <table>
                    <thead><tr><th>Dish</th><th>Cuisine</th><th>CM%</th><th>CM (AED)</th></tr></thead>
                    <tbody id="bottom10-tbody"></tbody>
                </table>
            </div>
        </div>
    </div>

    <div class="chart-card">
        <h3>Food Cost Distribution</h3>
        <div class="bar-chart" id="fc-distribution-chart"></div>
    </div>
</div>

</div><!-- end content -->

<script>
// ========== DATA ==========
const INGREDIENTS = {json_ingredients};
const RECIPES = {json_recipes};
const CROSS_UTIL = {json_cross_util};
const SUPPLIERS = {json_suppliers};
const CUISINE_SUMMARY = {json_cuisine_summary};
const CUISINES = {json.dumps(cuisines)};
const CUISINE_COLORS = {{
    'American': '#ef4444', 'Korean': '#f97316', 'Indian': '#eab308',
    'Chinese': '#22c55e', 'Japanese': '#06b6d4', 'Mexican': '#3b82f6',
    'Poke': '#a855f7'
}};

// ========== TAB SWITCHING ==========
function switchTab(idx) {{
    document.querySelectorAll('.tab').forEach((t,i) => t.classList.toggle('active', i===idx));
    document.querySelectorAll('.panel').forEach((p,i) => p.classList.toggle('active', i===idx));
}}

// ========== INGREDIENT TABLE ==========
let ingSort = {{ col: 0, asc: true }};
let ingPage = 0;
const ING_PER_PAGE = 50;
let filteredIngredients = [...INGREDIENTS];

function initIngredientFilters() {{
    const cats = [...new Set(INGREDIENTS.map(i => i.category))].sort();
    const suppliers = [...new Set(INGREDIENTS.map(i => i.supplier))].sort();
    const catSel = document.getElementById('ing-cat-filter');
    cats.forEach(c => {{ const o = document.createElement('option'); o.value = c; o.textContent = c; catSel.appendChild(o); }});
    const supSel = document.getElementById('ing-supplier-filter');
    suppliers.forEach(s => {{ const o = document.createElement('option'); o.value = s; o.textContent = s.substring(0,40); supSel.appendChild(o); }});
}}

function filterIngredients() {{
    const search = document.getElementById('ing-search').value.toLowerCase();
    const cat = document.getElementById('ing-cat-filter').value;
    const supplier = document.getElementById('ing-supplier-filter').value;
    const cogs = document.getElementById('ing-cogs-filter').value;
    filteredIngredients = INGREDIENTS.filter(i => {{
        if (search && !i.ingredient.toLowerCase().includes(search)) return false;
        if (cat && i.category !== cat) return false;
        if (supplier && i.supplier !== supplier) return false;
        if (cogs && i.affects_cogs !== cogs) return false;
        return true;
    }});
    ingPage = 0;
    renderIngTable();
}}

function sortIngTable(col) {{
    if (ingSort.col === col) ingSort.asc = !ingSort.asc;
    else {{ ingSort.col = col; ingSort.asc = true; }}
    const keys = ['ingredient','category','sub_category','uom','price_per_unit','supplier','affects_cogs'];
    const key = keys[col];
    filteredIngredients.sort((a,b) => {{
        let va = a[key], vb = b[key];
        if (typeof va === 'string') va = va.toLowerCase();
        if (typeof vb === 'string') vb = vb.toLowerCase();
        if (va < vb) return ingSort.asc ? -1 : 1;
        if (va > vb) return ingSort.asc ? 1 : -1;
        return 0;
    }});
    renderIngTable();
}}

function renderIngTable() {{
    const tbody = document.getElementById('ing-tbody');
    const start = ingPage * ING_PER_PAGE;
    const page = filteredIngredients.slice(start, start + ING_PER_PAGE);
    tbody.innerHTML = page.map(i => `<tr>
        <td>${{i.ingredient}}</td>
        <td>${{i.category}}</td>
        <td>${{i.sub_category}}</td>
        <td>${{i.uom}}</td>
        <td style="text-align:right">${{i.price_per_unit.toFixed(2)}}</td>
        <td style="font-size:11px">${{i.supplier.substring(0,35)}}</td>
        <td><span class="badge ${{i.affects_cogs==='Yes'?'badge-green':'badge-blue'}}">${{i.affects_cogs}}</span></td>
    </tr>`).join('');
    renderPagination('ing-pagination', filteredIngredients.length, ingPage, ING_PER_PAGE, p => {{ ingPage=p; renderIngTable(); }});
}}

// ========== RECIPE LIST ==========
let recipePage = 0;
const RECIPE_PER_PAGE = 30;
let filteredRecipes = [...RECIPES];

function initRecipeFilters() {{
    const sel = document.getElementById('recipe-cuisine-filter');
    CUISINES.forEach(c => {{ const o = document.createElement('option'); o.value = c; o.textContent = c; sel.appendChild(o); }});
    // Cuisine pills
    const pillContainer = document.getElementById('cuisine-pills');
    CUISINE_SUMMARY.forEach(cs => {{
        const pill = document.createElement('span');
        pill.className = 'pill';
        pill.innerHTML = `${{cs.cuisine}} <strong>${{cs.total_recipes}}</strong>`;
        pill.onclick = () => {{
            document.getElementById('recipe-cuisine-filter').value = cs.cuisine;
            filterRecipes();
        }};
        pillContainer.appendChild(pill);
    }});
}}

function filterRecipes() {{
    const search = document.getElementById('recipe-search').value.toLowerCase();
    const cuisine = document.getElementById('recipe-cuisine-filter').value;
    const type = document.getElementById('recipe-type-filter').value;
    filteredRecipes = RECIPES.filter(r => {{
        if (search && !r.dish_name.toLowerCase().includes(search)) return false;
        if (cuisine && r.cuisine !== cuisine) return false;
        if (type && r.type !== type) return false;
        return true;
    }});
    recipePage = 0;
    renderRecipeList();
}}

function renderRecipeList() {{
    const container = document.getElementById('recipe-list');
    const start = recipePage * RECIPE_PER_PAGE;
    const page = filteredRecipes.slice(start, start + RECIPE_PER_PAGE);
    container.innerHTML = page.map((r, idx) => {{
        const globalIdx = start + idx;
        const cmClass = r.waterfall ? (r.waterfall.cm_pct >= 20 ? 'cm-green' : r.waterfall.cm_pct >= 15 ? 'cm-yellow' : 'cm-red') : '';
        const cmText = r.waterfall ? `CM: ${{r.waterfall.cm_pct}}%` : (r.theoretical_cogs > 0 ? `COGS: ${{r.theoretical_cogs.toFixed(2)}}` : '');
        return `<div class="recipe-card">
            <div class="recipe-header" onclick="toggleRecipe(${{globalIdx}})">
                <div>
                    <span class="name">${{r.dish_name}}</span>
                    <span class="badge ${{r.type==='semi_finished'?'badge-purple':'badge-blue'}}" style="margin-left:8px">${{r.type==='semi_finished'?'SF':'Finished'}}</span>
                </div>
                <div class="meta">
                    <span style="color:${{CUISINE_COLORS[r.cuisine]||'#888'}}">${{r.cuisine}}</span>
                    <span>${{r.category}}</span>
                    <span>${{r.ingredient_count}} ing.</span>
                    <span class="${{cmClass}}">${{cmText}}</span>
                </div>
            </div>
            <div class="recipe-body" id="recipe-body-${{globalIdx}}">
                <table>
                    <thead><tr><th>Ingredient</th><th>Qty</th><th>UOM</th><th>Wastage %</th></tr></thead>
                    <tbody>${{r.ingredients.map(i => `<tr>
                        <td>${{i.ingredient}}</td>
                        <td style="text-align:right">${{i.quantity.toFixed(3)}}</td>
                        <td>${{i.uom}}</td>
                        <td style="text-align:right">${{i.wastage_pct}}%</td>
                    </tr>`).join('')}}</tbody>
                </table>
                ${{r.theoretical_cogs > 0 ? `<div style="margin-top:10px;font-size:12px;color:var(--text-dim)">Theoretical COGS: <strong style="color:var(--text)">AED ${{r.theoretical_cogs.toFixed(2)}}</strong>
                ${{r.recorded_cogs > 0 ? ` | Recorded: <strong>AED ${{r.recorded_cogs.toFixed(2)}}</strong> | Variance: <span class="${{r.variance_pct>5?'variance-flag':''}}">${{r.variance_pct}}%</span>` : ''}}
                ${{r.sell_price > 0 ? ` | Sell: AED ${{r.sell_price}}` : ''}}</div>` : ''}}
                ${{r.unmatched_ingredients && r.unmatched_ingredients.length > 0 ? `<div style="margin-top:6px;font-size:11px;color:var(--orange)">Unmatched: ${{r.unmatched_ingredients.join(', ')}}</div>` : ''}}
            </div>
        </div>`;
    }}).join('');
    renderPagination('recipe-pagination', filteredRecipes.length, recipePage, RECIPE_PER_PAGE, p => {{ recipePage=p; renderRecipeList(); }});
}}

function toggleRecipe(idx) {{
    const body = document.getElementById('recipe-body-' + idx);
    if (body) body.classList.toggle('open');
}}

// ========== COSTING TABLE ==========
let costingSort = {{ col: 8, asc: false }};
let costingPage = 0;
const COSTING_PER_PAGE = 50;
let costingData = RECIPES.filter(r => r.sell_price > 0 && r.waterfall);
let filteredCosting = [...costingData];

function initCostingFilters() {{
    const sel = document.getElementById('costing-cuisine');
    CUISINES.forEach(c => {{ const o = document.createElement('option'); o.value = c; o.textContent = c; sel.appendChild(o); }});
}}

function filterCosting() {{
    const search = document.getElementById('costing-search').value.toLowerCase();
    const cuisine = document.getElementById('costing-cuisine').value;
    const cm = document.getElementById('costing-cm').value;
    const variance = document.getElementById('costing-variance').value;
    filteredCosting = costingData.filter(r => {{
        if (search && !r.dish_name.toLowerCase().includes(search)) return false;
        if (cuisine && r.cuisine !== cuisine) return false;
        if (cm === 'green' && r.waterfall.cm_pct < 20) return false;
        if (cm === 'yellow' && (r.waterfall.cm_pct < 15 || r.waterfall.cm_pct >= 20)) return false;
        if (cm === 'red' && r.waterfall.cm_pct >= 15) return false;
        if (variance === 'flag' && r.variance_pct <= 5) return false;
        return true;
    }});
    costingPage = 0;
    renderCostingTable();
}}

function sortCostingTable(col) {{
    if (costingSort.col === col) costingSort.asc = !costingSort.asc;
    else {{ costingSort.col = col; costingSort.asc = true; }}
    const getVal = (r, c) => {{
        const w = r.waterfall || {{}};
        return [r.dish_name, r.cuisine, w.menu_price||0, w.discount||0, w.net_income||0,
                r.theoretical_cogs, r.recorded_cogs, w.cm||0, w.cm_pct||0, r.variance_pct][c];
    }};
    filteredCosting.sort((a,b) => {{
        let va = getVal(a, col), vb = getVal(b, col);
        if (typeof va === 'string') {{ va = va.toLowerCase(); vb = vb.toLowerCase(); }}
        if (va < vb) return costingSort.asc ? -1 : 1;
        if (va > vb) return costingSort.asc ? 1 : -1;
        return 0;
    }});
    renderCostingTable();
}}

function renderCostingTable() {{
    const tbody = document.getElementById('costing-tbody');
    const start = costingPage * COSTING_PER_PAGE;
    const page = filteredCosting.slice(start, start + COSTING_PER_PAGE);
    tbody.innerHTML = page.map(r => {{
        const w = r.waterfall;
        const cmClass = w.cm_pct >= 20 ? 'badge-green' : w.cm_pct >= 15 ? 'badge-yellow' : 'badge-red';
        return `<tr>
            <td>${{r.dish_name}}</td>
            <td style="color:${{CUISINE_COLORS[r.cuisine]||'#888'}}">${{r.cuisine}}</td>
            <td style="text-align:right">${{w.menu_price.toFixed(0)}}</td>
            <td style="text-align:right">${{w.discount.toFixed(0)}}</td>
            <td style="text-align:right">${{w.net_income.toFixed(2)}}</td>
            <td style="text-align:right">${{r.theoretical_cogs.toFixed(2)}}</td>
            <td style="text-align:right">${{r.recorded_cogs > 0 ? r.recorded_cogs.toFixed(2) : '-'}}</td>
            <td style="text-align:right;font-weight:600">${{w.cm.toFixed(2)}}</td>
            <td><span class="badge ${{cmClass}}">${{w.cm_pct}}%</span></td>
            <td style="text-align:right">${{r.variance_pct > 5 ? '<span class="variance-flag">'+r.variance_pct+'%</span>' : (r.variance_pct > 0 ? r.variance_pct+'%' : '-')}}</td>
        </tr>`;
    }}).join('');
    renderPagination('costing-pagination', filteredCosting.length, costingPage, COSTING_PER_PAGE, p => {{ costingPage=p; renderCostingTable(); }});
}}

// ========== CROSS-UTILIZATION ==========
function renderCrossUtil() {{
    // Shared ingredients table
    const shared = CROSS_UTIL.filter(c => c.cuisine_count >= 3);
    document.getElementById('shared-ing-tbody').innerHTML = shared.slice(0, 50).map(c =>
        `<tr><td style="text-transform:capitalize">${{c.ingredient}}</td>
        <td>${{c.cuisines.map(cu => `<span style="color:${{CUISINE_COLORS[cu]||'#888'}};margin-right:4px">${{cu}}</span>`).join('')}}</td>
        <td style="text-align:right">${{c.recipe_count}}</td></tr>`
    ).join('');

    // Ingredient count per cuisine bar chart
    const maxIng = Math.max(...CUISINE_SUMMARY.map(c => c.unique_ingredients));
    document.getElementById('cuisine-ing-chart').innerHTML = CUISINE_SUMMARY.map(c =>
        `<div class="bar-row">
            <div class="bar-label">${{c.cuisine}}</div>
            <div class="bar-track"><div class="bar-fill" style="width:${{c.unique_ingredients/maxIng*100}}%;background:${{CUISINE_COLORS[c.cuisine]||'#6366f1'}}">${{c.unique_ingredients}}</div></div>
        </div>`
    ).join('');

    // Matrix table
    renderMatrix();
}}

function renderMatrix() {{
    const search = (document.getElementById('matrix-search')?.value || '').toLowerCase();
    const thead = document.getElementById('matrix-table').querySelector('thead tr');
    thead.innerHTML = '<th>Ingredient</th>' + CUISINES.map(c => `<th style="color:${{CUISINE_COLORS[c]||'#888'}}">${{c.substring(0,3)}}</th>`).join('') + '<th>Total</th>';
    const filtered = search ? CROSS_UTIL.filter(c => c.ingredient.includes(search)) : CROSS_UTIL.slice(0, 100);
    document.getElementById('matrix-tbody').innerHTML = filtered.map(c =>
        `<tr><td style="text-transform:capitalize">${{c.ingredient}}</td>
        ${{CUISINES.map(cu => `<td style="text-align:center">${{c.cuisines.includes(cu) ? '<span style="color:var(--green)">&#9679;</span>' : '<span style="color:var(--border)">-</span>'}}</td>`).join('')}}
        <td style="text-align:center;font-weight:600">${{c.cuisine_count}}</td></tr>`
    ).join('');
}}

function filterMatrix() {{ renderMatrix(); }}

// ========== SUPPLIER INTELLIGENCE ==========
function renderSuppliers() {{
    const top15 = SUPPLIERS.slice(0, 15);
    const maxCount = Math.max(...top15.map(s => s.ingredient_count));
    document.getElementById('supplier-chart').innerHTML = top15.map(s =>
        `<div class="bar-row">
            <div class="bar-label" style="width:180px" title="${{s.supplier}}">${{s.supplier.substring(0,22)}}</div>
            <div class="bar-track"><div class="bar-fill" style="width:${{s.ingredient_count/maxCount*100}}%;background:var(--accent)">${{s.ingredient_count}}</div></div>
        </div>`
    ).join('');

    document.getElementById('supplier-cat-tbody').innerHTML = SUPPLIERS.map(s =>
        `<tr><td style="font-size:11px">${{s.supplier.substring(0,35)}}</td>
        <td style="text-align:right">${{s.ingredient_count}}</td>
        <td style="font-size:11px">${{s.categories.join(', ')}}</td></tr>`
    ).join('');
}}

// ========== ANALYTICS DASHBOARD ==========
function renderAnalytics() {{
    // Recipes by cuisine
    const maxRec = Math.max(...CUISINE_SUMMARY.map(c => c.total_recipes));
    document.getElementById('analytics-cuisine-chart').innerHTML = CUISINE_SUMMARY.map(c =>
        `<div class="bar-row">
            <div class="bar-label">${{c.cuisine}}</div>
            <div class="bar-track"><div class="bar-fill" style="width:${{c.total_recipes/maxRec*100}}%;background:${{CUISINE_COLORS[c.cuisine]||'#6366f1'}}">${{c.total_recipes}} (${{c.semi_finished}} SF + ${{c.finished}} F)</div></div>
        </div>`
    ).join('');

    // CM% by cuisine
    const maxCM = Math.max(...CUISINE_SUMMARY.map(c => c.avg_cm_pct), 30);
    document.getElementById('analytics-cm-chart').innerHTML = CUISINE_SUMMARY.filter(c => c.avg_cm_pct > 0).map(c => {{
        const color = c.avg_cm_pct >= 20 ? 'var(--green)' : c.avg_cm_pct >= 15 ? 'var(--yellow)' : 'var(--red)';
        return `<div class="bar-row">
            <div class="bar-label">${{c.cuisine}}</div>
            <div class="bar-track"><div class="bar-fill" style="width:${{c.avg_cm_pct/maxCM*100}}%;background:${{color}}">${{c.avg_cm_pct}}%</div></div>
        </div>`;
    }}).join('');

    // Top 10 / Bottom 10
    const sorted = costingData.filter(r => r.waterfall).sort((a,b) => b.waterfall.cm_pct - a.waterfall.cm_pct);
    const top10 = sorted.slice(0, 10);
    const bottom10 = sorted.slice(-10).reverse();
    document.getElementById('top10-tbody').innerHTML = top10.map(r =>
        `<tr><td>${{r.dish_name}}</td><td style="color:${{CUISINE_COLORS[r.cuisine]||'#888'}}">${{r.cuisine}}</td>
        <td><span class="badge badge-green">${{r.waterfall.cm_pct}}%</span></td>
        <td style="text-align:right">${{r.waterfall.cm.toFixed(2)}}</td></tr>`
    ).join('');
    document.getElementById('bottom10-tbody').innerHTML = bottom10.map(r => {{
        const cls = r.waterfall.cm_pct >= 20 ? 'badge-green' : r.waterfall.cm_pct >= 15 ? 'badge-yellow' : 'badge-red';
        return `<tr><td>${{r.dish_name}}</td><td style="color:${{CUISINE_COLORS[r.cuisine]||'#888'}}">${{r.cuisine}}</td>
        <td><span class="badge ${{cls}}">${{r.waterfall.cm_pct}}%</span></td>
        <td style="text-align:right">${{r.waterfall.cm.toFixed(2)}}</td></tr>`;
    }}).join('');

    // Food cost distribution
    const buckets = {{'<15%':0,'15-20%':0,'20-25%':0,'25-30%':0,'30-35%':0,'>35%':0}};
    costingData.forEach(r => {{
        if (!r.sell_price) return;
        const fc = r.theoretical_cogs / r.sell_price * 100;
        if (fc < 15) buckets['<15%']++;
        else if (fc < 20) buckets['15-20%']++;
        else if (fc < 25) buckets['20-25%']++;
        else if (fc < 30) buckets['25-30%']++;
        else if (fc < 35) buckets['30-35%']++;
        else buckets['>35%']++;
    }});
    const maxBucket = Math.max(...Object.values(buckets));
    const bucketColors = {{'<15%':'var(--green)','15-20%':'var(--green)','20-25%':'var(--green)','25-30%':'var(--yellow)','30-35%':'var(--orange)','>35%':'var(--red)'}};
    document.getElementById('fc-distribution-chart').innerHTML = Object.entries(buckets).map(([k,v]) =>
        `<div class="bar-row">
            <div class="bar-label">${{k}}</div>
            <div class="bar-track"><div class="bar-fill" style="width:${{v/maxBucket*100}}%;background:${{bucketColors[k]}}">${{v}} dishes</div></div>
        </div>`
    ).join('');
}}

// ========== PAGINATION HELPER ==========
function renderPagination(containerId, total, currentPage, perPage, callback) {{
    const totalPages = Math.ceil(total / perPage);
    const container = document.getElementById(containerId);
    if (totalPages <= 1) {{ container.innerHTML = `<span class="page-info">${{total}} items</span>`; return; }}
    container.innerHTML = `
        <button ${{currentPage===0?'disabled':''}} onclick="void(0)" id="${{containerId}}-prev">Prev</button>
        <span class="page-info">Page ${{currentPage+1}} of ${{totalPages}} (${{total}} items)</span>
        <button ${{currentPage>=totalPages-1?'disabled':''}} onclick="void(0)" id="${{containerId}}-next">Next</button>
    `;
    document.getElementById(containerId+'-prev').onclick = () => {{ if(currentPage>0) callback(currentPage-1); }};
    document.getElementById(containerId+'-next').onclick = () => {{ if(currentPage<totalPages-1) callback(currentPage+1); }};
}}

// ========== INIT ==========
document.addEventListener('DOMContentLoaded', () => {{
    initIngredientFilters();
    renderIngTable();
    initRecipeFilters();
    renderRecipeList();
    initCostingFilters();
    renderCostingTable();
    renderCrossUtil();
    renderSuppliers();
    renderAnalytics();
}});
</script>
</body>
</html>"""

    return html


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    print("Loading canonical prices...")
    canonical_prices = load_canonical_prices()
    print(f"  {len(canonical_prices)} ingredients loaded")

    print("Loading complete costing data...")
    complete_costing = load_complete_costing()
    print(f"  {len(complete_costing)} dishes loaded")

    print("Loading all recipes...")
    all_recipes = load_all_recipes()
    print(f"  {len(all_recipes)} total recipes loaded")

    print("Building cross-utilization matrix...")
    cross_util, cuisine_ingredients = build_cross_utilization(all_recipes)
    print(f"  {len(cross_util)} unique ingredients across recipes")

    print("Building supplier analysis...")
    supplier_analysis = build_supplier_analysis(canonical_prices)
    print(f"  {len(supplier_analysis)} suppliers analyzed")

    print("Generating HTML dashboard...")
    html = generate_html(canonical_prices, all_recipes, complete_costing,
                         cross_util, cuisine_ingredients, supplier_analysis)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    file_size = os.path.getsize(OUTPUT_FILE)
    print(f"\nDashboard generated: {OUTPUT_FILE}")
    print(f"File size: {file_size/1024:.0f} KB")
    print("Open in any browser to view.")


if __name__ == "__main__":
    main()
