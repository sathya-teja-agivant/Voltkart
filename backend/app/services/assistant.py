import json
import re
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import (
    Product,
    Policy,
    Conversation,
    Message,
    ConversationContext,
)
from app.services.groq_service import GroqService


NO_INFO = "I don't have that information available in the system."
DEFAULT_RESULT_LIMIT = 20
MAX_RESULT_LIMIT = 20

# This MVP catalog currently stores laptop specifications, but not colour.
UNSUPPORTED_CATALOG_ATTRIBUTES = {
    "colour": ("colour", "color", "coloue", "grey", "gray", "black", "silver", "white", "blue"),
    "screen_touch": ("touchscreen", "touch screen"),
    "graphics": ("gpu", "graphics card", "dedicated graphics"),
}


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
        "description": product.description,
    }


def json_safe(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _is_follow_up(query: str) -> bool:
    """Only inherit previous filters for clearly contextual follow-up messages."""
    q = query.lower().strip()
    follow_up_patterns = (
        r"\b(which|what) (of )?(these|those|them)\b",
        r"\b(among these|from these|out of these)\b",
        r"\b(the first|the second|the last|both of them)\b",
        r"\b(also show|sort these|rank these)\b",
        r"\b(which one|what about this|how about this)\b",
        r"\b(is it|are they|does it|do they)\b",
        r"\bmake (it|them) (cheaper|lighter)\b",
        r"\b(best battery|longest battery|cheapest|lightest)\b.*\b(these|them)\b",
    )
    return any(re.search(pattern, q) for pattern in follow_up_patterns)


def _extract_budget(q: str) -> int | None:
    patterns = (
        r"(?:under|below|less than|up to|upto|within|maximum|max(?:imum)?(?: budget)?(?: of)?)"
        r"\s*(?:₹|rs\.?\s*)?([\d,]+)",
        r"(?:₹|rs\.?\s*)([\d,]+)\s*(?:or less|and below|or below)",
    )
    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            return int(match.group(1).replace(",", ""))
    return None


def _extract_numeric_constraint(q: str, label: str):
    """Return (value, operator); bare RAM/storage values mean exact matching."""
    label_pattern = r"(?:gb\s*)?" + re.escape(label)
    patterns = (
        (rf"\b(?:at least|minimum|min\.?)\s*(\d+)\s*gb\s*{label}\b", "gte"),
        (rf"\b(\d+)\s*gb\s*\+\s*{label}\b", "gte"),
        (rf"\b(?:up to|maximum|max\.?)\s*(\d+)\s*gb\s*{label}\b", "lte"),
        (rf"\b(\d+)\s*gb\s*{label}\b", "eq"),
    )
    for pattern, operator in patterns:
        match = re.search(pattern, q)
        if match:
            return int(match.group(1)), operator
    return None, None


def _extract_brand(q: str) -> str | None:
    # Include common brands even when they are not present in the catalog. This
    # ensures an unsupported brand produces zero matches instead of all products.
    brands = (
        "hewlett packard", "hp", "dell", "lenovo", "asus", "acer", "apple",
        "msi", "samsung", "lg", "gigabyte", "razer", "microsoft", "vivo",
    )
    for brand in sorted(brands, key=len, reverse=True):
        if re.search(rf"\b{re.escape(brand)}\b", q):
            return "HP" if brand == "hewlett packard" else brand.title()
    return None


def _extract_processor(q: str) -> str | None:
    patterns = (
        r"\bintel\s+core\s+i[3579]\b",
        r"\bcore\s+i[3579]\b",
        r"\bi[3579]\b",
        r"\bintel\s+core\s+ultra\s+[3579]\b",
        r"\bcore\s+ultra\s+[3579]\b",
        r"\bryzen\s+[3579]\b",
        r"\bapple\s+m[1234]\b",
    )
    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            value = match.group(0)
            if value.startswith("i") and not value.startswith("intel"):
                value = "Intel Core " + value
            elif value.startswith("core "):
                value = "Intel " + value
            return value
    return None


def _extract_result_limit(q: str) -> int:
    patterns = (
        r"\b(?:top|best|cheapest|lightest|lowest|longest battery)\s*(\d+)\b",
        r"\b(\d+)\s+(?:cheapest|cheaper|best|top|lightest|lightweight)\b",
        r"\bshow\s+(\d+)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            return max(1, min(int(match.group(1)), MAX_RESULT_LIMIT))
    return DEFAULT_RESULT_LIMIT


def _is_mobile_query(q: str) -> bool:
    return bool(re.search(
        r"\b(mobile|mobiles|phone|phones|smartphone|smartphones|iphone)\b", q
    ))


def _extract_unsupported_attributes(q: str) -> list[str]:
    unsupported = []
    for attribute, terms in UNSUPPORTED_CATALOG_ATTRIBUTES.items():
        if any(term in q for term in terms):
            unsupported.append(attribute)
    return unsupported


def heuristic_intent(query: str, context: dict | None = None) -> dict:
    q = query.lower().strip()
    context = context or {}
    follow_up = _is_follow_up(q)

    if _is_mobile_query(q) and not re.search(r"\blaptop|notebook\b", q):
        intent = "unsupported"
        reason = "mobile_category"
    elif any(term in q for term in (
        "return policy", "refund", "warranty", "shipping policy",
        "delivery policy", "cancellation", "payment method", "emi", "policy",
    )):
        intent = "policy_query"
        reason = None
    elif re.search(r"\b(compare|comparison|versus|vs\.?|difference between)\b", q):
        intent = "product_comparison"
        reason = None
    elif re.search(r"^(hi|hello|hey|good morning|good afternoon|good evening)\b", q):
        intent = "greetings"
        reason = None
    elif (
        any(term in q for term in (
            "laptop", "laptops", "notebook", "notebooks", "recommend", "suggest",
            "cheapest", "lightest", "battery life", "processor", "ram", "storage",
            "gaming", "find ", "show me", "best value", "under ₹", "under rs",
            "under ", "in dell", "in hp", "in lenovo", "in asus", "in acer",
        ))
        or _extract_brand(q) is not None
        or follow_up and context.get("previous_recommendations")
    ):
        intent = "product_recommendation"
        reason = None
    else:
        intent = "unsupported"
        reason = None

    # Independent searches start clean. Only explicit contextual follow-ups
    # inherit the previous search's constraints and product IDs.
    filters = dict(context.get("active_constraints", {})) if follow_up else {}

    budget = _extract_budget(q)
    if budget is not None:
        filters["budget"] = budget

    ram, ram_operator = _extract_numeric_constraint(q, "ram")
    if ram is not None:
        filters["ram"] = ram
        filters["ram_operator"] = ram_operator

    # Accept "512GB storage", "512GB SSD", and "at least 512GB storage".
    storage_patterns = (
        (r"\b(?:at least|minimum|min\.?)\s*(\d+)\s*gb\s*(?:ssd|storage)\b", "gte"),
        (r"\b(\d+)\s*gb\s*\+\s*(?:ssd|storage)\b", "gte"),
        (r"\b(?:up to|maximum|max\.?)\s*(\d+)\s*gb\s*(?:ssd|storage)\b", "lte"),
        (r"\b(\d+)\s*gb\s*(?:ssd|storage)\b", "eq"),
    )
    for pattern, operator in storage_patterns:
        match = re.search(pattern, q)
        if match:
            filters["storage"] = int(match.group(1))
            filters["storage_operator"] = operator
            break

    brand = _extract_brand(q)
    if brand:
        filters["brand"] = brand

    processor = _extract_processor(q)
    if processor:
        filters["processor"] = processor

    if any(term in q for term in ("gaming", "gaming laptop", "for games", "play games")):
        filters["usage"] = "gaming"

    if any(term in q for term in ("lightest", "lightweight", "lighter", "lowest weight")):
        filters["sort_by"] = "weight"
    elif any(term in q for term in ("best battery", "battery life", "longest battery", "long battery")):
        filters["sort_by"] = "battery"
    elif any(term in q for term in ("cheapest", "lowest price", "least expensive", "cheaper")):
        filters["sort_by"] = "price"
    elif "sort by price" in q:
        filters["sort_by"] = "price"

    filters["result_limit"] = _extract_result_limit(q)
    filters["unsupported_attributes"] = _extract_unsupported_attributes(q)

    return {
        "intent": intent,
        "entities": {},
        "filters": filters,
        "is_follow_up": follow_up,
        "reason": reason,
    }


def detect_intent(groq: GroqService, query: str, context: dict) -> dict:
    """Keep catalog intent and filter extraction deterministic."""
    return heuristic_intent(query, context)


def merge_context(existing: dict, extracted: dict) -> dict:
    merged = dict(existing or {})
    merged.update(extracted or {})
    return merged


def retrieve_products(db: Session, filters: dict, limit: int = DEFAULT_RESULT_LIMIT) -> list[Product]:
    stmt = select(Product).where(Product.stock_status == "IN_STOCK")

    if filters.get("brand"):
        stmt = stmt.where(Product.brand.ilike(str(filters["brand"])))

    if filters.get("budget") is not None:
        stmt = stmt.where(Product.price <= Decimal(str(filters["budget"])))

    if filters.get("ram") is not None:
        ram = int(filters["ram"])
        operator = filters.get("ram_operator", "eq")
        if operator == "gte":
            stmt = stmt.where(Product.ram >= ram)
        elif operator == "lte":
            stmt = stmt.where(Product.ram <= ram)
        else:
            stmt = stmt.where(Product.ram == ram)

    if filters.get("storage") is not None:
        storage = int(filters["storage"])
        operator = filters.get("storage_operator", "eq")
        if operator == "gte":
            stmt = stmt.where(Product.storage >= storage)
        elif operator == "lte":
            stmt = stmt.where(Product.storage <= storage)
        else:
            stmt = stmt.where(Product.storage == storage)

    if filters.get("operating_system"):
        stmt = stmt.where(Product.operating_system.ilike(f"%{filters['operating_system']}%"))

    if filters.get("processor"):
        processor_term = str(filters["processor"]).strip()
        stmt = stmt.where(Product.processor.ilike(f"%{processor_term}%"))

    if filters.get("usage") == "gaming":
        gaming_terms = ("gaming", "game", "victus", "loq", "tuf")
        usage_conditions = []
        for term in gaming_terms:
            usage_conditions.extend((
                Product.product_name.ilike(f"%{term}%"),
                Product.description.ilike(f"%{term}%"),
            ))
        stmt = stmt.where(or_(*usage_conditions))

    products = list(db.scalars(stmt).all())

    sort_by = filters.get("sort_by", "price")
    if sort_by == "weight":
        products.sort(key=lambda p: (float(p.weight or 999), float(p.price), p.product_name.lower()))
    elif sort_by == "battery":
        products.sort(key=lambda p: (-float(p.battery_life or 0), float(p.price), p.product_name.lower()))
    else:
        products.sort(key=lambda p: (float(p.price), p.product_name.lower()))

    return products[:max(1, min(int(limit), MAX_RESULT_LIMIT))]


def retrieve_policy(db: Session, query: str) -> list[Policy]:
    terms = [
        token for token in re.findall(r"[a-zA-Z]{3,}", query.lower())
        if token not in {"what", "your", "about", "tell", "does", "have", "please"}
    ]
    stmt = select(Policy).where(Policy.is_active.is_(True))
    if terms:
        conditions = [
            or_(
                Policy.title.ilike(f"%{term}%"),
                Policy.category.ilike(f"%{term}%"),
                Policy.content.ilike(f"%{term}%"),
            )
            for term in terms[:6]
        ]
        stmt = stmt.where(or_(*conditions))
    return list(db.scalars(stmt.limit(5)).all())


def _find_named_products(db: Session, query: str) -> list[Product]:
    """Resolve explicit product names and preserve the order used by the user."""
    all_products = list(db.scalars(select(Product)).all())
    q = query.lower()
    matches = []
    for product in all_products:
        name = product.product_name.lower()
        position = q.find(name)
        if position >= 0:
            matches.append((position, product))
    matches.sort(key=lambda item: item[0])
    return [product for _, product in matches[:2]]


def _fallback_product_answer(products: list[Product]) -> str:
    if not products:
        return "I couldn't find in-stock laptops matching those requirements."
    lines = [
        f"- {p.product_name} ({p.brand}) — ₹{float(p.price):,.0f}, "
        f"{p.processor}, {p.ram}GB RAM, {p.storage}GB SSD, "
        f"{float(p.weight):.2f}kg, {float(p.battery_life):.1f} hours battery"
        for p in products
    ]
    return "Here are the matching laptops from our catalog:\n" + "\n".join(lines)


def _comparison_answer(products: list[Product]) -> str:
    if len(products) < 2:
        return (
            "I couldn't identify two products to compare. Please provide "
            "both laptop model names, or ask for recommendations first."
        )
    return "Comparison data:\n" + "\n".join(
        f"{p.product_name} ({p.brand}): ₹{float(p.price):,.0f}, "
        f"{p.processor}, {p.ram}GB RAM, {p.storage}GB SSD, "
        f"{float(p.weight):.2f}kg, {float(p.battery_life):.1f}h battery"
        for p in products
    )


def _unsupported_response(reason: str | None, unsupported_attributes: list[str]) -> str | None:
    if reason == "mobile_category":
        return (
            "VoltKart currently supports laptop recommendations only. "
            "I can't search for mobile phones in this catalog."
        )
    if unsupported_attributes:
        names = ", ".join(unsupported_attributes)
        return (
            f"I can't verify {names} because those specifications are not stored "
            "in the VoltKart catalog. Please search using the specifications "
            "available in the catalog, such as brand, budget, RAM or processor."
        )
    return None


def handle_chat(
    db: Session,
    groq: GroqService,
    conversation: Conversation,
    user_message: str,
) -> dict:
    context_row = conversation.context
    if context_row is None:
        context_row = ConversationContext(conversation_id=conversation.conversation_id)
        db.add(context_row)
        db.flush()

    prior_context = {
        "active_constraints": context_row.active_constraints or {},
        "previous_recommendations": context_row.previous_recommendations or [],
        "previous_comparisons": context_row.previous_comparisons or [],
    }

    detected = detect_intent(groq, user_message, prior_context)
    intent = detected["intent"]
    filters = dict(detected.get("filters") or {})

    if intent == "product_recommendation":
        result_limit = filters.pop("result_limit", DEFAULT_RESULT_LIMIT)
        unsupported_attributes = filters.pop("unsupported_attributes", [])
        reason = detected.get("reason")

        unsupported_answer = _unsupported_response(reason, unsupported_attributes)
        if unsupported_answer:
            answer = unsupported_answer
            products = []
        else:
            products = retrieve_products(db, filters, limit=result_limit)
            if not products:
                answer = (
                    "I couldn't find in-stock laptops matching all those constraints "
                    "in the catalog. I have not removed any of your requested filters. "
                    "Try relaxing one requirement."
                )
            else:
                answer = _fallback_product_answer(products)

        context_row.active_constraints = dict(filters)
        context_row.previous_recommendations = [
            str(product.product_id) for product in products
        ]
        context_row.previous_comparisons = []
        result_products = [_json_product(product) for product in products]
        message_type = "RECOMMENDATION"

    elif intent == "product_comparison":
        named_products = _find_named_products(db, user_message)

        if len(named_products) >= 2:
            products = named_products
        elif len(named_products) == 1:
            products = named_products
        else:
            previous_ids = prior_context["previous_recommendations"][:2]
            products = list(
                db.scalars(
                    select(Product).where(Product.product_id.in_(previous_ids))
                ).all()
            ) if previous_ids else []

        result_products = [_json_product(product) for product in products]
        answer = _comparison_answer(products)
        context_row.previous_comparisons = [
            str(product.product_id) for product in products
        ]
        message_type = "COMPARISON"

    elif intent == "policy_query":
        policies = retrieve_policy(db, user_message)
        if not policies:
            answer = NO_INFO
        else:
            policy_facts = [
                {"title": policy.title, "category": policy.category, "content": policy.content}
                for policy in policies
            ]
            try:
                answer = groq.answer(
                    "You are VoltKart customer support. Answer using only the "
                    "supplied policy records. Do not invent terms. If the records "
                    "do not answer the question, say exactly: " + NO_INFO,
                    json_safe({
                        "question": user_message,
                        "policy_records": policy_facts,
                    }),
                )
            except Exception:
                answer = "\n".join(
                    f"{policy['title']}: {policy['content']}"
                    for policy in policy_facts
                )
        result_products = []
        message_type = "POLICY_RESPONSE"

    elif intent == "greetings":
        answer = (
            "Hello! I'm VoltKart's laptop shopping assistant. I can help you "
            "find laptops, compare models, and answer questions about store policies."
        )
        result_products = []
        message_type = "TEXT"

    else:
        answer = (
            "I can help with laptop searches, recommendations, comparisons "
            "and VoltKart store policies. What would you like to know?"
        )
        result_products = []
        message_type = "TEXT"

    context_row.recent_searches = (context_row.recent_searches or [])[-9:] + [user_message]
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
    ))

    from datetime import datetime, timezone
    conversation.last_message_at = datetime.now(timezone.utc)
    if conversation.title == "New conversation":
        conversation.title = user_message[:60]

    db.commit()

    return {
        "conversation_id": str(conversation.conversation_id),
        "intent": intent,
        "answer": answer,
        "products": result_products,
        "active_constraints": context_row.active_constraints or {},
    }
