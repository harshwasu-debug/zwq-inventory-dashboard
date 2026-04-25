"""
Shared utility functions for ZwQ Inventory & Recipe Dashboard.
Extracted from invoice_server.py and build_inventory_dashboard.py.
"""

import os
import json
import base64
import re
import math
import time
from datetime import datetime, date
from difflib import SequenceMatcher
from collections import defaultdict
from io import BytesIO

from dotenv import load_dotenv
load_dotenv(override=True)

# Load API key from Streamlit secrets if available (for Streamlit Cloud deployment)
import os
try:
    import streamlit as st
    if "ANTHROPIC_API_KEY" in st.secrets:
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COSTING_DIR = os.path.join(BASE_DIR, "Dish_Costing")
INVOICES_DIR = os.path.join(BASE_DIR, "Invoices")
CANONICAL_PRICE_FILE = os.path.join(COSTING_DIR, "canonical_price_list.json")
ALIASES_FILE = os.path.join(INVOICES_DIR, "ingredient_aliases.json")
PRICE_HISTORY_FILE = os.path.join(INVOICES_DIR, "price_history.json")

os.makedirs(INVOICES_DIR, exist_ok=True)

# ============================================================================
# FILE I/O
# ============================================================================

def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_canonical_prices_raw():
    return load_json(CANONICAL_PRICE_FILE)

def load_canonical_prices_dict():
    data = load_json(CANONICAL_PRICE_FILE)
    prices = {}
    for item in data.get("items", []):
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

def load_aliases():
    return load_json(ALIASES_FILE, default={})

def save_aliases(aliases):
    save_json(ALIASES_FILE, aliases)

def load_price_history():
    return load_json(PRICE_HISTORY_FILE, default=[])

def save_price_history(history):
    save_json(PRICE_HISTORY_FILE, history)

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
                "dish": name, "cuisine": cuisine, "category": item.get("Category", ""),
                "recorded_cogs": round(float(cost), 2), "sell_price": round(float(sell), 2),
            }
    return costing

# ============================================================================
# RECIPE LOADING & NORMALIZATION
# ============================================================================

def normalize_qty(qty, uom):
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
    return qty, uom

def parse_ingredients(raw_ingredients):
    result = []
    for ing in raw_ingredients:
        name = ing.get("ingredient", "").strip()
        if not name:
            continue
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
        result.append({"ingredient": name, "quantity": round(qty, 4), "uom": uom,
                        "wastage_pct": wastage, "is_semi_finished_ref": is_sf})
    return result

def _load_recipes_standard(filename, cuisine, has_finished_by_category=False, finished_key="finished_recipes"):
    data = load_json(os.path.join(COSTING_DIR, filename))
    recipes = {"semi_finished": [], "finished": []}
    for r in data.get("semi_finished_recipes", []):
        recipes["semi_finished"].append({
            "dish_name": r["dish_name"], "recipe_code": r.get("recipe_code", ""),
            "category": "Semi-Finished", "cuisine": cuisine, "type": "semi_finished",
            "ingredients": parse_ingredients(r.get("ingredients", [])),
        })
    if has_finished_by_category:
        for cat_name, dishes in data.get("finished_dishes_by_category", data.get("finished_recipes_by_category", {})).items():
            for d in dishes:
                recipes["finished"].append({
                    "dish_name": d.get("dish_name", ""), "recipe_code": d.get("recipe_code", ""),
                    "category": cat_name, "cuisine": cuisine, "type": "finished",
                    "ingredients": parse_ingredients(d.get("ingredients", [])),
                })
    for r in data.get(finished_key, []):
        recipes["finished"].append({
            "dish_name": r.get("dish_name", ""), "recipe_code": r.get("recipe_code", ""),
            "category": r.get("category", ""), "cuisine": cuisine, "type": "finished",
            "ingredients": parse_ingredients(r.get("ingredients", [])),
        })
    return recipes

def load_all_recipes():
    all_recipes = []
    # American
    r = _load_recipes_standard("american_recipes.json", "American", has_finished_by_category=True, finished_key="_none_")
    all_recipes.extend(r["semi_finished"]); all_recipes.extend(r["finished"])
    # Korean
    r = _load_recipes_standard("korean_recipes.json", "Korean")
    all_recipes.extend(r["semi_finished"]); all_recipes.extend(r["finished"])
    # Indian
    r = _load_recipes_standard("indian_recipes.json", "Indian")
    all_recipes.extend(r["semi_finished"]); all_recipes.extend(r["finished"])
    # Mexican
    r = _load_recipes_standard("mexican_recipes.json", "Mexican", has_finished_by_category=True, finished_key="finished_dishes")
    all_recipes.extend(r["semi_finished"]); all_recipes.extend(r["finished"])
    # Chinese
    data = load_json(os.path.join(COSTING_DIR, "chinese_recipes.json"))
    for cat in data.get("categories", []):
        for d in cat.get("dishes", []):
            all_recipes.append({
                "dish_name": d.get("dish", "").strip(), "recipe_code": d.get("recipe_code", ""),
                "category": cat.get("category", ""), "cuisine": "Chinese", "type": "finished",
                "ingredients": parse_ingredients(d.get("ingredients", [])),
            })
    # Japanese
    data = load_json(os.path.join(COSTING_DIR, "japanese_recipes.json"))
    for sheet_name, sheet in data.get("sheets", {}).items():
        if not isinstance(sheet, dict): continue
        is_sf = "semi" in sheet_name.lower()
        for d in sheet.get("dishes", []):
            all_recipes.append({
                "dish_name": d.get("dish_name", ""), "recipe_code": d.get("recipe_code", ""),
                "category": d.get("category", sheet_name), "cuisine": "Japanese",
                "type": "semi_finished" if is_sf else "finished",
                "ingredients": parse_ingredients(d.get("ingredients", [])),
            })
    # Poke
    data = load_json(os.path.join(COSTING_DIR, "poke_recipes.json"))
    for sheet_name, sheet in data.get("sheets", {}).items():
        if not isinstance(sheet, dict): continue
        is_sf = "semi" in sheet_name.lower() or "draft" in sheet_name.lower()
        for d in sheet.get("recipes", []):
            all_recipes.append({
                "dish_name": d.get("dish_name", ""), "recipe_code": d.get("recipe_code", ""),
                "category": d.get("category", sheet_name), "cuisine": "Poke",
                "type": "semi_finished" if is_sf else "finished",
                "ingredients": parse_ingredients(d.get("ingredients", [])),
            })
    return all_recipes

# ============================================================================
# COGS & WATERFALL
# ============================================================================

def build_sf_cost_index(all_recipes, canonical_prices):
    sf_costs = {}
    for r in all_recipes:
        if r["type"] == "semi_finished":
            total = 0
            for ing in r["ingredients"]:
                name_key = ing["ingredient"].strip().lower()
                price_info = canonical_prices.get(name_key)
                if not price_info:
                    price_info = canonical_prices.get(name_key.replace("-sf", "").replace("- sf", "").strip())
                if price_info and price_info["affects_cogs"] == "Yes":
                    qty = ing["quantity"]
                    wastage = ing["wastage_pct"]
                    effective_qty = qty * (1 + wastage / 100.0) if wastage > 0 else qty
                    total += effective_qty * price_info["price_per_unit"]
            sf_costs[r["dish_name"].strip().lower()] = round(total, 2)
    return sf_costs

def calc_recipe_cogs(recipe, canonical_prices, sf_costs=None):
    if sf_costs is None: sf_costs = {}
    total, matched, unmatched = 0, 0, []
    for ing in recipe["ingredients"]:
        name_key = ing["ingredient"].strip().lower()
        is_sf_ref = ing.get("is_semi_finished_ref", False) or name_key.endswith("- sf") or name_key.endswith("-sf") or " sf" in name_key
        price_info = canonical_prices.get(name_key)
        if not price_info:
            price_info = canonical_prices.get(name_key.replace("-sf", "").replace("- sf", "").strip())
        if price_info and price_info["affects_cogs"] == "Yes":
            qty = ing["quantity"]; wastage = ing["wastage_pct"]
            effective_qty = qty * (1 + wastage / 100.0) if wastage > 0 else qty
            total += effective_qty * price_info["price_per_unit"]; matched += 1
        elif price_info and price_info["affects_cogs"] == "No":
            matched += 1
        elif is_sf_ref:
            sf_cost = sf_costs.get(name_key)
            if not sf_cost:
                for sk, sv in sf_costs.items():
                    if name_key in sk or sk in name_key: sf_cost = sv; break
            if sf_cost: total += sf_cost * ing["quantity"]; matched += 1
            else: unmatched.append(ing["ingredient"])
        else: unmatched.append(ing["ingredient"])
    return round(total, 2), matched, unmatched

def waterfall(menu_price, cogs):
    if menu_price <= 0:
        return {"menu_price": 0, "discount": 0, "net_after_discount": 0, "delivery": 0,
                "net_after_delivery": 0, "commission": 0, "net_income": 0, "cogs": cogs, "cm": -cogs, "cm_pct": 0}
    discount = min(menu_price / 2, 30)
    net_after_discount = menu_price - discount
    net_after_delivery = net_after_discount - 4
    net_income = net_after_delivery * 0.70
    cm = net_income - cogs
    cm_pct = (cm / menu_price * 100) if menu_price > 0 else 0
    return {"menu_price": round(menu_price, 2), "discount": round(discount, 2),
            "net_after_discount": round(net_after_discount, 2), "delivery": 4,
            "net_after_delivery": round(net_after_delivery, 2),
            "commission": round(net_after_delivery * 0.30, 2), "net_income": round(net_income, 2),
            "cogs": round(cogs, 2), "cm": round(cm, 2), "cm_pct": round(cm_pct, 1)}

# ============================================================================
# CROSS-UTILIZATION & SUPPLIER ANALYSIS
# ============================================================================

def build_cross_utilization(all_recipes):
    ing_cuisines = defaultdict(set); ing_recipe_count = defaultdict(int)
    cuisine_ingredients = defaultdict(set)
    for r in all_recipes:
        cuisine = r["cuisine"]
        for ing in r["ingredients"]:
            name_lower = ing["ingredient"].strip().lower()
            ing_cuisines[name_lower].add(cuisine)
            ing_recipe_count[name_lower] += 1
            cuisine_ingredients[cuisine].add(name_lower)
    cross_util = [{"ingredient": n, "cuisine_count": len(c), "cuisines": sorted(c),
                   "recipe_count": ing_recipe_count[n]} for n, c in ing_cuisines.items()]
    cross_util.sort(key=lambda x: (-x["cuisine_count"], -x["recipe_count"]))
    return cross_util, dict(cuisine_ingredients)

def build_supplier_analysis(canonical_prices):
    suppliers = defaultdict(lambda: {"ingredients": [], "categories": set(), "total_count": 0})
    for key, info in canonical_prices.items():
        s = info["supplier"]
        suppliers[s]["ingredients"].append(info["ingredient"])
        suppliers[s]["categories"].add(info["category"])
        suppliers[s]["total_count"] += 1
    return [{"supplier": n, "ingredient_count": d["total_count"], "categories": sorted(d["categories"])}
            for n, d in sorted(suppliers.items(), key=lambda x: -x[1]["total_count"])]

# ============================================================================
# COMPUTE ALL DASHBOARD DATA
# ============================================================================

def compute_dashboard_data():
    canonical_prices = load_canonical_prices_dict()
    complete_costing = load_complete_costing()
    all_recipes = load_all_recipes()
    sf_costs = build_sf_cost_index(all_recipes, canonical_prices)
    cross_util, cuisine_ingredients = build_cross_utilization(all_recipes)
    supplier_analysis = build_supplier_analysis(canonical_prices)

    recipe_data = []
    for r in all_recipes:
        cogs, matched, unmatched = calc_recipe_cogs(r, canonical_prices, sf_costs)
        recorded = complete_costing.get(r["dish_name"].lower(), {})
        recorded_cogs = recorded.get("recorded_cogs", 0)
        sell_price = recorded.get("sell_price", 0)
        wf = waterfall(sell_price, cogs) if sell_price > 0 else None
        variance = round(abs(cogs - recorded_cogs) / recorded_cogs * 100, 1) if recorded_cogs > 0 and cogs > 0 else 0
        recipe_data.append({
            "dish_name": r["dish_name"], "cuisine": r["cuisine"], "category": r["category"],
            "type": r["type"], "ingredients": r["ingredients"], "ingredient_count": len(r["ingredients"]),
            "theoretical_cogs": cogs, "recorded_cogs": recorded_cogs, "sell_price": sell_price,
            "waterfall": wf, "variance_pct": variance, "unmatched_ingredients": unmatched,
        })

    ingredient_list = load_canonical_prices_raw().get("items", [])

    return {
        "ingredient_list": ingredient_list,
        "recipe_data": recipe_data,
        "cross_util": cross_util,
        "cuisine_ingredients": cuisine_ingredients,
        "supplier_analysis": supplier_analysis,
    }

# ============================================================================
# FUZZY MATCHING (for invoice receiving)
# ============================================================================

def fuzzy_match_ingredient(invoice_item_name, canonical_data, aliases):
    name_lower = invoice_item_name.strip().lower()
    if name_lower in aliases:
        alias = aliases[name_lower]
        for item in canonical_data.get("items", []):
            if item["ingredient"].strip().lower() == alias.lower():
                return {"matched": True, "match_type": "alias", "canonical_name": item["ingredient"],
                        "confidence": 1.0, "suggestions": [], "canonical_item": item}
    scored = []
    for item in canonical_data.get("items", []):
        canonical_lower = item["ingredient"].strip().lower()
        ratio = SequenceMatcher(None, name_lower, canonical_lower).ratio()
        invoice_words = set(re.findall(r'\w+', name_lower))
        canonical_words = set(re.findall(r'\w+', canonical_lower))
        word_overlap = len(invoice_words & canonical_words) / max(len(invoice_words | canonical_words), 1)
        scored.append((ratio * 0.6 + word_overlap * 0.4, item))
    scored.sort(key=lambda x: -x[0])
    top = scored[:5]
    if top and top[0][0] >= 0.55:
        return {"matched": True, "match_type": "fuzzy", "canonical_name": top[0][1]["ingredient"],
                "confidence": round(top[0][0], 3),
                "suggestions": [{"name": s[1]["ingredient"], "score": round(s[0], 3),
                                 "price": s[1]["price_per_unit"], "uom": s[1]["uom"]} for s in top[:3]],
                "canonical_item": top[0][1]}
    return {"matched": False, "match_type": "unmatched", "canonical_name": None,
            "confidence": round(top[0][0], 3) if top else 0,
            "suggestions": [{"name": s[1]["ingredient"], "score": round(s[0], 3),
                             "price": s[1]["price_per_unit"], "uom": s[1]["uom"]} for s in top[:5]],
            "canonical_item": None}

def parse_buying_unit(buying_unit_str):
    if not buying_unit_str: return None, None
    s = str(buying_unit_str).strip().lower()
    m = re.match(r'(\d+)\s*x\s*(\d*\.?\d+)\s*(kg|l|ltr|gm|g|ml|pc|piece|roll)', s)
    if m: return float(m.group(1)) * (float(m.group(2)) if m.group(2) else 1), m.group(3)
    m = re.match(r'(\d*\.?\d+)\s*(kg|l|ltr|gm|g|ml|pc|piece|pieces|nos)', s)
    if m: return float(m.group(1)), m.group(2)
    m = re.match(r'(\d+)\s*pc', s)
    if m: return float(m.group(1)), 'piece'
    return None, None

def normalize_price(invoice_price, invoice_qty, invoice_unit, canonical_uom, buying_unit_str=None):
    if not invoice_qty or invoice_qty <= 0: return None
    unit_lower = str(invoice_unit).lower().strip() if invoice_unit else ""
    price_per_qty = invoice_price / invoice_qty
    canonical_lower = canonical_uom.lower()
    if canonical_lower == "kg":
        if unit_lower in ("kg", "kgs"): return round(price_per_qty, 4)
        elif unit_lower in ("g", "gm", "gms", "gram"): return round(price_per_qty * 1000, 4)
    elif canonical_lower == "l":
        if unit_lower in ("l", "ltr", "litre"): return round(price_per_qty, 4)
        elif unit_lower in ("ml",): return round(price_per_qty * 1000, 4)
    elif canonical_lower == "piece":
        if unit_lower in ("piece", "pc", "pcs", "pieces", "nos", "each"): return round(price_per_qty, 4)
    if buying_unit_str:
        parsed_qty, _ = parse_buying_unit(buying_unit_str)
        if parsed_qty and parsed_qty > 0: return round(invoice_price / (invoice_qty * parsed_qty), 4)
    return round(price_per_qty, 4)

# ============================================================================
# CLAUDE VISION OCR
# ============================================================================

SINGLE_INVOICE_PROMPT = """You are an expert at reading supplier invoices for a restaurant/cloud kitchen.
Analyze this invoice image and extract ALL information in this JSON format:
```json
{"supplier_name":"","invoice_date":"YYYY-MM-DD","invoice_number":"","currency":"AED","items":[{"item_name":"","quantity":0,"unit":"","unit_price":0,"total_price":0}],"subtotal":0,"vat_percentage":5,"vat_amount":0,"grand_total":0,"notes":""}
```
Rules: Extract EVERY line item. Prices as numbers. If unclear add "(unclear)". invoice_date as YYYY-MM-DD. Translate Arabic item names to English. Return ONLY valid JSON."""

MULTI_PAGE_PROMPT = """You are an expert at reading supplier invoices for a restaurant/cloud kitchen.
These images are pages from a scanned PDF. The PDF may contain ONE invoice spanning multiple pages, OR MULTIPLE SEPARATE invoices.
Return a JSON object with an "invoices" array:
```json
{"invoices":[{"supplier_name":"","invoice_date":"YYYY-MM-DD","invoice_number":"","currency":"AED","pages":[],"items":[{"item_name":"","quantity":0,"unit":"","unit_price":0,"total_price":0}],"subtotal":0,"vat_percentage":5,"vat_amount":0,"grand_total":0,"notes":""}]}
```
Rules: Extract EVERY line item from EVERY invoice. Keep items grouped with correct invoice. Prices as numbers. invoice_date as YYYY-MM-DD. Translate Arabic to English. Return ONLY valid JSON."""

MAX_RAW_BYTES = int(5_242_880 * 3 / 4) - 1000

def compress_image(image_bytes, media_type="image/jpeg"):
    from PIL import Image
    if len(image_bytes) <= MAX_RAW_BYTES:
        return base64.b64encode(image_bytes).decode("utf-8"), media_type
    img = Image.open(BytesIO(image_bytes))
    if max(img.size) > 2400:
        ratio = 2400 / max(img.size)
        img = img.resize((int(img.size[0] * ratio), int(img.size[1] * ratio)), Image.LANCZOS)
    if img.mode in ("RGBA", "P"): img = img.convert("RGB")
    for quality in [85, 70, 55, 40, 30]:
        buf = BytesIO(); img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= MAX_RAW_BYTES:
            return base64.b64encode(buf.getvalue()).decode("utf-8"), "image/jpeg"
    img = img.resize((int(img.size[0] * 0.5), int(img.size[1] * 0.5)), Image.LANCZOS)
    buf = BytesIO(); img.save(buf, format="JPEG", quality=40, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("utf-8"), "image/jpeg"

def pdf_to_images(pdf_bytes, dpi=200):
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    for page_num in range(len(doc)):
        pix = doc[page_num].get_pixmap(matrix=matrix)
        b64, mtype = compress_image(pix.tobytes("png"), "image/png")
        pages.append((b64, mtype))
    doc.close()
    return pages

def _call_claude(client, **kwargs):
    import anthropic
    models = ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001"]
    for model in models:
        kwargs["model"] = model
        for attempt in range(3):
            try:
                return client.messages.create(**kwargs)
            except anthropic._exceptions.OverloadedError:
                if attempt < 2: time.sleep((attempt + 1) * 3)
                else: break
    raise Exception("All Claude models overloaded. Try again in a few minutes.")

def _parse_json(text):
    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    return json.loads(m.group(1) if m else text)

def extract_invoice_single(image_b64, media_type):
    import anthropic
    client = anthropic.Anthropic()
    msg = _call_claude(client, model="claude-sonnet-4-20250514", max_tokens=4096,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
            {"type": "text", "text": SINGLE_INVOICE_PROMPT}]}])
    return _parse_json(msg.content[0].text)

def extract_invoice_multipage(pages):
    import anthropic
    client = anthropic.Anthropic()
    content = [{"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}} for b64, mt in pages]
    content.append({"type": "text", "text": f"This PDF has {len(pages)} page(s). Check if these contain ONE or MULTIPLE invoices.\n\n" + MULTI_PAGE_PROMPT})
    msg = _call_claude(client, model="claude-sonnet-4-20250514", max_tokens=16384,
        messages=[{"role": "user", "content": content}])
    result = _parse_json(msg.content[0].text)
    if "invoices" in result: return result
    return {"invoices": [result]}

def process_uploaded_file(file_bytes, filename):
    """Process an uploaded file (image or PDF) and return matched invoice data."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"

    if ext == "pdf":
        pages = pdf_to_images(file_bytes, dpi=200)
        if not pages: raise ValueError("PDF has no pages")
        if len(pages) == 1:
            extracted = extract_invoice_single(pages[0][0], pages[0][1])
            extracted = {"invoices": [extracted]}
        else:
            extracted = extract_invoice_multipage(pages)
    else:
        media_types = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
        b64, mt = compress_image(file_bytes, media_types.get(ext, "image/jpeg"))
        extracted = {"invoices": [extract_invoice_single(b64, mt)]}

    canonical_data = load_canonical_prices_raw()
    aliases = load_aliases()
    results = []
    for inv in extracted.get("invoices", []):
        matched_items = []
        for item in inv.get("items", []):
            match = fuzzy_match_ingredient(item["item_name"], canonical_data, aliases)
            normalized_price, price_change_pct, internal_price = None, None, None
            if match["canonical_item"]:
                ci = match["canonical_item"]
                internal_price = ci["price_per_unit"]
                normalized_price = normalize_price(item.get("unit_price", 0), 1, item.get("unit", ""), ci["uom"], ci.get("buying_unit"))
                if normalized_price and internal_price > 0:
                    price_change_pct = round((normalized_price - internal_price) / internal_price * 100, 1)
            matched_items.append({**item, "match": match, "internal_price": internal_price,
                                  "normalized_invoice_price": normalized_price, "price_change_pct": price_change_pct})
        results.append({**inv, "items": matched_items})
    return results

def confirm_invoice(invoice_data):
    """Confirm an invoice: save it, update prices, log changes."""
    canonical_data = load_canonical_prices_raw()
    aliases = load_aliases()
    price_history = load_price_history()
    today = date.today().isoformat()
    price_updates = []

    for item in invoice_data.get("items", []):
        canonical_name = item.get("confirmed_canonical_name")
        if not canonical_name: continue
        invoice_name = item.get("item_name", "").strip().lower()
        if invoice_name and canonical_name:
            aliases[invoice_name] = canonical_name
        confirmed_price = item.get("confirmed_price")
        if confirmed_price and confirmed_price > 0:
            for ci in canonical_data.get("items", []):
                if ci["ingredient"].strip().lower() == canonical_name.strip().lower():
                    old_price = ci["price_per_unit"]
                    change_pct = round((confirmed_price - old_price) / old_price * 100, 1) if old_price > 0 else 0
                    price_history.append({"date": today, "ingredient": ci["ingredient"],
                        "old_price": old_price, "new_price": confirmed_price, "change_pct": change_pct,
                        "supplier": invoice_data.get("supplier_name", ""),
                        "invoice_number": invoice_data.get("invoice_number", ""), "uom": ci["uom"]})
                    ci["price_per_unit"] = confirmed_price
                    price_updates.append({"ingredient": ci["ingredient"], "old_price": old_price,
                                          "new_price": confirmed_price, "change_pct": change_pct})
                    break

    canonical_data["generated_date"] = today
    save_json(CANONICAL_PRICE_FILE, canonical_data)
    save_aliases(aliases)
    save_price_history(price_history)

    inv_number = invoice_data.get("invoice_number", "unknown")
    inv_date = invoice_data.get("invoice_date", today)
    safe_number = re.sub(r'[^\w\-]', '_', str(inv_number))
    save_json(os.path.join(INVOICES_DIR, f"{inv_date}_{safe_number}.json"),
              {**invoice_data, "confirmed_at": datetime.now().isoformat(), "price_updates": price_updates})

    # Update stock levels for received items
    for item in invoice_data.get("items", []):
        canonical_name = item.get("confirmed_canonical_name")
        if canonical_name and item.get("quantity", 0) > 0:
            update_stock(canonical_name, item["quantity"], item.get("unit", ""),
                         "receipt", f"Invoice {invoice_data.get('invoice_number', '?')}")

    return price_updates


# ============================================================================
# STOCK MANAGEMENT
# ============================================================================

INVENTORY_DIR = os.path.join(BASE_DIR, "Inventory")
STOCK_LEVELS_FILE = os.path.join(INVENTORY_DIR, "stock_levels.json")
STOCK_MOVEMENTS_FILE = os.path.join(INVENTORY_DIR, "stock_movements.json")
BRAND_RECIPE_MAP_FILE = os.path.join(INVENTORY_DIR, "brand_recipe_map.json")
SALES_UPLOADS_DIR = os.path.join(INVENTORY_DIR, "sales_uploads")

os.makedirs(INVENTORY_DIR, exist_ok=True)
os.makedirs(SALES_UPLOADS_DIR, exist_ok=True)


def load_stock_levels():
    return load_json(STOCK_LEVELS_FILE, default={})

def save_stock_levels(levels):
    save_json(STOCK_LEVELS_FILE, levels)

def load_stock_movements():
    return load_json(STOCK_MOVEMENTS_FILE, default=[])

def save_stock_movements(movements):
    save_json(STOCK_MOVEMENTS_FILE, movements)

def load_brand_recipe_map():
    return load_json(BRAND_RECIPE_MAP_FILE, default={"mappings": []})

def save_brand_recipe_map(data):
    save_json(BRAND_RECIPE_MAP_FILE, data)

def load_brand_menus():
    """Load brand menu items from Menu_Deliverect_All_Brands.json."""
    path = os.path.join(BASE_DIR, "Menu_Deliverect_All_Brands.json")
    data = load_json(path, default={})
    return data.get("brands", data)


def update_stock(ingredient_name, quantity, unit, movement_type, reference):
    """Update stock level for an ingredient and log the movement."""
    levels = load_stock_levels()
    movements = load_stock_movements()
    today = date.today().isoformat()

    key = ingredient_name.strip().lower()

    # Normalize quantity to canonical UOM using ingredient price list
    canonical = load_canonical_prices_dict()
    canon_info = canonical.get(key, {})
    canon_uom = canon_info.get("uom", unit)

    # Simple unit conversion
    qty = float(quantity)
    unit_lower = str(unit).lower().strip()
    if canon_uom == "Kg" and unit_lower in ("g", "gm"): qty /= 1000
    elif canon_uom == "L" and unit_lower == "ml": qty /= 1000

    # Update level
    current = levels.get(key, {"ingredient": ingredient_name, "quantity": 0, "uom": canon_uom, "last_updated": today})
    if movement_type == "receipt":
        current["quantity"] = round(current.get("quantity", 0) + qty, 4)
        current["last_received"] = today
    elif movement_type == "depletion":
        current["quantity"] = round(current.get("quantity", 0) - qty, 4)
    elif movement_type == "adjustment":
        current["quantity"] = round(qty, 4)
    current["uom"] = canon_uom
    current["ingredient"] = ingredient_name
    current["last_updated"] = today
    levels[key] = current
    save_stock_levels(levels)

    # Log movement
    movements.append({
        "date": today,
        "type": movement_type,
        "ingredient": ingredient_name,
        "quantity": round(qty, 4),
        "uom": canon_uom,
        "reference": reference,
        "running_balance": current["quantity"],
    })
    save_stock_movements(movements)


def process_sales_depletion(sales_items, reference="Sales"):
    """Process sales items and deplete stock based on recipe mappings.

    sales_items: list of dicts with keys: brand, menu_item, modifier, qty
    Returns: {consumed: [...], unmatched: [...], depletion_summary: [...]}
    """
    brm = load_brand_recipe_map()
    canonical_prices = load_canonical_prices_dict()
    all_recipes = load_all_recipes()
    sf_costs_index = build_sf_cost_index(all_recipes, canonical_prices)

    # Build lookup: (brand_lower, menu_item_lower) -> mapping
    mapping_lookup = {}
    modifier_lookup = {}  # (brand_lower, menu_item_lower, modifier_lower) -> modifier_info
    for m in brm.get("mappings", []):
        key = (m["brand"].strip().lower(), m["menu_item"].strip().lower())
        mapping_lookup[key] = m
        for mod in m.get("modifiers", []):
            mod_key = (m["brand"].strip().lower(), m["menu_item"].strip().lower(), mod["modifier_name"].strip().lower())
            modifier_lookup[mod_key] = mod

    # Build recipe lookup by code and name
    recipe_by_code = {}
    recipe_by_name = {}
    for r in all_recipes:
        if r.get("recipe_code"): recipe_by_code[r["recipe_code"].lower()] = r
        recipe_by_name[r["dish_name"].strip().lower()] = r

    consumed = defaultdict(float)  # ingredient_lower -> total qty consumed
    unmatched = []
    matched_count = 0

    for sale in sales_items:
        brand = str(sale.get("brand", "")).strip()
        menu_item = str(sale.get("menu_item", "")).strip()
        modifier = str(sale.get("modifier", "") or "").strip()
        qty = float(sale.get("qty", 1))

        # Find recipe mapping
        key = (brand.lower(), menu_item.lower())
        mapping = mapping_lookup.get(key)

        if not mapping:
            unmatched.append({"brand": brand, "menu_item": menu_item, "modifier": modifier, "qty": qty})
            continue

        # Find recipe
        recipe = None
        rc = mapping.get("recipe_code", "").lower()
        rn = mapping.get("recipe_name", "").lower()
        if rc: recipe = recipe_by_code.get(rc)
        if not recipe and rn: recipe = recipe_by_name.get(rn)

        if not recipe:
            unmatched.append({"brand": brand, "menu_item": menu_item, "modifier": modifier, "qty": qty, "reason": "recipe not found"})
            continue

        matched_count += 1

        # Deplete base recipe ingredients × qty sold
        for ing in recipe.get("ingredients", []):
            ing_name = ing["ingredient"].strip().lower()
            ing_qty = ing["quantity"] * qty
            wastage = ing.get("wastage_pct", 0)
            if wastage > 0: ing_qty *= (1 + wastage / 100)
            consumed[ing_name] += ing_qty

        # Handle modifier additional ingredients
        if modifier:
            mod_key = (brand.lower(), menu_item.lower(), modifier.lower())
            mod_info = modifier_lookup.get(mod_key)
            if mod_info:
                for add_ing in mod_info.get("additional_ingredients", []):
                    ing_name = add_ing["ingredient"].strip().lower()
                    ing_qty = add_ing["quantity"] * qty
                    consumed[ing_name] += ing_qty

    # Apply depletion to stock
    depletion_summary = []
    stock_levels = load_stock_levels()
    for ing_lower, total_qty in consumed.items():
        # Find canonical name
        canon = canonical_prices.get(ing_lower, {})
        display_name = canon.get("ingredient", ing_lower)
        uom = canon.get("uom", "Kg")

        update_stock(display_name, round(total_qty, 4), uom, "depletion", reference)

        # Get updated stock level
        updated = load_stock_levels().get(ing_lower, {})
        depletion_summary.append({
            "ingredient": display_name,
            "consumed": round(total_qty, 4),
            "uom": uom,
            "remaining": updated.get("quantity", 0),
        })

    depletion_summary.sort(key=lambda x: -x["consumed"])

    return {
        "matched_count": matched_count,
        "unmatched": unmatched,
        "consumed": dict(consumed),
        "depletion_summary": depletion_summary,
        "total_ingredients_depleted": len(consumed),
    }


# ============================================================================
# WASTAGE TRACKING (Staff Meals, Expired, Damaged, etc.)
# ============================================================================

WASTAGE_FILE = os.path.join(INVENTORY_DIR, "wastage_log.json")
STOCK_COUNTS_FILE = os.path.join(INVENTORY_DIR, "stock_counts.json")

WASTAGE_TYPES = [
    {"name": "Staff Meal", "expense": True, "description": "Free meal for staff"},
    {"name": "Expired Goods", "expense": False, "description": "Past expiration date"},
    {"name": "Overcooked / Burnt", "expense": False, "description": "Kitchen error"},
    {"name": "Damaged on Receipt", "expense": False, "description": "Damaged supplier delivery"},
    {"name": "Spoilage", "expense": False, "description": "Food spoiled before use"},
    {"name": "Photoshoot / Marketing", "expense": True, "description": "Used for content/marketing"},
    {"name": "Management Meal", "expense": True, "description": "Management consumption"},
    {"name": "Customer Complaint Replacement", "expense": False, "description": "Re-made for customer"},
    {"name": "Testing / R&D", "expense": True, "description": "Recipe development"},
    {"name": "Other", "expense": False, "description": "Other reason"},
]


def load_wastage_log():
    return load_json(WASTAGE_FILE, default=[])

def save_wastage_log(log):
    save_json(WASTAGE_FILE, log)


def record_wastage(ingredient, quantity, uom, wastage_type, notes="", brand=""):
    """Record a wastage event and deplete stock."""
    log = load_wastage_log()
    today = date.today().isoformat()

    is_expense = next((wt["expense"] for wt in WASTAGE_TYPES if wt["name"] == wastage_type), False)

    entry = {
        "date": today,
        "ingredient": ingredient,
        "quantity": round(float(quantity), 4),
        "uom": uom,
        "type": wastage_type,
        "is_expense": is_expense,
        "brand": brand,
        "notes": notes,
        "logged_at": datetime.now().isoformat(),
    }
    log.append(entry)
    save_wastage_log(log)

    # Deplete stock
    update_stock(ingredient, quantity, uom, "depletion", f"Wastage: {wastage_type}")
    return entry


# ============================================================================
# STOCK COUNT (Physical Inventory) & VARIANCE
# ============================================================================

def load_stock_counts():
    return load_json(STOCK_COUNTS_FILE, default=[])

def save_stock_counts(counts):
    save_json(STOCK_COUNTS_FILE, counts)


def record_stock_count(count_data, count_date=None, notes=""):
    """Record a stock count event.

    count_data: list of {ingredient, counted_qty, uom}
    Returns: variance report comparing system stock vs counted stock
    """
    counts = load_stock_counts()
    if count_date is None:
        count_date = date.today().isoformat()

    stock_levels = load_stock_levels()
    canonical = load_canonical_prices_dict()

    variances = []
    for item in count_data:
        ing_name = item["ingredient"]
        counted = float(item.get("counted_qty", 0))
        uom = item.get("uom", "")

        key = ing_name.strip().lower()
        system_qty = stock_levels.get(key, {}).get("quantity", 0)
        diff = counted - system_qty
        diff_pct = (diff / system_qty * 100) if system_qty > 0 else (100 if counted > 0 else 0)

        unit_price = canonical.get(key, {}).get("price_per_unit", 0)
        value_impact = diff * unit_price

        variances.append({
            "ingredient": ing_name,
            "system_qty": round(system_qty, 4),
            "counted_qty": round(counted, 4),
            "variance": round(diff, 4),
            "variance_pct": round(diff_pct, 1),
            "uom": uom,
            "unit_price": round(unit_price, 2),
            "value_impact": round(value_impact, 2),
        })

        # Apply count adjustment to stock
        update_stock(ing_name, counted, uom, "adjustment", f"Stock Count {count_date}")

    count_event = {
        "date": count_date,
        "logged_at": datetime.now().isoformat(),
        "items_counted": len(count_data),
        "total_value_impact": round(sum(v["value_impact"] for v in variances), 2),
        "notes": notes,
        "variances": variances,
    }
    counts.append(count_event)
    save_stock_counts(counts)
    return count_event


def calculate_slow_moving(days_lookback=30, threshold_movements=2):
    """Identify ingredients with low consumption over the lookback period."""
    movements = load_stock_movements()
    stock_levels = load_stock_levels()
    canonical = load_canonical_prices_dict()

    cutoff = (date.today() - __import__("datetime").timedelta(days=days_lookback)).isoformat()

    # Count depletion events per ingredient
    consumption = defaultdict(lambda: {"count": 0, "total_qty": 0})
    for m in movements:
        if m.get("date", "") >= cutoff and m.get("type") == "depletion":
            key = m.get("ingredient", "").strip().lower()
            consumption[key]["count"] += 1
            consumption[key]["total_qty"] += abs(m.get("quantity", 0))

    slow_items = []
    for key, info in stock_levels.items():
        qty = info.get("quantity", 0)
        if qty <= 0: continue
        cons = consumption.get(key, {"count": 0, "total_qty": 0})
        canon = canonical.get(key, {})
        unit_price = canon.get("price_per_unit", 0)
        stock_value = qty * unit_price

        if cons["count"] <= threshold_movements:
            avg_daily = cons["total_qty"] / max(days_lookback, 1)
            days_supply = qty / avg_daily if avg_daily > 0 else float("inf")
            slow_items.append({
                "ingredient": info.get("ingredient", key),
                "current_stock": round(qty, 3),
                "uom": info.get("uom", ""),
                "stock_value": round(stock_value, 2),
                "movements_in_period": cons["count"],
                "consumed_qty": round(cons["total_qty"], 3),
                "avg_daily_use": round(avg_daily, 4),
                "days_supply": round(days_supply, 1) if days_supply != float("inf") else "infinite",
                "category": canon.get("category", ""),
            })

    slow_items.sort(key=lambda x: -x["stock_value"])
    return slow_items
