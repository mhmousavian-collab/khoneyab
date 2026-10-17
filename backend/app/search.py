import json
import re
import unicodedata
from difflib import SequenceMatcher
from collections import defaultdict
from typing import Iterable
from sqlalchemy.orm import Session
from .models import Advertisement
from .schemas import SearchCriteria
from .seed import CITY_DATA
from .ai import chat_json

DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
AMENITIES = {"parking": "پارکینگ", "elevator": "آسانسور", "storage": "انباری"}
RANKING_WEIGHTS = {"base": 50, "budget": 5, "bedrooms": 7, "area": 4, "amenity": 11, "emphasis": 3, "transit": 11, "missed_preference": -5}
NEIGHBORHOODS = {
    "تهران": ["سعادت آباد", "نارمک", "تهرانپارس", "پونک", "یوسف آباد", "اکباتان", "ستارخان", "شهرک غرب", "ونک", "جنت آباد"],
    "مشهد": ["احمدآباد", "قاسم آباد", "وکیل آباد", "الهیه", "سجاد", "طبرسی"],
    "اصفهان": ["مرداویج", "خانه اصفهان", "ملک شهر", "سپاهان شهر", "جلفا", "چهارباغ بالا"],
    "شیراز": ["معالی آباد", "قصرالدشت", "فرهنگ شهر", "عفیف آباد", "صدرا", "بلوار رحمت"],
    "کرج": ["گوهردشت", "جهانشهر", "عظیمیه", "مهرشهر", "گلشهر", "فردیس"],
    "تبریز": ["ائل گلی", "ولیعصر", "رشدیه", "آبرسان", "منظریه", "مرزداران"],
    "قم": ["سالاریه", "پردیسان", "زنبیل آباد", "بلوار امین", "نیروگاه"],
    "اهواز": ["کیانپارس", "گلستان", "زیتون کارمندی", "کوی ملت", "پادادشهر"],
    "رشت": ["گلسار", "منظریه", "حمیدیان", "معلم", "بلوار دیلمان"],
    "یزد": ["صفائیه", "آزادشهر", "کوی دانشگاه", "بلوار جمهوری", "محمودآباد"],
}
CITIES = {
    "تهران": ("تهران", ["تهران", "tehran"]),
    "مشهد": ("مشهد", ["مشهد", "mashhad"]),
    "اصفهان": ("اصفهان", ["اصفهان", "isfahan", "esfahan"]),
    "شیراز": ("شیراز", ["شیراز", "shiraz"]),
    "کرج": ("کرج", ["کرج", "karaj"]),
    "تبریز": ("تبریز", ["تبریز", "tabriz"]),
    "قم": ("قم", ["قم", "qom"]),
    "اهواز": ("اهواز", ["اهواز", "ahvaz"]),
    "رشت": ("رشت", ["رشت", "rasht"]),
    "یزد": ("یزد", ["یزد", "yazd"]),
}


def normalize_text(value: str) -> str:
    value = (value or "").translate(DIGIT_MAP).replace("ي", "ی").replace("ك", "ک").replace("ۀ", "ه")
    value = unicodedata.normalize("NFKC", value).lower().replace("\u200c", " ")
    value = value.replace("٬", ",").replace("،", ",").replace("٫", ".")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _scaled_number(raw: str, unit: str | None, currency: str | None = None) -> int:
    number = float(raw.replace(",", ""))
    unit = unit or ""
    if "میلیارد" in unit:
        number *= 1_000_000_000
    elif "میلیون" in unit:
        number *= 1_000_000
    elif "هزار" in unit:
        number *= 1_000
    # Rial is one tenth of a toman. Store every price internally in toman.
    if currency == "ریال":
        number /= 10
    return int(number)


def fallback_parse_query(query: str, current: SearchCriteria | None = None) -> SearchCriteria:
    text = normalize_text(query)
    data = current.model_dump() if current else {}
    data["emphasis"] = list(data.get("emphasis") or [])
    data["must_have_amenities"] = list(data.get("must_have_amenities") or [])
    data["preferred_amenities"] = list(data.get("preferred_amenities") or [])

    if any(word in text for word in ["اجاره", "رهن", "ودیعه", "rent"]):
        data["transaction_type"] = "rent"
        data["max_price_toman"] = None
    elif any(word in text for word in ["خرید", "فروش", "بخر", "sale", "خریداری"]):
        data["transaction_type"] = "sale"
        data["max_deposit_toman"] = None
        data["max_monthly_rent_toman"] = None

    for city, (_, aliases) in CITIES.items():
        if any(normalize_text(alias) in text for alias in aliases):
            data["city"] = city
            break
    if data.get("city"):
        for neighborhood in NEIGHBORHOODS.get(data["city"], []):
            if normalize_text(neighborhood) in text:
                canonical = next((candidate for candidate in CITY_DATA.get(data["city"], {}).get("neighborhoods", [])
                                  if normalize_text(candidate) == normalize_text(neighborhood)), neighborhood)
                data["neighborhood"] = canonical
                break

    if any(term in text for term in ["ویلا", "ویلایی", "villa"]):
        data["property_type"] = "villa"
    elif any(term in text for term in ["خانه", "حیاط دار", "حیاط‌دار", "house"]):
        data["property_type"] = "house"
    elif any(term in text for term in ["آپارتمان", "اپارتمان", "برج", "واحد", "apartment"]):
        data["property_type"] = "apartment"

    bedroom_match = re.search(r"(?<!\d)([0-9])\s*(?:خوابه|اتاق\s*خواب|خواب)", text)
    if bedroom_match:
        data["bedrooms"] = int(bedroom_match.group(1))
    else:
        number_words = {"یک": 1, "یه": 1, "یک": 1, "دو": 2, "سه": 3, "چهار": 4, "پنج": 5}
        word_match = re.search(r"\b(یک|یه|دو|سه|چهار|پنج)\s*(?:خوابه|اتاق\s*خواب|خواب)", text)
        if word_match:
            data["bedrooms"] = number_words[word_match.group(1)]

    area_between = re.search(r"([0-9][0-9,.]*)\s*(?:تا|الی|-)\s*([0-9][0-9,.]*)\s*(?:متر|متری|متر مربع)", text)
    if area_between:
        data["min_area_sqm"] = float(area_between.group(1).replace(",", ""))
        data["max_area_sqm"] = float(area_between.group(2).replace(",", ""))
    else:
        min_area = re.search(r"(?:حداقل|بیشتر از|بالای)\s*([0-9][0-9,.]*)\s*(?:متر|متری)", text)
        max_area = re.search(r"(?:حداکثر|حداکثر تا|زیر|کمتر از|تا)\s*([0-9][0-9,.]*)\s*(?:متر|متری)", text)
        if min_area:
            data["min_area_sqm"] = float(min_area.group(1).replace(",", ""))
        if max_area:
            data["max_area_sqm"] = float(max_area.group(1).replace(",", ""))

    amount_pattern = re.compile(r"(?:تا|حداکثر|زیر|کمتر از|بودجه(?:\s*ی)?\s*حدود|حدود)?\s*([0-9][0-9,.]*)\s*(میلیارد|میلیون|هزار)?\s*(تومان|تومن|ریال)?")
    amounts = []
    for m in amount_pattern.finditer(text):
        raw, unit, currency = m.group(1), m.group(2), m.group(3)
        end = m.end()
        context = text[max(0, m.start()-18):min(len(text), end+26)]
        # Ignore common room counts and area quantities accidentally matching as money.
        if re.search(r"(?:^|\s)متر(?:\s|$)", context) or "خواب" in context:
            continue
        if unit or currency or any(token in context for token in ["بودجه", "قیمت", "ودیعه", "اجاره", "میلیون", "میلیارد"]):
            amounts.append((_scaled_number(raw, unit, currency), context))

    is_rent = data.get("transaction_type") == "rent" or any(x in text for x in ["اجاره", "رهن", "ودیعه", "پیش پرداخت", "پیشپرداخت"] )
    if is_rent:
        # Parse independently labelled deposit and monthly-rent amounts when both are supplied.
        deposit_pattern = re.compile(r"(?:ودیعه|رهن|پیش(?:\s*پرداخت)?)\s*(?:(?:تا|حداکثر|حدود)\s*)?([0-9][0-9,.]*)\s*(میلیارد|میلیون|هزار)?\s*(تومان|تومن|ریال)?")
        monthly_pattern = re.compile(r"(?:اجاره(?:\s*ی)?(?:\s*ماهانه)?|ماهانه)\s*(?:(?:تا|حداکثر|حدود)\s*)?([0-9][0-9,.]*)\s*(میلیارد|میلیون|هزار)?\s*(تومان|تومن|ریال)?")
        deposit_match = deposit_pattern.search(text)
        monthly_match = monthly_pattern.search(text)
        if deposit_match:
            data["max_deposit_toman"] = _scaled_number(deposit_match.group(1), deposit_match.group(2), deposit_match.group(3))
        if monthly_match:
            data["max_monthly_rent_toman"] = _scaled_number(monthly_match.group(1), monthly_match.group(2), monthly_match.group(3))
        if not deposit_match and not monthly_match and amounts:
            amount, ctx = amounts[-1]
            if "اجاره" in ctx or "ماهانه" in ctx:
                data["max_monthly_rent_toman"] = amount
            else:
                data["max_deposit_toman"] = amount
    elif amounts:
        amount, _ctx = amounts[-1]
        data["transaction_type"] = data.get("transaction_type") or "sale"
        data["max_price_toman"] = amount

    hard_marker = any(w in text for w in ["حتما", "حتماً", "باید", "الزامی", "اجباری", "فقط", "ضروری"])
    for key, words in {
        "parking": ["پارکینگ"],
        "elevator": ["آسانسور"],
        "storage": ["انباری"],
    }.items():
        if any(word in text for word in words):
            dest = "must_have_amenities" if hard_marker else "preferred_amenities"
            if key not in data[dest]:
                data[dest].append(key)
            other = "preferred_amenities" if dest == "must_have_amenities" else "must_have_amenities"
            data[other] = [x for x in data[other] if x != key]
            data["emphasis"].append(key)

    explicit_transit = re.search(r"(?:حداکثر|تا|کمتر از)\s*([0-9]+)\s*دقیقه.{0,18}(?:مترو|مترو|حمل.?ونقل)", text)
    if explicit_transit:
        data["transit_max_minutes"] = int(explicit_transit.group(1))
    elif any(w in text for w in ["مترو", "حمل و نقل عمومی", "ایستگاه"]):
        data["transit_preference_minutes"] = 10
        data["emphasis"].append("transit")

    # Avoid duplicate emphasis items while keeping order.
    data["emphasis"] = list(dict.fromkeys(data["emphasis"]))
    return SearchCriteria.model_validate(data)


def _query_needs_ai(query: str, criteria: SearchCriteria) -> bool:
    text = normalize_text(query)
    complex_markers = [
        "بهترین گزینه", "بهترین انتخاب", "مناسب خانواده", "برای خانواده", "خوش قیمت", "ارزش خرید",
        "رفت و آمد", "محله آرام", "نورگیر", "ترجیح می دهم", "ترجیح میدم", "ترجیحا", "ترجیحاً",
        "با این حال", "اما", "ولی", "در عوض", "بین این دو", "تا حد ممکن", "پیشنهاد بده", "از نظر",
        "که هم", "در حالی که", "اگر", "اگه", "یه جور",
    ]
    if any(normalize_text(marker) in text for marker in complex_markers):
        return True
    recognized = sum([
        bool(criteria.transaction_type), bool(criteria.city), bool(criteria.neighborhood), bool(criteria.property_type),
        criteria.max_price_toman is not None or criteria.max_deposit_toman is not None or criteria.max_monthly_rent_toman is not None,
        criteria.bedrooms is not None, criteria.min_area_sqm is not None or criteria.max_area_sqm is not None,
        bool(criteria.must_have_amenities or criteria.preferred_amenities), criteria.transit_max_minutes is not None or criteria.transit_preference_minutes is not None,
    ])
    # Two or more recognized criteria make the query straightforward enough for deterministic parsing.
    return recognized < 2


def interpret_query(query: str, current: SearchCriteria | None = None) -> tuple[SearchCriteria, str]:
    base = fallback_parse_query(query, current)
    if not _query_needs_ai(query, base):
        return base, "rules"
    payload = {
        "query": query,
        "existing_criteria": current.model_dump() if current else None,
        "rule_based_parse": base.model_dump(),
    }
    system = (
        "You extract residential property search criteria for Iran. Return ONLY one JSON object with fields: "
        "transaction_type (sale|rent|null), city, neighborhood, property_type (apartment|house|villa|null), "
        "max_price_toman, max_deposit_toman, max_monthly_rent_toman, min_area_sqm, max_area_sqm, bedrooms, "
        "must_have_amenities (parking|elevator|storage array), preferred_amenities (same enum array), "
        "transit_max_minutes, transit_preference_minutes, emphasis (string array). "
        "Explicit numeric limits are hard constraints. Ordinary amenity/metro mentions are preferences unless clearly mandatory. "
        "Use the rule_based_parse values as a starting point and preserve all plausible constraints. Currency is toman."
    )
    ai_result = chat_json("cheap", system, json.dumps(payload, ensure_ascii=False))
    if isinstance(ai_result, dict):
        try:
            merged = {**base.model_dump(), **ai_result}
            # Preserve inferred fields when the model omits or nulls them.
            for key, value in base.model_dump().items():
                if key not in ai_result or (ai_result.get(key) is None and value is not None):
                    merged[key] = value
            return SearchCriteria.model_validate(merged), "ai"
        except Exception:
            pass
    return base, "rules"


def refine_query(message: str, current: SearchCriteria) -> tuple[SearchCriteria, str]:
    data = {"message": message, "current_criteria": current.model_dump()}
    system = (
        "Update the current Iranian residential property search criteria based on the user's follow-up. Return only a JSON object "
        "with the same SearchCriteria fields. Preserve existing constraints unless the message clearly changes/removes them. "
        "The app performs final filtering and ranking. Amounts are toman."
    )
    answer = chat_json("standard", system, json.dumps(data, ensure_ascii=False))
    if isinstance(answer, dict):
        try:
            merged = {**current.model_dump(), **answer}
            return SearchCriteria.model_validate(merged), "ai"
        except Exception:
            pass
    # Useful, predictable no-LLM fallback: interpret follow-ups as additions, overrides, or removals.
    text = normalize_text(message)
    result = fallback_parse_query(message, current)
    removal_markers = ["بدون", "لازم نیست", "نیازی به", "اهمیتی ندارد", "مهم نیست", "حذف کن"]
    if any(marker in text for marker in removal_markers):
        for amenity, label in AMENITIES.items():
            if label in text:
                result.must_have_amenities = [a for a in result.must_have_amenities if a != amenity]
                result.preferred_amenities = [a for a in result.preferred_amenities if a != amenity]
        if any(word in text for word in ["مترو", "حمل و نقل", "ایستگاه"]):
            result.transit_preference_minutes = None
            result.transit_max_minutes = None
    if any(word in text for word in ["بودجه مهم نیست", "بدون محدودیت بودجه", "محدودیت قیمت را بردار"]):
        result.max_price_toman = None
        result.max_deposit_toman = None
        result.max_monthly_rent_toman = None
    return result, "rules"


def comparison_summary(properties: list[dict], user_goal: str | None = None) -> tuple[str | None, str]:
    prompt = {"properties": properties, "user_goal": user_goal or "Find the best overall fit."}
    system = (
        "Compare the provided synthetic property records. Return JSON with one string field 'summary'. "
        "Use only the supplied facts, identify trade-offs, and do not claim a property is objectively best without context. "
        "Do not invent facts or market claims. Write in Persian."
    )
    result = chat_json("premium", system, json.dumps(prompt, ensure_ascii=False), timeout=28.0)
    if isinstance(result, dict) and isinstance(result.get("summary"), str):
        return result["summary"][:3000], "ai"
    return None, "unavailable"


def _price_value(ad: Advertisement) -> int:
    if ad.transaction_type == "sale":
        return ad.sale_price_toman or 0
    # One consistent numeric value for generic sorting; detailed rent numbers remain visible.
    return (ad.deposit_toman or 0) + 12 * (ad.monthly_rent_toman or 0)


def _matches_hard(ad: Advertisement, c: SearchCriteria) -> list[str]:
    failed: list[str] = []
    if c.transaction_type and ad.transaction_type != c.transaction_type:
        failed.append("نوع معامله")
    if c.city and ad.city != c.city:
        failed.append("شهر")
    if c.neighborhood and normalize_text(ad.neighborhood) != normalize_text(c.neighborhood):
        failed.append("محله")
    if c.property_type and ad.property_type != c.property_type:
        failed.append("نوع ملک")
    if c.transaction_type == "sale" and c.max_price_toman is not None and (ad.sale_price_toman or 0) > c.max_price_toman:
        failed.append("بودجه خرید")
    if c.transaction_type == "rent" and c.max_deposit_toman is not None and (ad.deposit_toman or 0) > c.max_deposit_toman:
        failed.append("حداکثر ودیعه")
    if c.transaction_type == "rent" and c.max_monthly_rent_toman is not None and (ad.monthly_rent_toman or 0) > c.max_monthly_rent_toman:
        failed.append("حداکثر اجاره ماهانه")
    if c.min_area_sqm is not None and ad.area_sqm < c.min_area_sqm:
        failed.append("حداقل متراژ")
    if c.max_area_sqm is not None and ad.area_sqm > c.max_area_sqm:
        failed.append("حداکثر متراژ")
    if c.bedrooms is not None and ad.bedrooms != c.bedrooms:
        failed.append("تعداد اتاق خواب")
    for amenity in c.must_have_amenities:
        if not bool(getattr(ad, amenity, False)):
            failed.append(AMENITIES[amenity])
    if c.transit_max_minutes is not None and (ad.transit_walk_minutes is None or ad.transit_walk_minutes > c.transit_max_minutes):
        failed.append("فاصله تا حمل‌ونقل عمومی")
    return failed


def _score(ad: Advertisement, c: SearchCriteria) -> tuple[int, list[str], list[str]]:
    score = RANKING_WEIGHTS["base"]
    reasons: list[str] = []
    unmet: list[str] = []
    if c.transaction_type == "sale" and c.max_price_toman is not None:
        reasons.append("در محدوده بودجه خرید")
        score += RANKING_WEIGHTS["budget"]
    if c.transaction_type == "rent" and (c.max_deposit_toman is not None or c.max_monthly_rent_toman is not None):
        reasons.append("در محدوده بودجه اجاره")
        score += RANKING_WEIGHTS["budget"]
    if c.city:
        reasons.append(f"در شهر {ad.city}")
    if c.bedrooms is not None:
        reasons.append(f"{ad.bedrooms} اتاق خواب مطابق درخواست")
        score += RANKING_WEIGHTS["bedrooms"]
    if c.min_area_sqm is not None or c.max_area_sqm is not None:
        reasons.append(f"متراژ {int(ad.area_sqm)} متر مطابق محدوده")
        score += RANKING_WEIGHTS["area"]

    emphasis = set(c.emphasis)
    pref_amenities = list(dict.fromkeys(c.preferred_amenities))
    for amenity in pref_amenities:
        weight = RANKING_WEIGHTS["amenity"] + (RANKING_WEIGHTS["emphasis"] if amenity in emphasis else 0)
        label = AMENITIES[amenity]
        if bool(getattr(ad, amenity, False)):
            score += weight
            reasons.append(f"{label} دارد")
        else:
            score += RANKING_WEIGHTS["missed_preference"]
            unmet.append(f"{label} ندارد")
    if c.transit_preference_minutes is not None:
        target = c.transit_preference_minutes
        if ad.transit_walk_minutes is not None and ad.transit_walk_minutes <= target:
            score += RANKING_WEIGHTS["transit"] + (RANKING_WEIGHTS["emphasis"] if "transit" in emphasis else 0)
            reasons.append(f"حدود {ad.transit_walk_minutes} دقیقه تا {ad.transit_mode or 'حمل‌ونقل عمومی'}")
        else:
            score += RANKING_WEIGHTS["missed_preference"]
            if ad.transit_walk_minutes is None:
                unmet.append("فاصله‌ی حمل‌ونقل عمومی مشخص نیست")
            else:
                unmet.append(f"فاصله تا حمل‌ونقل عمومی {ad.transit_walk_minutes} دقیقه است")
    for amenity in c.must_have_amenities:
        label = AMENITIES[amenity]
        if bool(getattr(ad, amenity, False)):
            reasons.append(f"{label} دارد")
    if c.transit_max_minutes is not None:
        reasons.append(f"حدود {ad.transit_walk_minutes} دقیقه تا حمل‌ونقل عمومی")

    score = max(0, min(100, score))
    return score, list(dict.fromkeys(reasons)), list(dict.fromkeys(unmet))


def _serialize_ad(ad: Advertisement) -> dict:
    return {
        "id": ad.id,
        "group_key": ad.group_key,
        "transaction_type": ad.transaction_type,
        "property_type": ad.property_type,
        "city": ad.city,
        "neighborhood": ad.neighborhood,
        "latitude": ad.latitude,
        "longitude": ad.longitude,
        "area_sqm": ad.area_sqm,
        "bedrooms": ad.bedrooms,
        "sale_price_toman": ad.sale_price_toman,
        "deposit_toman": ad.deposit_toman,
        "monthly_rent_toman": ad.monthly_rent_toman,
        "price_per_sqm_toman": int((ad.sale_price_toman or 0) / ad.area_sqm) if ad.transaction_type == "sale" and ad.area_sqm else None,
        "floor_number": ad.floor_number,
        "total_floors": ad.total_floors,
        "building_age_years": ad.building_age_years,
        "parking": ad.parking,
        "elevator": ad.elevator,
        "storage": ad.storage,
        "transit_mode": ad.transit_mode,
        "transit_station": ad.transit_station,
        "transit_distance_m": ad.transit_distance_m,
        "transit_walk_minutes": ad.transit_walk_minutes,
        "neighborhood_info": ad.neighborhood_info,
        "description": ad.description,
        "images": json.loads(ad.images_json or "[]"),
        "listing_date": ad.listing_date,
        "source_name": ad.source_name,
        "source_url": ad.source_url,
        "title": ad.title,
        "synthetic": True,
    }


def serialize_group(group_ads: list[Advertisement], c: SearchCriteria, representative: Advertisement | None = None) -> dict:
    primary = group_ads[0]
    ad = representative or primary
    score, reasons, unmet = _score(ad, c)
    item = _serialize_ad(ad)
    item.update({
        "property_id": primary.group_key,
        "group_key": primary.group_key,
        "advertisement_count": len(group_ads),
        "match_score": score,
        "match_reasons": reasons,
        "unmet_preferences": unmet,
        "sources": [{"id": source.id, "source_name": source.source_name, "title": source.title, "source_url": source.source_url} for source in group_ads],
    })
    return item


def _similar_text(a: str | None, b: str | None) -> float:
    left, right = normalize_text(a or ""), normalize_text(b or "")
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _looks_like_duplicate(a: Advertisement, b: Advertisement) -> bool:
    """Conservative field-and-text deduplication for ads without a shared source group key."""
    if a.transaction_type != b.transaction_type or normalize_text(a.city) != normalize_text(b.city) or normalize_text(a.neighborhood) != normalize_text(b.neighborhood):
        return False
    if a.property_type != b.property_type or a.bedrooms != b.bedrooms:
        return False
    if abs(a.area_sqm - b.area_sqm) > 2.0:
        return False
    if a.floor_number is not None and b.floor_number is not None and a.floor_number != b.floor_number:
        return False
    if a.building_age_years is not None and b.building_age_years is not None and abs(a.building_age_years - b.building_age_years) > 2:
        return False
    # Approximate coordinates must be unusually close to reduce accidental merging of similar homes.
    if abs(a.latitude - b.latitude) > 0.002 or abs(a.longitude - b.longitude) > 0.002:
        return False
    # Similar unit details and at least one comparable price are a further guard against false positives.
    if a.transaction_type == "sale":
        pa, pb = a.sale_price_toman or 0, b.sale_price_toman or 0
        if not pa or not pb or abs(pa - pb) / max(pa, pb) > 0.07:
            return False
    else:
        da, db = a.deposit_toman or 0, b.deposit_toman or 0
        ra, rb = a.monthly_rent_toman or 0, b.monthly_rent_toman or 0
        if da and db and abs(da - db) / max(da, db) > 0.12:
            return False
        if ra and rb and abs(ra - rb) / max(ra, rb) > 0.15:
            return False
    return _similar_text(a.title, b.title) >= 0.52 or _similar_text(a.description, b.description) >= 0.72


def group_ads(ads: Iterable[Advertisement]) -> list[list[Advertisement]]:
    """Group explicit duplicate keys and cautiously infer duplicates from stored listing fields."""
    rows = sorted(ads, key=lambda a: a.id)
    parent = list(range(len(rows)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[max(rx, ry)] = min(rx, ry)

    by_key: dict[str, int] = {}
    for i, ad in enumerate(rows):
        if ad.group_key in by_key:
            union(i, by_key[ad.group_key])
        else:
            by_key[ad.group_key] = i

    # Catalog is small in the MVP; the pairwise pass keeps the implementation dependency-free.
    for i, ad in enumerate(rows):
        for j in range(i + 1, len(rows)):
            other = rows[j]
            if ad.group_key != other.group_key and _looks_like_duplicate(ad, other):
                union(i, j)

    groups: dict[int, list[Advertisement]] = defaultdict(list)
    for i, ad in enumerate(rows):
        groups[find(i)].append(ad)
    return sorted(groups.values(), key=lambda group: group[0].id)


def search_properties(db: Session, criteria: SearchCriteria, sort_by: str = "relevance", limit: int = 80) -> dict:
    all_ads = db.query(Advertisement).order_by(Advertisement.id.asc()).all()
    groups = group_ads(all_ads)
    exact: list[dict] = []
    relaxable_near: list[tuple[int, dict, list[str]]] = []
    for group in groups:
        per_ad = [(ad, _matches_hard(ad, criteria)) for ad in group]
        exact_ad = next((ad for ad, failed in per_ad if not failed), None)
        if exact_ad is not None:
            exact.append(serialize_group(group, criteria, exact_ad))
            continue
        # Transaction, city and neighborhood are foundational scope and are never relaxed.
        scoped = [ad for ad, _failed in per_ad
                  if (not criteria.transaction_type or ad.transaction_type == criteria.transaction_type)
                  and (not criteria.city or normalize_text(ad.city) == normalize_text(criteria.city))
                  and (not criteria.neighborhood or normalize_text(ad.neighborhood) == normalize_text(criteria.neighborhood))]
        if not scoped:
            continue
        near_ad = min(scoped, key=lambda ad: (len(_matches_hard(ad, criteria)), -_score(ad, criteria)[0]))
        failed = _matches_hard(near_ad, criteria)
        # Only offer near matches that fail at least one refinable constraint.
        if failed:
            relaxable_near.append((len(failed), serialize_group(group, criteria, near_ad), failed))

    def price_for(item: dict) -> int:
        if item["transaction_type"] == "sale":
            return item["sale_price_toman"] or 0
        return (item["deposit_toman"] or 0) + 12 * (item["monthly_rent_toman"] or 0)

    if sort_by == "price_asc":
        exact.sort(key=price_for)
    elif sort_by == "price_desc":
        exact.sort(key=price_for, reverse=True)
    elif sort_by == "area_asc":
        exact.sort(key=lambda p: p["area_sqm"])
    elif sort_by == "area_desc":
        exact.sort(key=lambda p: p["area_sqm"], reverse=True)
    else:
        exact.sort(key=lambda p: (p["match_score"], -price_for(p)), reverse=True)

    relaxable_near.sort(key=lambda pair: (pair[0], -pair[1]["match_score"]))
    near_results = []
    for _, item, failed in relaxable_near[:12]:
        item["failed_constraints"] = list(dict.fromkeys(failed))
        near_results.append(item)

    return {
        "results": exact[:limit],
        "total": len(exact),
        "near_matches": near_results if not exact else [],
        "near_matches_total": len(relaxable_near) if not exact else 0,
        "criteria": criteria.model_dump(),
        "sort_by": sort_by,
        "synthetic": True,
    }


def get_group_detail(db: Session, property_id: str, criteria: SearchCriteria | None = None) -> dict | None:
    all_ads = db.query(Advertisement).order_by(Advertisement.id.asc()).all()
    groups = group_ads(all_ads)
    target_id = None
    try:
        target_id = int(property_id)
    except (ValueError, TypeError):
        pass
    ads = next((group for group in groups if any(a.group_key == property_id for a in group)
                or (target_id is not None and any(a.id == target_id for a in group))), [])
    if not ads:
        return None
    c = criteria or SearchCriteria(transaction_type=ads[0].transaction_type)
    exact_ad = next((ad for ad in ads if not _matches_hard(ad, c)), None)
    representative = exact_ad or min(ads, key=lambda ad: (len(_matches_hard(ad, c)), -_score(ad, c)[0]))
    result = serialize_group(ads, c, representative)
    result["sources"] = [{"id": a.id, "source_name": a.source_name, "title": a.title, "source_url": a.source_url,
                          "sale_price_toman": a.sale_price_toman, "deposit_toman": a.deposit_toman,
                          "monthly_rent_toman": a.monthly_rent_toman} for a in ads]
    return result
