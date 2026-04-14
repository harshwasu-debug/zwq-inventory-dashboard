#!/usr/bin/env python3
"""
Invoice Receiving Server for ZwQ Cloud Kitchen Group
Flask API that processes supplier invoice images via Claude Vision API,
matches items to canonical prices, and updates the price database.
"""

import os
import json
import base64
import re
import subprocess
import sys
from datetime import datetime, date
from difflib import SequenceMatcher
from collections import defaultdict

from dotenv import load_dotenv
load_dotenv(override=True)  # Load ANTHROPIC_API_KEY from .env file

from flask import Flask, request, jsonify, send_from_directory
import anthropic
import fitz  # PyMuPDF for PDF handling

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COSTING_DIR = os.path.join(BASE_DIR, "Dish_Costing")
INVOICES_DIR = os.path.join(BASE_DIR, "Invoices")
CANONICAL_PRICE_FILE = os.path.join(COSTING_DIR, "canonical_price_list.json")
ALIASES_FILE = os.path.join(INVOICES_DIR, "ingredient_aliases.json")
PRICE_HISTORY_FILE = os.path.join(INVOICES_DIR, "price_history.json")

# Ensure directories exist
os.makedirs(INVOICES_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# DATA HELPERS
# ---------------------------------------------------------------------------

def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_canonical_prices():
    return load_json(CANONICAL_PRICE_FILE)


def load_aliases():
    return load_json(ALIASES_FILE, default={})


def save_aliases(aliases):
    save_json(ALIASES_FILE, aliases)


def load_price_history():
    return load_json(PRICE_HISTORY_FILE, default=[])


def save_price_history(history):
    save_json(PRICE_HISTORY_FILE, history)


# ---------------------------------------------------------------------------
# FUZZY MATCHING
# ---------------------------------------------------------------------------

def fuzzy_match_ingredient(invoice_item_name, canonical_data, aliases):
    """Match an invoice item name to canonical ingredient list."""
    name_lower = invoice_item_name.strip().lower()

    # Check aliases first (exact previous matches)
    if name_lower in aliases:
        alias = aliases[name_lower]
        # Verify the alias target still exists
        for item in canonical_data["items"]:
            if item["ingredient"].strip().lower() == alias.lower():
                return {
                    "matched": True,
                    "match_type": "alias",
                    "canonical_name": item["ingredient"],
                    "confidence": 1.0,
                    "suggestions": [],
                    "canonical_item": item,
                }
        # Alias target was removed, fall through to fuzzy

    # Fuzzy match against all canonical ingredients
    scored = []
    for item in canonical_data["items"]:
        canonical_lower = item["ingredient"].strip().lower()
        # Multiple matching strategies
        ratio = SequenceMatcher(None, name_lower, canonical_lower).ratio()

        # Boost if key words overlap
        invoice_words = set(re.findall(r'\w+', name_lower))
        canonical_words = set(re.findall(r'\w+', canonical_lower))
        word_overlap = len(invoice_words & canonical_words) / max(len(invoice_words | canonical_words), 1)

        combined = ratio * 0.6 + word_overlap * 0.4
        scored.append((combined, item))

    scored.sort(key=lambda x: -x[0])
    top = scored[:5]

    if top[0][0] >= 0.75:
        return {
            "matched": True,
            "match_type": "fuzzy",
            "canonical_name": top[0][1]["ingredient"],
            "confidence": round(top[0][0], 3),
            "suggestions": [{"name": s[1]["ingredient"], "score": round(s[0], 3),
                             "price": s[1]["price_per_unit"], "uom": s[1]["uom"]} for s in top[:3]],
            "canonical_item": top[0][1],
        }
    else:
        return {
            "matched": False,
            "match_type": "unmatched",
            "canonical_name": None,
            "confidence": round(top[0][0], 3) if top else 0,
            "suggestions": [{"name": s[1]["ingredient"], "score": round(s[0], 3),
                             "price": s[1]["price_per_unit"], "uom": s[1]["uom"]} for s in top[:5]],
            "canonical_item": None,
        }


# ---------------------------------------------------------------------------
# UNIT CONVERSION
# ---------------------------------------------------------------------------

def parse_buying_unit(buying_unit_str):
    """Parse buying unit string like '10 Kg', '6x1L', '454gm', '1x6 Roll'."""
    if not buying_unit_str:
        return None, None
    s = str(buying_unit_str).strip().lower()

    # Pattern: NxM unit (e.g., 6x1L, 1x6 Roll)
    m = re.match(r'(\d+)\s*x\s*(\d*\.?\d+)\s*(kg|l|ltr|gm|g|ml|pc|piece|roll)', s)
    if m:
        count = float(m.group(1))
        size = float(m.group(2)) if m.group(2) else 1
        unit = m.group(3)
        return count * size, unit

    # Pattern: N unit (e.g., 10 Kg, 454gm)
    m = re.match(r'(\d*\.?\d+)\s*(kg|l|ltr|gm|g|ml|pc|piece|pieces|nos)', s)
    if m:
        return float(m.group(1)), m.group(2)

    # Pattern: Npc (e.g., 1pc)
    m = re.match(r'(\d+)\s*pc', s)
    if m:
        return float(m.group(1)), 'piece'

    return None, None


def normalize_price(invoice_price, invoice_qty, invoice_unit, canonical_uom, buying_unit_str=None):
    """Convert invoice price to canonical price per unit."""
    if not invoice_qty or invoice_qty <= 0:
        return None

    unit_lower = str(invoice_unit).lower().strip() if invoice_unit else ""

    # Price per buying unit
    price_per_qty = invoice_price / invoice_qty

    # Convert to canonical UOM
    canonical_lower = canonical_uom.lower()

    if canonical_lower == "kg":
        if unit_lower in ("kg", "kgs"):
            return round(price_per_qty, 4)
        elif unit_lower in ("g", "gm", "gms", "gram"):
            return round(price_per_qty * 1000, 4)
    elif canonical_lower == "l":
        if unit_lower in ("l", "ltr", "litre"):
            return round(price_per_qty, 4)
        elif unit_lower in ("ml",):
            return round(price_per_qty * 1000, 4)
    elif canonical_lower == "piece":
        if unit_lower in ("piece", "pc", "pcs", "pieces", "nos", "each"):
            return round(price_per_qty, 4)

    # Fallback: try parsing the buying_unit from canonical to figure out conversion
    if buying_unit_str:
        parsed_qty, parsed_unit = parse_buying_unit(buying_unit_str)
        if parsed_qty and parsed_qty > 0:
            return round(invoice_price / (invoice_qty * parsed_qty), 4)

    return round(price_per_qty, 4)


# ---------------------------------------------------------------------------
# CLAUDE VISION OCR
# ---------------------------------------------------------------------------

SINGLE_INVOICE_PROMPT = """You are an expert at reading supplier invoices for a restaurant/cloud kitchen.

Analyze this invoice image and extract ALL information in the following JSON format. Be precise with numbers.

```json
{
  "supplier_name": "Full supplier company name",
  "invoice_date": "YYYY-MM-DD",
  "invoice_number": "Invoice code/number",
  "currency": "AED",
  "items": [
    {
      "item_name": "Item description as shown on invoice",
      "quantity": 5,
      "unit": "Kg or L or Piece or Box or Carton etc",
      "unit_price": 12.50,
      "total_price": 62.50
    }
  ],
  "subtotal": 500.00,
  "vat_percentage": 5,
  "vat_amount": 25.00,
  "grand_total": 525.00,
  "notes": "Any relevant notes or payment terms"
}
```

Rules:
- Extract EVERY line item, even if partially visible
- If a field is unclear, provide your best reading and add "(unclear)" suffix
- Prices should be numbers, not strings
- For quantity, include the number and unit separately
- If VAT is not shown, set vat_percentage and vat_amount to 0
- invoice_date must be YYYY-MM-DD format
- If the invoice is in Arabic, translate item names to English but keep supplier name as-is
- Return ONLY valid JSON, no other text"""


MULTI_PAGE_PROMPT = """You are an expert at reading supplier invoices for a restaurant/cloud kitchen.

These images are pages from a scanned PDF. The PDF may contain:
- ONE invoice spanning multiple pages, OR
- MULTIPLE SEPARATE invoices (different invoice numbers, dates, or suppliers)

First, determine how many SEPARATE invoices are present by looking for:
- Different invoice numbers
- Different dates
- "Total" rows followed by a new invoice header
- Page headers that restart numbering

Return a JSON array of invoices. If there is only one invoice, return an array with one element.

```json
{
  "invoices": [
    {
      "supplier_name": "Full supplier company name",
      "invoice_date": "YYYY-MM-DD",
      "invoice_number": "Invoice code/number",
      "currency": "AED",
      "pages": [1, 2],
      "items": [
        {
          "item_name": "Item description as shown on invoice",
          "quantity": 5,
          "unit": "Kg or L or Piece or Box or Carton etc",
          "unit_price": 12.50,
          "total_price": 62.50
        }
      ],
      "subtotal": 500.00,
      "vat_percentage": 5,
      "vat_amount": 25.00,
      "grand_total": 525.00,
      "notes": ""
    }
  ]
}
```

Rules:
- Extract EVERY line item from EVERY invoice
- Keep items grouped with their correct invoice — do NOT mix items between invoices
- If a field is unclear, add "(unclear)" suffix
- Prices should be numbers, not strings
- If VAT is not shown, set vat_percentage and vat_amount to 0
- invoice_date must be YYYY-MM-DD format
- If the invoice is in Arabic, translate item names to English but keep supplier name as-is
- Return ONLY valid JSON, no other text"""


MAX_BASE64_BYTES = 5_242_880  # Claude's 5MB limit is on base64-encoded size
MAX_RAW_BYTES = int(MAX_BASE64_BYTES * 3 / 4) - 1000  # base64 adds ~33%, with safety margin = ~3.9MB


def compress_image(image_bytes, media_type="image/jpeg"):
    """Compress image so base64-encoded version stays under Claude's 5MB limit. Returns (base64, media_type)."""
    from io import BytesIO
    from PIL import Image

    # Check if base64 encoded would be under limit
    size = len(image_bytes)
    if size <= MAX_RAW_BYTES:
        return base64.b64encode(image_bytes).decode("utf-8"), media_type

    # Open with PIL and compress as JPEG
    img = Image.open(BytesIO(image_bytes))

    # Resize if very large dimensions
    max_dim = 2400
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    # Convert to RGB if needed (for JPEG)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Compress with decreasing quality until under limit
    for quality in [85, 70, 55, 40, 30]:
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= MAX_RAW_BYTES:
            return base64.b64encode(buf.getvalue()).decode("utf-8"), "image/jpeg"

    # Last resort: resize more aggressively
    img = img.resize((int(img.size[0] * 0.5), int(img.size[1] * 0.5)), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=40, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("utf-8"), "image/jpeg"


def pdf_to_images(pdf_bytes, dpi=200):
    """Convert PDF bytes to a list of (base64_png, media_type) tuples, one per page."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    zoom = dpi / 72  # 72 is default PDF DPI
    matrix = fitz.Matrix(zoom, zoom)
    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=matrix)
        png_bytes = pix.tobytes("png")
        b64, mtype = compress_image(png_bytes, "image/png")
        pages.append((b64, mtype))
    doc.close()
    return pages


MODELS = ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001"]


def call_claude_with_retry(client, **kwargs):
    """Call Claude API with retry on overloaded errors. Falls back to Haiku if Sonnet is down."""
    import time
    for model in MODELS:
        kwargs["model"] = model
        for attempt in range(3):
            try:
                result = client.messages.create(**kwargs)
                if model != MODELS[0]:
                    print(f"  Used fallback model: {model}")
                return result
            except anthropic._exceptions.OverloadedError:
                if attempt < 2:
                    wait = (attempt + 1) * 3
                    print(f"  {model} overloaded, retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"  {model} overloaded after 3 attempts, trying next model...")
                    break
    raise Exception("All Claude models are currently overloaded. Please try again in a few minutes.")


def parse_claude_json(response_text):
    """Extract JSON from Claude's response, handling markdown code blocks."""
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response_text)
    if json_match:
        return json.loads(json_match.group(1))
    return json.loads(response_text)


def extract_invoice_with_claude(image_base64, media_type="image/jpeg"):
    """Send single invoice image to Claude Vision API for extraction."""
    client = anthropic.Anthropic()

    message = call_claude_with_retry(client,
        model=MODELS[0],
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_base64,
                    }
                },
                {
                    "type": "text",
                    "text": SINGLE_INVOICE_PROMPT,
                }
            ]
        }]
    )

    return parse_claude_json(message.content[0].text)


def extract_invoice_multipage(pages):
    """Send multi-page PDF to Claude Vision. Detects multiple invoices in one PDF."""
    client = anthropic.Anthropic()

    content = []
    for i, (b64, mtype) in enumerate(pages):
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mtype,
                "data": b64,
            }
        })

    content.append({
        "type": "text",
        "text": f"This PDF has {len(pages)} page(s). Carefully check if these pages contain "
                f"ONE invoice or MULTIPLE SEPARATE invoices.\n\n" + MULTI_PAGE_PROMPT,
    })

    message = call_claude_with_retry(client,
        model=MODELS[0],
        max_tokens=16384,
        messages=[{"role": "user", "content": content}]
    )

    result = parse_claude_json(message.content[0].text)

    # If Claude returned the multi-invoice format with "invoices" array
    if "invoices" in result:
        return result  # Contains {"invoices": [...]}

    # If Claude returned a single invoice (old format), wrap it
    return {"invoices": [result]}


# ---------------------------------------------------------------------------
# API ROUTES
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "Inventory_Recipe_Dashboard.html")


@app.route("/invoices")
def invoice_page():
    return send_from_directory(BASE_DIR, "Invoice_Receiving.html")


@app.route("/dashboard")
def dashboard():
    return send_from_directory(BASE_DIR, "Inventory_Recipe_Dashboard.html")


@app.route("/api/ingredients")
def get_ingredients():
    """Return canonical ingredient list for frontend matching."""
    data = load_canonical_prices()
    return jsonify({"items": data.get("items", [])})


@app.route("/api/upload-invoice", methods=["POST"])
def upload_invoice():
    """Process uploaded invoice image or PDF via Claude Vision API."""
    if "invoice" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["invoice"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    # Read file
    file_data = file.read()
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"

    # Save original file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_filename = f"{timestamp}_{file.filename}"
    saved_path = os.path.join(INVOICES_DIR, saved_filename)
    with open(saved_path, "wb") as f:
        f.write(file_data)

    # Extract via Claude Vision
    try:
        if ext == "pdf":
            # Convert PDF pages to images, send all to Claude in one request
            pages = pdf_to_images(file_data, dpi=200)
            if not pages:
                return jsonify({"error": "PDF has no pages"}), 400
            if len(pages) == 1:
                extracted = extract_invoice_with_claude(pages[0][0], pages[0][1])
            else:
                # Multi-page: send all pages together so Claude sees the full invoice
                extracted = extract_invoice_multipage(pages)
            page_count = len(pages)
        else:
            # Image file — compress if needed to stay under 5MB
            image_base64, media_type = compress_image(file_data, {
                "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                "webp": "image/webp", "gif": "image/gif"
            }.get(ext, "image/jpeg"))
            extracted = extract_invoice_with_claude(image_base64, media_type)
            page_count = 1
    except json.JSONDecodeError as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to parse Claude response as JSON: {str(e)}"}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Vision API error: Error code: {getattr(e, 'status_code', '?')} - {str(e)}"}), 500

    image_filename = saved_filename

    # Normalize extracted data to always be a list of invoices
    if "invoices" in extracted:
        invoice_list = extracted["invoices"]
    else:
        invoice_list = [extracted]

    canonical_data = load_canonical_prices()
    aliases = load_aliases()

    processed_invoices = []
    for inv in invoice_list:
        # Fuzzy match each item against canonical prices
        matched_items = []
        for item in inv.get("items", []):
            match = fuzzy_match_ingredient(item["item_name"], canonical_data, aliases)
            normalized_price = None
            price_change_pct = None
            internal_price = None
            if match["canonical_item"]:
                ci = match["canonical_item"]
                internal_price = ci["price_per_unit"]
                normalized_price = normalize_price(
                    item.get("unit_price", 0), 1, item.get("unit", ""),
                    ci["uom"], ci.get("buying_unit"))
                if normalized_price and internal_price > 0:
                    price_change_pct = round((normalized_price - internal_price) / internal_price * 100, 1)
            matched_items.append({
                **item,
                "match": match,
                "internal_price": internal_price,
                "normalized_invoice_price": normalized_price,
                "price_change_pct": price_change_pct,
                "receiving_status": "received",
                "received_qty": item.get("quantity", 0),
            })

        processed_invoices.append({
            **inv,
            "items": matched_items,
            "image_file": image_filename,
            "page_count": page_count,
            "processed_at": datetime.now().isoformat(),
        })

    # If single invoice, return it directly (backward compatible)
    # If multiple, return array so frontend can show them sequentially
    if len(processed_invoices) == 1:
        return jsonify(processed_invoices[0])
    else:
        return jsonify({
            "multiple_invoices": True,
            "invoice_count": len(processed_invoices),
            "invoices": processed_invoices,
        })


@app.route("/api/manual-invoice", methods=["POST"])
def manual_invoice():
    """Process manually entered invoice data — fuzzy match items, no OCR needed."""
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    canonical_data = load_canonical_prices()
    aliases = load_aliases()

    # Check for duplicate
    inv_number = data.get("invoice_number", "")
    supplier = data.get("supplier_name", "")
    if inv_number and supplier and not inv_number.startswith("MANUAL-"):
        skip = {"ingredient_aliases.json", "price_history.json"}
        for ef in os.listdir(INVOICES_DIR):
            if ef.endswith(".json") and ef not in skip:
                try:
                    edata = load_json(os.path.join(INVOICES_DIR, ef))
                    if (edata.get("invoice_number") == inv_number and
                        edata.get("supplier_name") == supplier):
                        return jsonify({"error": f"Duplicate: {supplier} #{inv_number}", "duplicate": True}), 409
                except (json.JSONDecodeError, KeyError):
                    continue

    # Fuzzy match each item
    matched_items = []
    for item in data.get("items", []):
        match = fuzzy_match_ingredient(item["item_name"], canonical_data, aliases)
        normalized_price = None
        price_change_pct = None
        internal_price = None
        if match["canonical_item"]:
            ci = match["canonical_item"]
            internal_price = ci["price_per_unit"]
            normalized_price = normalize_price(
                item.get("unit_price", 0), 1, item.get("unit", ""), ci["uom"], ci.get("buying_unit"))
            if normalized_price and internal_price > 0:
                price_change_pct = round((normalized_price - internal_price) / internal_price * 100, 1)

        matched_items.append({
            **item,
            "match": match,
            "internal_price": internal_price,
            "normalized_invoice_price": normalized_price,
            "price_change_pct": price_change_pct,
            "receiving_status": "received",
            "received_qty": item.get("quantity", 0),
        })

    result = {
        **data,
        "items": matched_items,
        "image_file": None,
        "processed_at": datetime.now().isoformat(),
    }
    return jsonify(result)


@app.route("/api/confirm-invoice", methods=["POST"])
def confirm_invoice():
    """Confirm reviewed invoice data, update prices, save record."""
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    canonical_data = load_canonical_prices()
    aliases = load_aliases()
    price_history = load_price_history()

    price_updates = []
    new_aliases = []
    today = date.today().isoformat()

    for item in data.get("items", []):
        match = item.get("match", {})
        canonical_name = item.get("confirmed_canonical_name") or match.get("canonical_name")
        if not canonical_name:
            continue

        invoice_name = item.get("item_name", "").strip().lower()

        # Save alias mapping
        if invoice_name and canonical_name:
            aliases[invoice_name] = canonical_name
            new_aliases.append({"invoice": invoice_name, "canonical": canonical_name})

        # Update price if chef confirmed a new price
        confirmed_price = item.get("confirmed_price")
        if confirmed_price is not None and confirmed_price > 0:
            for ci in canonical_data["items"]:
                if ci["ingredient"].strip().lower() == canonical_name.strip().lower():
                    old_price = ci["price_per_unit"]
                    change_pct = round((confirmed_price - old_price) / old_price * 100, 1) if old_price > 0 else 0

                    # Log price change
                    price_history.append({
                        "date": today,
                        "ingredient": ci["ingredient"],
                        "old_price": old_price,
                        "new_price": confirmed_price,
                        "change_pct": change_pct,
                        "supplier": data.get("supplier_name", ""),
                        "invoice_number": data.get("invoice_number", ""),
                        "uom": ci["uom"],
                    })

                    # Update canonical price
                    ci["price_per_unit"] = confirmed_price
                    ci["buying_price"] = item.get("unit_price", confirmed_price)

                    price_updates.append({
                        "ingredient": ci["ingredient"],
                        "old_price": old_price,
                        "new_price": confirmed_price,
                        "change_pct": change_pct,
                    })
                    break

    # Save updated data
    canonical_data["generated_date"] = today
    save_json(CANONICAL_PRICE_FILE, canonical_data)
    save_aliases(aliases)
    save_price_history(price_history)

    # Save confirmed invoice
    inv_number = data.get("invoice_number", "unknown")
    inv_date = data.get("invoice_date", today)
    safe_number = re.sub(r'[^\w\-]', '_', str(inv_number))
    invoice_filename = f"{inv_date}_{safe_number}.json"
    invoice_record = {
        **data,
        "confirmed_at": datetime.now().isoformat(),
        "price_updates": price_updates,
    }
    save_json(os.path.join(INVOICES_DIR, invoice_filename), invoice_record)

    # Regenerate dashboard in background
    try:
        build_script = os.path.join(BASE_DIR, "build_inventory_dashboard.py")
        subprocess.Popen([sys.executable, build_script],
                         cwd=BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass  # Non-blocking

    return jsonify({
        "success": True,
        "invoice_file": invoice_filename,
        "price_updates": price_updates,
        "aliases_added": len(new_aliases),
        "message": f"Invoice confirmed. {len(price_updates)} price(s) updated.",
    })


@app.route("/api/invoices")
def list_invoices():
    """List all confirmed invoices."""
    invoices = []
    skip = {"ingredient_aliases.json", "price_history.json"}
    for f in sorted(os.listdir(INVOICES_DIR), reverse=True):
        if f.endswith(".json") and f not in skip:
            try:
                data = load_json(os.path.join(INVOICES_DIR, f))
                invoices.append({
                    "filename": f,
                    "supplier_name": data.get("supplier_name", ""),
                    "invoice_number": data.get("invoice_number", ""),
                    "invoice_date": data.get("invoice_date", ""),
                    "grand_total": data.get("grand_total", 0),
                    "item_count": len(data.get("items", [])),
                    "price_updates": len(data.get("price_updates", [])),
                    "confirmed_at": data.get("confirmed_at", ""),
                })
            except (json.JSONDecodeError, KeyError):
                continue
    return jsonify({"invoices": invoices})


@app.route("/api/price-history")
def get_price_history():
    """Get price change history, optionally filtered by ingredient."""
    history = load_price_history()
    ingredient = request.args.get("ingredient", "").strip().lower()
    if ingredient:
        history = [h for h in history if h["ingredient"].strip().lower() == ingredient]
    # Most recent first
    history.reverse()
    return jsonify({"history": history})


@app.route("/api/daily-summary")
def daily_summary():
    """Generate daily receiving summary."""
    target_date = request.args.get("date", date.today().isoformat())
    invoices = []
    skip = {"ingredient_aliases.json", "price_history.json"}
    for f in os.listdir(INVOICES_DIR):
        if f.endswith(".json") and f not in skip:
            try:
                data = load_json(os.path.join(INVOICES_DIR, f))
                if data.get("invoice_date") == target_date:
                    invoices.append(data)
            except (json.JSONDecodeError, KeyError):
                continue

    total_spend = sum(inv.get("grand_total", 0) for inv in invoices)
    total_vat = sum(inv.get("vat_amount", 0) for inv in invoices)
    total_items = sum(len(inv.get("items", [])) for inv in invoices)

    price_history = load_price_history()
    today_changes = [h for h in price_history if h["date"] == target_date]
    increases = [h for h in today_changes if h["change_pct"] > 0]
    decreases = [h for h in today_changes if h["change_pct"] < 0]
    big_increases = [h for h in increases if h["change_pct"] > 10]

    return jsonify({
        "date": target_date,
        "total_invoices": len(invoices),
        "total_spend": round(total_spend, 2),
        "total_vat": round(total_vat, 2),
        "total_items": total_items,
        "price_increases": len(increases),
        "price_decreases": len(decreases),
        "big_increases_10pct": big_increases,
        "suppliers": list(set(inv.get("supplier_name", "") for inv in invoices)),
    })


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Invoice Server starting...")
    print(f"  Invoices dir: {INVOICES_DIR}")
    print(f"  Canonical prices: {CANONICAL_PRICE_FILE}")
    print(f"  Open http://localhost:5000 in your browser")
    app.run(host="0.0.0.0", port=5000, debug=False)
