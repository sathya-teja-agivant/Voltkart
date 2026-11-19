"""VoltKart assistant: Understand -> Retrieve -> Respond.

Division of labour
------------------
* UNDERSTAND (LLM + code): the LLM returns JSON that is validated with
  pydantic (`IntentResult`). Numbers (budget, RAM, storage) are always parsed
  by code and win over the LLM. If the LLM is unavailable or returns invalid
  JSON, a rule-based parser is used instead.
* RETRIEVE (code only): SQL filters, ranking, fuzzy product-name matching and
  FAQ lookup. Prices and specs always come straight from the database.
* RESPOND (LLM, grounded): the LLM only receives the retrieved rows / FAQ text.
  Its answer is then checked in code (every price and spec number must exist in
  the retrieved data). If the check fails, a deterministic answer is used.
"""
import difflib
import json
import logging
import re
from datetime import datetime, timezone
from decimal import Decimal

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Conversation,
    ConversationContext,
    Message,
    Policy,
    Product,
)
from app.schemas import IntentResult
from app.services.groq_service import GroqService, LLMError

logger = logging.getLogger(__name__)

NO_INFO = "I don't have that information available in the system."
DEFAULT_RESULT_LIMIT = 20  # show every match by default; "top 3" / "show 5" still narrows it
MAX_RESULT_LIMIT = 20

KNOWN_BRANDS = (
    "hp", "dell", "lenovo", "asus", "acer", "apple", "msi", "samsung", "lg",
    "gigabyte", "razer", "microsoft", "vivo", "huawei", "xiaomi", "realme",
)
BRAND_ALIASES = {"hewlett packard": "HP", "macbook": "Apple"}

# What the catalog does not store. We say so instead of guessing.
UNSUPPORTED_CATALOG_ATTRIBUTES = {
    "colour": ("colour", "color", "grey", "gray", "black", "silver", "white", "blue", "red", "gold"),
    "touchscreen": ("touchscreen", "touch screen", "touch-screen"),
    "graphics card": ("gpu", "graphics card", "dedicated graphics", "graphics"),
}

NEED_PATTERNS = {
    "battery": r"\b(battery|long[- ]lasting|all[- ]day|backup)\b",
    "portable": r"\b(light|lightweight|lighter|portable|travel|slim|thin|carry)\b",
    "performance": r"\b(coding|programming|developer|development|editing|video|design|heavy|performance|multitask\w*|data science|machine learning)\b",
    "student": r"\b(college|student|students|school|study|studying|university)\b",
    "office": r"\b(office|business|professional|meetings?)\b",
    "gaming": r"\b(gaming|games|gamer)\b",
}

NON_LAPTOP_RE = re.compile(
    r"\b(phones?|mobiles?|smartphones?|iphones?|tablets?|ipads?|tvs?|televisions?|"
    r"headphones?|earbuds?|airpods|smart ?watch(?:es)?|cameras?|printers?|"
    r"monitors?|keyboards?|mouse|mice|speakers?|consoles?|playstation|xbox|"
    r"fridges?|refrigerators?|washing machines?)\b"
)
ACCESSORY_RE = re.compile(
    r"\b(bags?|backpacks?|chargers?|sleeves?)\b"
    r"|\blaptop\s+(stands?|covers?|cases?|skins?|mouse|keyboards?|monitors?)\b"
)
POLICY_RE = re.compile(
    r"\b(returns?|returned|refunds?|warranty|warranties|guarantee|shipping|shipped|ship|"
    r"delivery|deliver|delivered|dispatch(?:ed)?|cancel|cancelled|cancellation|cancelling|"
    r"payments?|pay|paying|emis?|instal+ments?|cod|cash on delivery|exchange|replacement|"
    r"invoice|gst|policy|policies|track|tracking|order status|customer care|helpline|"
    r"damaged|defective|discounts?|coupons?|offers|cashback)\b"
)
COMPARE_RE = re.compile(
    r"\b(compare|comparison|versus|difference between|differences between|"
    r"which is better|better than)\b|\bvs\b\.?"
)
GREETING_RE = re.compile(r"^(hi+|hello|hey+|good (morning|afternoon|evening)|namaste|thanks|thank you|bye)\b")
RECOMMEND_RE = re.compile(
    r"\b(laptops?|notebooks?|recommend\w*|suggest\w*|cheapest|lightest|gaming|show me|find|"
    r"best|options?|budget|under|below|looking for|need|want|buy)\b"
)
FOLLOW_UP_RE = re.compile(
    r"\b(which|what) (of )?(these|those|them|one)\b|\b(among|from|out of) (these|those)\b|"
    r"\b(the first|the second|the third|the last|both of them|these two)\b|"
    r"\b(also show|sort these|rank these|which one|what about this|how about this)\b|"
    r"\b(is it|are they|does it|do they)\b|"
    r"\b(lighter|cheaper|less expensive|more affordable|better battery|longer battery|more battery)\b|"
    r"\b(anything|something|any) (else|lighter|cheaper|other|better|with)\b|"
    r"\b(other options|more options|show more|what else|any other)\b|"
    r"\b(best battery|longest battery|cheapest|lightest)\b.*\b(these|them)\b"
)
REFINE_PATTERNS = (
    ("lighter", r"\b(lighter|less heavy)\b"),
    ("cheaper", r"\b(cheaper|less expensive|lower price|more affordable)\b"),
    ("longer_battery", r"\b(better battery|longer battery|more battery|longer[- ]lasting)\b"),
)
# Topics a customer may ask about that the FAQ must explicitly cover before we
# are allowed to answer. If the FAQ text never mentions them we say NO_INFO.
GATED_TOPICS = (
    "emi", "emis", "installment", "installments", "instalment", "instalments",
    "discount", "discounts", "coupon", "coupons", "cashback", "insurance",
    "exchange offer", "trade-in", "trade in", "student discount",
)

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #
def json_safe(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _inr(value) -> str:
    """Indian digit grouping, e.g. 124990 -> ₹1,24,990."""
    n = int(round(float(value)))
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return ("-" if n < 0 else "") + "₹" + s


def _storage_label(gb: int) -> str:
    return f"{gb / 1000:g} TB" if gb >= 1000 else f"{gb} GB"


def _json_product(product: Product) -> dict:
    return {
        "product_id": str(product.product_id),
        "product_name": product.product_name,
        "brand": product.brand,
        "processor": product.processor,
        "ram_gb": product.ram,
        "storage_gb": product.storage,
        "display_size_inches": product.display_size,
        "battery_life_hours": product.battery_life,
        "weight_kg": product.weight,
        "operating_system": product.operating_system,
        "price_inr": float(product.price),
        "stock_status": product.stock_status,
        "warranty": product.warranty,
        "description": product.description,
    }


def _llm_facts(product: Product) -> dict:
    """Minimal, pre-formatted facts handed to the LLM (prices as strings so the
    model copies them instead of re-formatting numbers)."""
    return {
        "name": product.product_name,
        "brand": product.brand,
        "price": _inr(product.price),
        "processor": product.processor,
        "ram": f"{product.ram} GB",
        "storage": _storage_label(product.storage),
        "display": f"{product.display_size:g} inch",
        "battery": f"{product.battery_life:g} hours",
        "weight": f"{product.weight:g} kg",
        "os": product.operating_system,
        "warranty": product.warranty,
        "in_stock": product.stock_status == "IN_STOCK",
        "description": product.description,
    }


def _spec_line(p: Product) -> str:
    return (
        f"{p.processor}, {p.ram} GB RAM, {_storage_label(p.storage)} storage, "
        f"{p.display_size:g}\" display, {p.weight:g} kg, {p.battery_life:g} hours battery"
    )


# --------------------------------------------------------------------------- #
# UNDERSTAND - rule-based parsing (also the fallback when the LLM fails)
# --------------------------------------------------------------------------- #
_CUR = r"(?:₹|rs\.?|inr)?\s*"
_NUM = r"(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|lakhs?|lacs?)?"
_UNIT_AFTER = re.compile(r"\s*(gb|tb|kg|hours?|hrs?|h\b|inch|\")")


def _amount(num: str, suffix: str | None) -> int | None:
    try:
        value = float(num.replace(",", "").strip("."))
    except ValueError:
        return None
    if suffix in ("k", "thousand"):
        value *= 1_000
    elif suffix and suffix.startswith(("lakh", "lac")):
        value *= 100_000
    return int(round(value))


def _budget_matches(q: str, pattern: str):
    """Yield (amount, match) for amounts that look like money, not specs."""
    for m in re.finditer(pattern, q):
        groups = m.groups()
        # last two groups are always the (number, suffix) of the amount that matters
        num, suffix = groups[-2], groups[-1]
        if _UNIT_AFTER.match(q, m.end()) and not suffix:
            continue  # "under 16 gb" is a spec, not a budget
        amount = _amount(num, suffix)
        if amount is not None and amount >= 1000:
            yield amount, m


def _extract_budget(q: str) -> dict:
    """Return {'budget_min','budget_max','unparsed'} parsed from the query."""
    out: dict = {"budget_min": None, "budget_max": None, "unparsed": False}

    m = re.search(rf"\bbetween\s*{_CUR}{_NUM}\s*(?:and|to|-)\s*{_CUR}{_NUM}", q)
    if m:
        lo = _amount(m.group(1), m.group(2) or m.group(4))  # "40 and 60k" -> both thousands
        hi = _amount(m.group(3), m.group(4))
        if lo and hi and lo >= 1000 and hi >= 1000:
            out["budget_min"], out["budget_max"] = sorted((lo, hi))
            return out

    for amount, _ in _budget_matches(q, rf"\b(?:around|about|approx(?:imately)?|roughly|near)\s*{_CUR}{_NUM}"):
        out["budget_min"], out["budget_max"] = int(amount * 0.85), int(amount * 1.15)
        return out

    max_patterns = (
        rf"\b(?:under|below|less than|upto|up to|within|maximum|max|at most|not more than|"
        rf"budget(?: is| of| around)?|my budget)\s*(?:of\s*)?{_CUR}{_NUM}",
        rf"{_CUR}{_NUM}\s*(?:or less|and below|or below|max|maximum|budget)\b",
    )
    for pattern in max_patterns:
        for amount, _ in _budget_matches(q, pattern):
            out["budget_max"] = amount
            break
        if out["budget_max"]:
            break

    for amount, _ in _budget_matches(
        q, rf"\b(?:above|over|more than|at least|minimum|starting from|from)\s*{_CUR}{_NUM}"
    ):
        out["budget_min"] = amount
        break

    if out["budget_max"] is None and out["budget_min"] is None:
        # A budget word followed by a number we could not use as money.
        for m in re.finditer(rf"\b(?:under|below|within|budget|around|between)\b\s*{_CUR}(\d[\d,]*)", q):
            if not _UNIT_AFTER.match(q, m.end()):
                out["unparsed"] = True
                break
    return out


def _extract_memory(q: str) -> dict:
    """Parse RAM / storage constraints (GB or TB)."""
    out = {"ram_gb": None, "ram_operator": "eq", "storage_gb": None, "storage_operator": "eq"}
    kinds_ram = {"ram", "memory"}
    kinds_storage = {"ssd", "storage", "hdd", "nvme"}

    def classify(kind: str | None, value_gb: float, unit: str) -> str | None:
        if kind in kinds_ram:
            return "ram"
        if kind in kinds_storage or unit == "tb":
            return "storage"
        if value_gb in (4, 8, 12, 16, 24, 32, 64):
            return "ram"
        if value_gb in (128, 256, 512, 1000, 1024, 2000):
            return "storage"
        return None

    def operator(pre: str | None, post: str | None) -> str:
        if post or (pre and re.match(r"at ?least|minimum|min", pre)):
            return "gte"
        if pre and re.match(r"up ?to|maximum|max|at most", pre):
            return "lte"
        return "eq"

    spans = []
    num_first = re.compile(
        r"(?:(?P<pre>at ?least|minimum|min\.?|up ?to|maximum|max\.?|at most)\s*)?"
        r"(?P<n>\d+(?:\.\d+)?)\s*(?P<u>gb|tb)\b\s*"
        r"(?P<post>\+|or more|and above|or above|and more)?\s*"
        r"(?P<kind>ram|memory|ssd|storage|hdd|nvme)?"
    )
    for m in num_first.finditer(q):
        spans.append((m.start(), m.group("kind"), float(m.group("n")), m.group("u"), m.group("pre"), m.group("post")))
    kind_first = re.compile(r"\b(?P<kind>ram|memory|ssd|storage)\s*(?:of|:)?\s*(?P<n>\d+(?:\.\d+)?)\s*(?P<u>gb|tb)\b")
    for m in kind_first.finditer(q):
        spans.append((m.start(), m.group("kind"), float(m.group("n")), m.group("u"), None, None))

    for _, kind, n, unit, pre, post in sorted(spans):
        value_gb = n * 1000 if unit == "tb" else n
        target = classify(kind, value_gb, unit)
        if target == "ram" and out["ram_gb"] is None:
            out["ram_gb"], out["ram_operator"] = int(value_gb), operator(pre, post)
        elif target == "storage" and out["storage_gb"] is None:
            out["storage_gb"], out["storage_operator"] = int(value_gb), operator(pre, post)
    return out


def _extract_brand(q: str) -> str | None:
    for alias, brand in BRAND_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", q):
            return brand
    for brand in sorted(KNOWN_BRANDS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(brand)}\b", q):
            return "HP" if brand == "hp" else brand.title() if brand != "asus" else "ASUS"
    return None


def _extract_processor(q: str) -> str | None:
    patterns = (
        r"\bintel\s+core\s+ultra\s+[3579]\b", r"\bcore\s+ultra\s+[3579]\b",
        r"\bintel\s+core\s+i[3579]\b", r"\bcore\s+i[3579]\b", r"\bi[3579]\b",
        r"\bryzen\s+[3579]\b", r"\bapple\s+m[1234]\b", r"\bm[1234]\b",
    )
    for pattern in patterns:
        m = re.search(pattern, q)
        if m:
            value = m.group(0)
            if re.fullmatch(r"i[3579]", value):
                return "Intel Core " + value
            if value.startswith("core "):
                return "Intel " + value
            if re.fullmatch(r"m[1234]", value):
                return "Apple " + value
            return value
    return None


def _extract_result_limit(q: str) -> int:
    patterns = (
        r"\b(?:top|best|cheapest|lightest|show|list|give me)\s*(\d+|" + "|".join(NUMBER_WORDS) + r")\b",
        r"\b(\d+|" + "|".join(NUMBER_WORDS) + r")\s+(?:cheapest|cheaper|best|top|lightest|laptops|options|models)\b",
    )
    for pattern in patterns:
        m = re.search(pattern, q)
        if m:
            raw = m.group(1)
            n = int(raw) if raw.isdigit() else NUMBER_WORDS[raw]
            return max(1, min(n, MAX_RESULT_LIMIT))
    if re.search(r"\b(show|list) (me )?all\b", q):
        return MAX_RESULT_LIMIT
    return DEFAULT_RESULT_LIMIT


def _extract_needs(q: str) -> list[str]:
    return [name for name, pattern in NEED_PATTERNS.items() if re.search(pattern, q)]


def _extract_unsupported_attributes(q: str) -> list[str]:
    found = []
    for attribute, terms in UNSUPPORTED_CATALOG_ATTRIBUTES.items():
        if any(re.search(rf"\b{re.escape(t)}\b", q) for t in terms):
            found.append(attribute)
    return found


def _ordinal_indices(q: str) -> list[int]:
    """'first two' -> [0,1]; 'first and third' -> [0,2]; 'the last' -> [-1]."""
    m = re.search(r"\b(?:first|top)\s+(two|2|three|3)\b", q)
    if m:
        return list(range(2 if m.group(1) in ("two", "2") else 3))
    mapping = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2, "fourth": 3, "last": -1}
    found = []
    for m in re.finditer(r"\b(first|1st|second|2nd|third|3rd|fourth|last)\b", q):
        idx = mapping[m.group(1)]
        if idx not in found:
            found.append(idx)
    return found or [0, 1]


def heuristic_intent(query: str, context: dict | None = None) -> dict:
    """Rule-based understanding. Returns a dict shaped like IntentResult."""
    q = query.lower().strip()
    context = context or {}
    has_prev = bool(context.get("previous_recommendations"))

    budget = _extract_budget(q)
    memory = _extract_memory(q)
    brand = _extract_brand(q)
    processor = _extract_processor(q)
    needs = _extract_needs(q)

    refine = next((name for name, pattern in REFINE_PATTERNS if re.search(pattern, q)), None)
    sort_by = None
    if re.search(r"\b(lightest|lowest weight)\b", q):
        sort_by = "weight"
    elif re.search(r"\b(longest battery|best battery|highest battery)\b", q):
        sort_by = "battery"
    elif re.search(r"\b(cheapest|lowest price|least expensive)\b", q):
        sort_by = "price"
    elif refine:
        sort_by = {"lighter": "weight", "cheaper": "price", "longer_battery": "battery"}[refine]

    unparsed = []
    if budget["unparsed"]:
        unparsed.append("budget")
    if re.search(r"\d\s*(gb|tb)\b", q) and memory["ram_gb"] is None and memory["storage_gb"] is None:
        unparsed.append("RAM/storage size")

    has_filters = any((
        budget["budget_min"], budget["budget_max"], memory["ram_gb"], memory["storage_gb"],
        brand, processor, needs, sort_by,
    ))

    # --- intent -----------------------------------------------------------
    words = q.split()
    if GREETING_RE.match(q) and len(words) <= 4:
        intent = "greetings"
    elif (NON_LAPTOP_RE.search(q) and not re.search(r"\b(laptops?|notebooks?)\b", q)) or ACCESSORY_RE.search(q):
        intent = "out_of_scope"
    elif POLICY_RE.search(q):
        intent = "policy_query"
    elif COMPARE_RE.search(q):
        intent = "product_comparison"
    elif RECOMMEND_RE.search(q) or has_filters or (has_prev and (refine or FOLLOW_UP_RE.search(q))):
        intent = "product_recommendation"
    else:
        intent = "other"

    # --- follow-up ----------------------------------------------------------
    follow_up = False
    if has_prev:
        follow_up = bool(FOLLOW_UP_RE.search(q))
        # Short filter-only message such as "under 50000" or "only Dell".
        if not follow_up and intent == "product_recommendation" and has_filters and len(words) <= 6 \
                and not re.search(r"\b(laptops?|notebooks?|recommend\w*|show me|find)\b", q):
            follow_up = True

    return {
        "intent": intent,
        "is_follow_up": follow_up,
        "budget_min": budget["budget_min"],
        "budget_max": budget["budget_max"],
        "ram_gb": memory["ram_gb"],
        "ram_operator": memory["ram_operator"],
        "storage_gb": memory["storage_gb"],
        "storage_operator": memory["storage_operator"],
        "brand": brand,
        "processor": processor,
        "usage": "gaming" if "gaming" in needs else None,
        "needs": needs,
        "sort_by": sort_by,
        "refine": refine,
        "product_names": [],
        "clarifying_question": None,
        "result_limit": _extract_result_limit(q),
        "unsupported_attributes": _extract_unsupported_attributes(q),
        "unparsed": unparsed,
    }


# --------------------------------------------------------------------------- #
# UNDERSTAND - LLM step with validated JSON
# --------------------------------------------------------------------------- #
INTENT_SYSTEM_PROMPT = """You are the understanding step of VoltKart, an online LAPTOP store assistant.
Read the customer's latest message (and the short conversation state) and return ONE JSON object, nothing else.

Keys:
- "intent": one of
    "product_recommendation" (wants laptop suggestions / search / refine earlier suggestions),
    "product_comparison" (compare laptops, including "compare the first two"),
    "product_info" (asks about one specific named laptop),
    "policy_query" (returns, refunds, warranty, shipping, delivery, payment, EMI, cancellation, invoice, support),
    "greetings",
    "out_of_scope" (anything that is not laptops or store policy, e.g. phones, tablets, accessories),
    "clarify" (too vague to act on; put one short question in "clarifying_question"),
    "other".
- "is_follow_up": true only if the message depends on the previous suggestions ("anything lighter?", "compare the first two", "cheaper ones", "under 50000" after a search).
- "budget_min", "budget_max": integers in INR or null.
- "ram_gb", "storage_gb": integers (1 TB = 1000) or null; "ram_operator"/"storage_operator": "eq", "gte" or "lte".
- "brand": a laptop brand named by the customer or null. "processor": e.g. "Intel Core i5", "Ryzen 7" or null.
- "usage": "gaming" or null.
- "needs": subset of ["battery","portable","performance","student","office","gaming"].
- "sort_by": "price", "weight", "battery" or null (only for explicit cheapest / lightest / longest battery).
- "refine": "lighter", "cheaper", "longer_battery" or null (relative to the previously shown laptops).
- "product_names": laptop model names the customer typed.
- "clarifying_question": string or null.
Never invent values the customer did not state. Use null when unsure."""


def _llm_intent(groq: GroqService, query: str, context: dict) -> IntentResult | None:
    if not getattr(groq, "available", False):
        return None
    state = {
        "message": query,
        "conversation_state": {
            "active_constraints": context.get("active_constraints", {}),
            "last_shown_laptops": context.get("previous_names", []),
            "last_compared_laptops": context.get("previous_comparison_names", []),
            "recent_user_messages": context.get("recent_searches", [])[-3:],
        },
    }
    try:
        raw = groq.complete_json(INTENT_SYSTEM_PROMPT, json_safe(state))
        return IntentResult.model_validate(raw)
    except (LLMError, ValidationError) as exc:
        logger.warning("LLM intent rejected, using rule-based parser: %s", exc)
        return None


def detect_intent(groq: GroqService, query: str, context: dict) -> dict:
    """LLM understanding validated by pydantic, merged with code-parsed numbers.

    Returns a dict shaped like IntentResult plus 'source' ('llm' | 'rules').
    """
    rules = heuristic_intent(query, context)
    llm = _llm_intent(groq, query, context)
    if llm is None:
        rules["source"] = "rules"
        return rules

    merged = dict(rules)
    merged["source"] = "llm"
    llm_d = llm.model_dump()
    q = query.lower()

    # Intent: trust the LLM, except where code has a hard, reliable signal.
    intent = llm_d["intent"]
    if rules["intent"] == "out_of_scope":
        intent = "out_of_scope"
    elif intent == "other" and rules["intent"] != "other":
        intent = rules["intent"]
    merged["intent"] = intent

    # Numeric constraints: code-parsed values win; LLM only fills gaps, and only
    # when the number really appears in the customer's message.
    for key in ("budget_min", "budget_max"):
        if merged[key] is None and llm_d[key] and 10_000 <= llm_d[key] <= 1_000_000:
            merged[key] = llm_d[key]
    for key, op_key in (("ram_gb", "ram_operator"), ("storage_gb", "storage_operator")):
        if merged[key] is None and llm_d[key]:
            digits = str(llm_d[key] // 1000 if llm_d[key] >= 1000 else llm_d[key])
            if re.search(rf"\b{digits}\b", q):
                merged[key], merged[op_key] = llm_d[key], llm_d[op_key]
    if merged["brand"] is None and llm_d["brand"] and llm_d["brand"].lower() in KNOWN_BRANDS:
        merged["brand"] = "HP" if llm_d["brand"].lower() == "hp" else llm_d["brand"].title()
    if merged["processor"] is None and llm_d["processor"]:
        merged["processor"] = llm_d["processor"]
    for key in ("sort_by", "refine"):
        if merged[key] is None:
            merged[key] = llm_d[key]
    if merged["usage"] is None and llm_d["usage"] == "gaming":
        merged["usage"] = "gaming"
    merged["needs"] = sorted(set(merged["needs"]) | {n for n in llm_d["needs"] if n in NEED_PATTERNS})
    merged["is_follow_up"] = bool(
        (rules["is_follow_up"] or llm_d["is_follow_up"]) and context.get("previous_recommendations")
    )
    merged["product_names"] = llm_d["product_names"]
    merged["clarifying_question"] = llm_d["clarifying_question"]
    return merged


# --------------------------------------------------------------------------- #
# RETRIEVE - products
# --------------------------------------------------------------------------- #
FILTER_KEYS = (
    "budget_min", "budget_max", "ram_gb", "ram_operator", "storage_gb", "storage_operator",
    "brand", "processor", "usage", "needs", "sort_by",
)
LEGACY_KEYS = {"budget": "budget_max", "ram": "ram_gb", "storage": "storage_gb"}


def _normalize_constraints(raw: dict | None) -> dict:
    """Read constraints saved by older versions of the app."""
    out = {}
    for key, value in (raw or {}).items():
        out[LEGACY_KEYS.get(key, key)] = value
    return {k: v for k, v in out.items() if k in FILTER_KEYS and v not in (None, [], "")}


def _build_filters(detected: dict, prior: dict) -> dict:
    fresh = {k: detected.get(k) for k in FILTER_KEYS if detected.get(k) not in (None, [], "")}
    for value_key, op_key in (("ram_gb", "ram_operator"), ("storage_gb", "storage_operator")):
        if value_key not in fresh:
            fresh.pop(op_key, None)
    if not detected.get("is_follow_up"):
        return fresh
    merged = {**_normalize_constraints(prior), **fresh}
    merged["needs"] = sorted(set(prior.get("needs", [])) | set(fresh.get("needs", []))) or None
    return {k: v for k, v in merged.items() if v not in (None, [], "")}


def _apply_numeric(column, value, operator, stmt):
    if operator == "gte":
        return stmt.where(column >= value)
    if operator == "lte":
        return stmt.where(column <= value)
    return stmt.where(column == value)


def query_products(db: Session, filters: dict) -> list[Product]:
    """All IN_STOCK products that satisfy the hard filters (unranked)."""
    stmt = select(Product).where(Product.stock_status == "IN_STOCK")
    if filters.get("brand"):
        stmt = stmt.where(Product.brand.ilike(str(filters["brand"])))
    if filters.get("budget_max") is not None:
        stmt = stmt.where(Product.price <= Decimal(str(filters["budget_max"])))
    if filters.get("budget_min") is not None:
        stmt = stmt.where(Product.price >= Decimal(str(filters["budget_min"])))
    if filters.get("ram_gb") is not None:
        stmt = _apply_numeric(Product.ram, int(filters["ram_gb"]), filters.get("ram_operator", "eq"), stmt)
    if filters.get("storage_gb") is not None:
        stmt = _apply_numeric(Product.storage, int(filters["storage_gb"]), filters.get("storage_operator", "eq"), stmt)
    if filters.get("processor"):
        stmt = stmt.where(Product.processor.ilike(f"%{str(filters['processor']).strip()}%"))
    products = list(db.scalars(stmt).all())
    if filters.get("usage") == "gaming":
        terms = ("gaming", "game", "victus", "loq", "tuf")
        products = [
            p for p in products
            if any(t in f"{p.product_name} {p.description}".lower() for t in terms)
        ]
    return products


def _minmax(values: list[float]):
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    return lambda v: (v - lo) / span


def rank_products(products: list[Product], filters: dict) -> list[Product]:
    """Rank by an explicit sort (cheapest / lightest / best battery) or, when the
    customer described needs, by a weighted score over catalog specs."""
    if len(products) <= 1:
        return list(products)
    sort_by = filters.get("sort_by")
    tie = lambda p: (float(p.price), p.product_name.lower())  # noqa: E731
    if sort_by == "weight":
        return sorted(products, key=lambda p: (float(p.weight), *tie(p)))
    if sort_by == "battery":
        return sorted(products, key=lambda p: (-float(p.battery_life), *tie(p)))
    if sort_by == "price":
        return sorted(products, key=tie)

    needs = set(filters.get("needs") or [])
    w = {"battery": 1.0, "light": 1.0, "ram": 1.0, "storage": 0.5, "price": 0.5}
    if "battery" in needs:
        w["battery"] = 4.0
    if "portable" in needs:
        w["light"] = 3.0
        w["battery"] = max(w["battery"], 1.5)
    if needs & {"performance", "gaming"}:
        w.update(ram=2.5, storage=1.5, battery=min(w["battery"], 0.5) if "battery" not in needs else w["battery"],
                 light=min(w["light"], 0.5) if "portable" not in needs else w["light"], price=0.0)
    if "student" in needs:
        w["battery"] = max(w["battery"], 2.0)
        w["light"] = max(w["light"], 1.5)
        w["price"] = max(w["price"], 0.75)
    if "office" in needs:
        w["battery"] = max(w["battery"], 2.0)

    nb = _minmax([p.battery_life for p in products])
    nw = _minmax([p.weight for p in products])
    nr = _minmax([p.ram for p in products])
    ns = _minmax([p.storage for p in products])
    npr = _minmax([float(p.price) for p in products])

    def score(p: Product) -> float:
        return (
            w["battery"] * nb(p.battery_life)
            + w["light"] * (1 - nw(p.weight))
            + w["ram"] * nr(p.ram)
            + w["storage"] * ns(p.storage)
            + w["price"] * (1 - npr(float(p.price)))
        )

    return sorted(products, key=lambda p: (-score(p), *tie(p)))


def _refine_candidates(candidates: list[Product], previous: list[Product], refine: str) -> list[Product]:
    """Keep only products strictly better than everything shown before."""
    if not previous:
        return candidates
    if refine == "lighter":
        limit = min(p.weight for p in previous)
        return [p for p in candidates if p.weight < limit]
    if refine == "cheaper":
        limit = min(float(p.price) for p in previous)
        return [p for p in candidates if float(p.price) < limit]
    if refine == "longer_battery":
        limit = max(p.battery_life for p in previous)
        return [p for p in candidates if p.battery_life > limit]
    return candidates


def _load_products(db: Session, ids: list[str]) -> list[Product]:
    """Load products preserving the order of `ids` (SQL IN does not)."""
    if not ids:
        return []
    from uuid import UUID
    uuids = []
    for raw in ids:
        try:
            uuids.append(UUID(str(raw)))
        except ValueError:
            continue
    rows = {p.product_id: p for p in db.scalars(select(Product).where(Product.product_id.in_(uuids))).all()}
    return [rows[u] for u in uuids if u in rows]


# --------------------------------------------------------------------------- #
# RETRIEVE - fuzzy product-name matching
# --------------------------------------------------------------------------- #
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def _tok_eq(a: str, b: str) -> bool:
    if a == b:
        return True
    if len(a) >= 5 and len(b) >= 5 and not a.isdigit() and not b.isdigit():
        return difflib.SequenceMatcher(None, a, b).ratio() >= 0.85
    return False


def _find_named_products(db: Session, text: str) -> list[Product]:
    """Find laptops named in `text`, in the order mentioned.

    'Inspiron 15' matches 'Inspiron 15 3530'; 'IdeaPad Slim 5' beats
    'IdeaPad Slim 3'; typos such as 'Inspirion' still match. An ambiguous
    mention ('MacBook Air') returns every equally good candidate.
    """
    q_tokens = _TOKEN_RE.findall(text.lower())
    if not q_tokens:
        return []
    spans = []
    for product in db.scalars(select(Product)).all():
        name_tokens = _TOKEN_RE.findall(product.product_name.lower())
        need = min(2, len(name_tokens))
        for i in range(len(q_tokens)):
            k = 0
            while k < len(name_tokens) and i + k < len(q_tokens) and _tok_eq(q_tokens[i + k], name_tokens[k]):
                k += 1
            if k >= need:
                spans.append((i, k, product))
    spans.sort(key=lambda s: (-s[1], s[0]))
    used: set[int] = set()
    groups: dict[tuple[int, int], list[Product]] = {}
    for i, k, product in spans:
        key = (i, k)
        if key in groups:
            groups[key].append(product)
            continue
        positions = set(range(i, i + k))
        if positions & used:
            continue
        used |= positions
        groups[key] = [product]
    result: list[Product] = []
    for (_, _), products in sorted(groups.items(), key=lambda kv: kv[0][0]):
        for product in products:
            if product not in result:
                result.append(product)
    return result[:4]


# --------------------------------------------------------------------------- #
# RETRIEVE - FAQ
# --------------------------------------------------------------------------- #
FAQ_STOPWORDS = {
    "what", "whats", "your", "about", "tell", "does", "have", "please", "the", "and", "for",
    "are", "can", "how", "long", "will", "you", "any", "with", "from", "that", "this", "there",
    "when", "which", "where", "laptop", "laptops", "store", "voltkart", "get", "was", "did",
    "its", "not", "but", "has", "had", "who", "why", "much", "many", "take", "takes",
    "need", "want", "know", "give", "buy", "sell", "offer", "offers",
}
FAQ_SYNONYMS = {
    r"\brefund|\breturn|\bexchange|\bmoney back": ["return", "refund"],
    r"\bship|\bdeliver|\bdispatch|\bcourier|\bpin ?code": ["shipping", "delivery"],
    r"\btrack|\border status|\bwhere is my order": ["tracking"],
    r"\bpay|\bupi|\bcard|\bcod\b|\bcash on delivery|\bnet banking": ["payment"],
    r"\bcancel": ["cancel"],
    r"\binvoice|\bgst|\bbill": ["invoice"],
    r"\bdamage|\bdefect|\bfaulty|\bbroken|\bdead on arrival": ["damage", "defect"],
    r"\bwarranty|\bguarantee|\bservice cent": ["warranty"],
    r"\bsupport|\bcontact|\bhelpline|\bcustomer care|\bcall you|\bemail": ["support"],
}


def _faq_terms(query: str) -> set[str]:
    q = query.lower()
    terms = {t[:6] for t in re.findall(r"[a-z]{3,}", q) if t not in FAQ_STOPWORDS}
    for pattern, extra in FAQ_SYNONYMS.items():
        if re.search(pattern, q):
            terms.update(e[:6] for e in extra)
    return terms


def retrieve_policy_scored(db: Session, query: str, limit: int = 3) -> list[tuple[int, Policy]]:
    """Rank active FAQ entries by how many query terms they contain."""
    terms = _faq_terms(query)
    if not terms:
        return []
    scored = []
    for policy in db.scalars(select(Policy).where(Policy.is_active.is_(True))).all():
        head = f"{policy.title} {policy.category}".lower()
        body = policy.content.lower()
        score = sum(3 for t in terms if t in head) + sum(1 for t in terms if t in body)
        if score > 0:
            scored.append((score, policy))
    scored.sort(key=lambda s: (-s[0], s[1].title))
    return scored[:limit]


def retrieve_policy(db: Session, query: str, limit: int = 3) -> list[Policy]:
    return [p for _, p in retrieve_policy_scored(db, query, limit)]


def _faq_cannot_answer(db: Session, query: str) -> bool:
    """True if the question is about a topic (EMI, discounts ...) that no active
    FAQ entry mentions. Deterministic, so the LLM can't improvise a policy."""
    q = query.lower()
    asked = [t for t in GATED_TOPICS if re.search(rf"\b{re.escape(t)}\b", q)]
    if not asked:
        return False
    corpus = " ".join(
        f"{p.title} {p.content}".lower()
        for p in db.scalars(select(Policy).where(Policy.is_active.is_(True))).all()
    )
    return any(t not in corpus for t in asked)


# --------------------------------------------------------------------------- #
# RESPOND - grounding checks
# --------------------------------------------------------------------------- #
def _close(value: float, allowed: set[float], tol: float = 0.011) -> bool:
    return any(abs(value - a) <= tol for a in allowed)


def _answer_is_grounded(answer: str, products: list[Product], extra_money: tuple[int, ...] = ()) -> bool:
    """Every ₹ amount and GB/kg/hour/inch figure in the answer must exist in the
    retrieved rows (or be a simple difference between two rows)."""
    prices = {int(round(float(p.price))) for p in products}
    money = set(prices) | {abs(a - b) for a in prices for b in prices} | set(extra_money)
    for m in re.finditer(r"(?:₹|\brs\.?|\binr)\s*(\d[\d,]*(?:\.\d+)?)", answer, flags=re.IGNORECASE):
        try:
            value = float(m.group(1).replace(",", "").strip("."))
        except ValueError:
            return False
        if value not in money:
            return False

    def diffs(values: list[float]) -> set[float]:
        base = set(values)
        return base | {round(abs(a - b), 2) for a in values for b in values}

    allowed = {
        "gb": diffs([p.ram for p in products] + [p.storage for p in products]),
        "tb": {p.storage / 1000 for p in products},
        "kg": diffs([p.weight for p in products]),
        "hours": diffs([p.battery_life for p in products]),
        "inch": diffs([p.display_size for p in products]),
    }
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(gb|tb|kg|hours?|hrs?|h|inch(?:es)?|\")(?![a-z])", answer, flags=re.IGNORECASE):
        value, unit = float(m.group(1)), m.group(2).lower()
        key = {"gb": "gb", "tb": "tb", "kg": "kg", "inch": "inch", "inches": "inch", '"': "inch"}.get(unit, "hours")
        if not _close(value, allowed[key]):
            return False
    return True


def _llm_text(groq: GroqService, system: str, payload: dict) -> str | None:
    if not getattr(groq, "available", False):
        return None
    try:
        return groq.answer(system, json_safe(payload))
    except LLMError:
        return None


# --------------------------------------------------------------------------- #
# RESPOND - recommendations
# --------------------------------------------------------------------------- #
RECOMMEND_SYSTEM_PROMPT = (
    "You are VoltKart's laptop shopping assistant. Use ONLY the products in the JSON. "
    "Use only these facts; if something isn't listed, say so. Never invent specs, prices, "
    "products or availability, and never mention products that are not in the JSON. "
    "Copy prices exactly as given (e.g. ₹57,990). Start with one friendly sentence, then give "
    "one short sentence (max 25 words) per product, in the given order, explaining why it fits the "
    "customer's stated needs, using only listed facts. If the customer asked for something the data "
    "does not contain (colour, GPU, touchscreen), say you don't have that information. "
    "Plain text, no tables."
)


def _reason(p: Product, needs: set[str], filters: dict) -> str:
    bits = []
    if "battery" in needs:
        bits.append(f"{p.battery_life:g} hours of battery")
    if "portable" in needs or filters.get("sort_by") == "weight":
        bits.append(f"light at {p.weight:g} kg")
    if needs & {"performance", "gaming"}:
        bits.append(f"{p.ram} GB RAM with {p.processor}")
    if "student" in needs and not bits:
        bits.append(f"{p.battery_life:g} hours of battery at {p.weight:g} kg for campus use")
    if filters.get("sort_by") == "price" and not bits:
        bits.append("one of the lowest prices that match")
    if filters.get("sort_by") == "battery" and not bits:
        bits.append(f"{p.battery_life:g} hours of battery")
    if not bits:
        bits.append(f"{p.ram} GB RAM, {_storage_label(p.storage)} storage and {p.battery_life:g} hours of battery")
    budget = filters.get("budget_max")
    if budget:
        bits.append(f"within your {_inr(budget)} budget")
    return ", ".join(bits)


def _fallback_recommendation(products: list[Product], filters: dict) -> str:
    needs = set(filters.get("needs") or [])
    lines = [f"Here are {len(products)} matching laptop{'s' if len(products) != 1 else ''} from our catalog:"]
    for i, p in enumerate(products, 1):
        lines.append(
            f"{i}. {p.product_name} ({p.brand}) - {_inr(p.price)}. {_spec_line(p)}. "
            f"Why: {_reason(p, needs, filters)}."
        )
    return "\n".join(lines)


def _recommendation_answer(groq, user_message: str, products: list[Product], filters: dict) -> str:
    needs = set(filters.get("needs") or [])
    payload = {
        "customer_message": user_message,
        "customer_needs": sorted(needs),
        "constraints": {k: v for k, v in filters.items() if k not in ("needs",)},
        "products": [_llm_facts(p) for p in products],
    }
    text = _llm_text(groq, RECOMMEND_SYSTEM_PROMPT, payload)
    extra = tuple(v for v in (filters.get("budget_min"), filters.get("budget_max")) if v)
    if text and _answer_is_grounded(text, products, extra):
        return text
    if text:
        logger.warning("Recommendation answer failed grounding check; using fallback")
    return _fallback_recommendation(products, filters)


# --------------------------------------------------------------------------- #
# RESPOND - comparison
# --------------------------------------------------------------------------- #
def _comparison_table(products: list[Product]) -> dict:
    spec_rows = (
        ("Brand", lambda p: p.brand),
        ("Price", lambda p: _inr(p.price)),
        ("Processor", lambda p: p.processor),
        ("RAM", lambda p: f"{p.ram} GB"),
        ("Storage", lambda p: _storage_label(p.storage)),
        ("Display", lambda p: f"{p.display_size:g} inch"),
        ("Battery", lambda p: f"{p.battery_life:g} hours"),
        ("Weight", lambda p: f"{p.weight:g} kg"),
        ("Operating system", lambda p: p.operating_system),
        ("Warranty", lambda p: p.warranty),
        ("Availability", lambda p: "In stock" if p.stock_status == "IN_STOCK" else "Out of stock"),
    )
    return {
        "columns": [p.product_name for p in products],
        "rows": [{"label": label, "values": [fn(p) for p in products]} for label, fn in spec_rows],
    }


def _fallback_verdict(products: list[Product]) -> str:
    wins: dict[str, list[str]] = {p.product_name: [] for p in products}

    def check(label: str, key, lower_better: bool):
        values = [key(p) for p in products]
        if len(set(values)) == 1:
            return
        best = min(values) if lower_better else max(values)
        winners = [p for p in products if key(p) == best]
        if len(winners) == 1:
            wins[winners[0].product_name].append(label)

    check("price (lower)", lambda p: float(p.price), True)
    check("battery life", lambda p: p.battery_life, False)
    check("weight (lighter)", lambda p: p.weight, True)
    check("RAM", lambda p: p.ram, False)
    check("storage", lambda p: p.storage, False)

    parts = [f"{name} is ahead on {', '.join(w)}." for name, w in wins.items() if w]
    if not parts:
        return "These laptops have identical specs and price in our catalog."
    ranked = sorted(wins.items(), key=lambda kv: -len(kv[1]))
    if len(ranked) > 1 and len(ranked[0][1]) > len(ranked[1][1]):
        parts.append(f"Overall, {ranked[0][0]} wins more of the compared specs; choose the other if its strengths matter more to you.")
    else:
        parts.append("They are closely matched, so pick based on which strengths matter most to you.")
    return " ".join(parts)


COMPARE_SYSTEM_PROMPT = (
    "You are VoltKart's laptop shopping assistant. Use ONLY the products in the JSON. "
    "Use only these facts; if something isn't listed, say so. A spec table is already shown to the "
    "customer, so do not repeat it. Write a short verdict of at most 3 sentences: what each laptop "
    "is better at and who should pick which. Copy prices and numbers exactly as given. "
    "Plain text only."
)


def _comparison_answer(groq, user_message: str, products: list[Product]) -> str:
    notes = []
    for p in products:
        if p.stock_status != "IN_STOCK":
            notes.append(f"Note: {p.product_name} is currently out of stock.")
    text = _llm_text(groq, COMPARE_SYSTEM_PROMPT, {
        "customer_message": user_message,
        "products": [_llm_facts(p) for p in products],
    })
    if text and _answer_is_grounded(text, products):
        verdict = text
    else:
        verdict = _fallback_verdict(products)
    return " ".join(["Here is a side-by-side comparison.", verdict] + notes)


# --------------------------------------------------------------------------- #
# RESPOND - single product, policy, misc
# --------------------------------------------------------------------------- #
INFO_SYSTEM_PROMPT = (
    "You are VoltKart's laptop shopping assistant. Answer the customer's question about the "
    "laptop(s) in the JSON using ONLY these facts; if something isn't listed, say you don't have "
    "that information. Do not invent specs, prices or availability. Copy prices and numbers "
    "exactly as given. Plain text, maximum 80 words."
)


def _product_info_answer(groq, user_message: str, products: list[Product]) -> str:
    text = _llm_text(groq, INFO_SYSTEM_PROMPT, {
        "customer_message": user_message,
        "products": [_llm_facts(p) for p in products],
    })
    if text and _answer_is_grounded(text, products):
        return text
    lines = []
    for p in products:
        stock = "In stock" if p.stock_status == "IN_STOCK" else "Currently out of stock"
        lines.append(f"{p.product_name} ({p.brand}) - {_inr(p.price)}. {_spec_line(p)}. {p.warranty}. {stock}.")
    return "\n".join(lines)


POLICY_SYSTEM_PROMPT = (
    "You are VoltKart customer support. Answer using only the supplied policy records. "
    "Use only these facts; if something isn't listed, say so. Do not invent terms, numbers or "
    "timelines. If the records do not answer the question, say exactly: " + NO_INFO
)


def _policy_answer(db: Session, groq, user_message: str) -> str:
    if _faq_cannot_answer(db, user_message):
        return NO_INFO
    scored = retrieve_policy_scored(db, user_message)
    if not scored:
        return NO_INFO
    records = [{"title": p.title, "content": p.content} for _, p in scored]
    # Without the LLM, show only the entries that are close to the best match.
    top = scored[0][0]
    fallback = "\n".join(f"{p.title}: {p.content}" for sc, p in scored if sc >= 0.6 * top)
    text = _llm_text(groq, POLICY_SYSTEM_PROMPT, {"question": user_message, "policy_records": records})
    if not text:
        return fallback
    allowed = set(re.findall(r"\d+", " ".join(r["content"] for r in records) + " " + user_message))
    if not set(re.findall(r"\d+", text)) <= allowed:
        logger.warning("Policy answer contained numbers not in the FAQ; using raw FAQ text")
        return fallback
    return text


GREETING_TEXT = (
    "Hello! I'm VoltKart's laptop shopping assistant. I can recommend laptops, compare models, "
    "and answer questions about returns, warranty, shipping and payments."
)
OUT_OF_SCOPE_TEXT = (
    "VoltKart sells laptops only, so I can't help with that. I can recommend laptops, compare "
    "models or answer questions about store policies."
)
OTHER_TEXT = (
    "I can help with laptop recommendations, comparisons and VoltKart store policies. "
    "What would you like to know?"
)
CLARIFY_TEXT = (
    "Happy to help you pick a laptop. What is your budget, and what will you mainly use it for "
    "(for example college, coding, gaming or travel)?"
)


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def _persistable(filters: dict) -> dict:
    out = {k: v for k, v in filters.items() if k in FILTER_KEYS and v not in (None, [], "")}
    for value_key, op_key in (("ram_gb", "ram_operator"), ("storage_gb", "storage_operator")):
        if value_key not in out:
            out.pop(op_key, None)
    return out


def handle_chat(db: Session, groq: GroqService, conversation: Conversation, user_message: str) -> dict:
    context_row = conversation.context
    if context_row is None:
        context_row = ConversationContext(conversation_id=conversation.conversation_id)
        db.add(context_row)
        db.flush()

    prev_rec_ids = list(context_row.previous_recommendations or [])
    prev_cmp_ids = list(context_row.previous_comparisons or [])
    prev_products = _load_products(db, prev_rec_ids)
    prior_context = {
        "active_constraints": _normalize_constraints(context_row.active_constraints),
        "previous_recommendations": prev_rec_ids,
        "previous_comparisons": prev_cmp_ids,
        "previous_names": [p.product_name for p in prev_products],
        "previous_comparison_names": [p.product_name for p in _load_products(db, prev_cmp_ids)],
        "recent_searches": list(context_row.recent_searches or []),
    }

    detected = detect_intent(groq, user_message, prior_context)
    intent = detected["intent"]

    named = _find_named_products(db, " ".join([user_message] + list(detected.get("product_names") or [])))
    if named and intent not in ("policy_query", "product_comparison", "greetings", "out_of_scope"):
        intent = "product_info"

    result_products: list[Product] = []
    comparison = None
    message_type = "TEXT"
    notes: list[str] = []

    if intent == "product_recommendation":
        filters = _build_filters(detected, prior_context["active_constraints"])
        if not filters and not detected.get("is_follow_up"):
            intent = "clarify"
        else:
            message_type = "RECOMMENDATION"
            limit = detected.get("result_limit") or DEFAULT_RESULT_LIMIT
            refine = detected.get("refine") if detected.get("is_follow_up") else None
            if detected.get("unsupported_attributes"):
                notes.append(
                    "Note: our catalog does not list "
                    + ", ".join(detected["unsupported_attributes"])
                    + ", so I could not filter by that."
                )
            if detected.get("unparsed"):
                notes.append(
                    "Note: I couldn't read your " + " or ".join(detected["unparsed"])
                    + " requirement, so I did not apply it. Try e.g. 'under ₹60,000' or '16GB RAM'."
                )

            candidates = query_products(db, filters)
            narrowed = _refine_candidates(candidates, prev_products, refine) if refine else candidates
            if refine and not narrowed and candidates and prev_products:
                if refine == "lighter":
                    ref = min(prev_products, key=lambda p: p.weight)
                    text = f"lighter than {ref.product_name} ({ref.weight:g} kg), the lightest I showed"
                elif refine == "cheaper":
                    ref = min(prev_products, key=lambda p: float(p.price))
                    text = f"cheaper than {ref.product_name} ({_inr(ref.price)}), the cheapest I showed"
                else:
                    ref = max(prev_products, key=lambda p: p.battery_life)
                    text = f"longer-lasting than {ref.product_name} ({ref.battery_life:g} hours), the best battery I showed"
                notes.append(
                    f"Note: no in-stock laptop meeting your requirements is {text}, "
                    "so these are the best options available."
                )
                narrowed = candidates
            result_products = rank_products(narrowed, filters)[:limit]

            if result_products:
                body = _recommendation_answer(groq, user_message, result_products, filters)
            else:
                body = (
                    "I couldn't find in-stock laptops matching all those requirements in our catalog. "
                    "I haven't dropped any of your filters."
                )
                if filters.get("budget_max"):
                    looser = query_products(db, {**filters, "budget_max": None})
                    if looser:
                        cheapest = min(looser, key=lambda p: float(p.price))
                        body += (
                            f" The cheapest laptop that meets your other requirements is "
                            f"{cheapest.product_name} at {_inr(cheapest.price)}."
                        )
                    else:
                        body += " Try relaxing one requirement."
                else:
                    body += " Try relaxing one requirement."
            answer = body

            context_row.active_constraints = _persistable(filters)
            if result_products:
                context_row.previous_recommendations = [str(p.product_id) for p in result_products]
                context_row.previous_comparisons = []

    if intent == "product_comparison":
        message_type = "COMPARISON"
        products: list[Product] = []
        if len(named) >= 2:
            products = named[:3]
        elif len(named) == 1:
            others = [p for p in prev_products if p.product_id != named[0].product_id]
            products = [named[0]] + others[:1]
        else:
            idx = _ordinal_indices(user_message.lower())
            explicit = bool(re.search(r"\b(first|second|third|last|top|1st|2nd|3rd)\b", user_message.lower()))
            source = prev_products
            if not explicit and prev_cmp_ids:
                source = _load_products(db, prev_cmp_ids)
            for i in idx:
                try:
                    p = source[i]
                except IndexError:
                    continue
                if p not in products:
                    products.append(p)
            products = products[:3]

        if len(products) < 2:
            answer = (
                "I need two laptops to compare. Tell me both model names, or ask for "
                "recommendations first and then say 'compare the first two'."
            )
            message_type = "TEXT"
        else:
            result_products = products
            comparison = _comparison_table(products)
            answer = _comparison_answer(groq, user_message, products)
            context_row.previous_comparisons = [str(p.product_id) for p in products]

    elif intent == "product_info":
        message_type = "PRODUCT_INFO"
        result_products = named[:2]
        answer = _product_info_answer(groq, user_message, result_products)

    elif intent == "policy_query":
        message_type = "POLICY_RESPONSE"
        answer = _policy_answer(db, groq, user_message)

    elif intent == "greetings":
        answer = GREETING_TEXT

    elif intent == "out_of_scope":
        answer = OUT_OF_SCOPE_TEXT

    elif intent == "clarify":
        answer = detected.get("clarifying_question") or CLARIFY_TEXT
        if detected.get("unparsed"):
            answer = ("I couldn't read your " + " or ".join(detected["unparsed"])
                      + " requirement (try e.g. 'under ₹60,000'). " + answer)

    elif intent == "other":
        answer = OTHER_TEXT

    if intent == "product_recommendation" and notes:
        answer = answer + "\n\n" + " ".join(notes)

    payload = {
        "products": [_json_product(p) for p in result_products],
        "comparison": comparison,
    }
    context_row.recent_searches = (list(context_row.recent_searches or []))[-9:] + [user_message]
    db.add(Message(
        conversation_id=conversation.conversation_id,
        sender_type="USER",
        message_type="TEXT",
        message_content=user_message,
    ))
    db.add(Message(
        conversation_id=conversation.conversation_id,
        sender_type="ASSISTANT",
        message_type=message_type,
        message_content=answer,
        payload=payload if (result_products or comparison) else None,
    ))
    conversation.last_message_at = datetime.now(timezone.utc)
    if conversation.title == "New conversation":
        conversation.title = user_message[:60]
    db.commit()

    return {
        "conversation_id": str(conversation.conversation_id),
        "intent": intent,
        "answer": answer,
        "products": payload["products"],
        "comparison": comparison,
        "active_constraints": context_row.active_constraints or {},
    }