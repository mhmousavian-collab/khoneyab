import json
import random
from datetime import date
from sqlalchemy.orm import Session
from .models import Advertisement

CITY_DATA = {
    "تهران": {"center": (35.7219, 51.3347), "neighborhoods": ["سعادت‌آباد", "نارمک", "تهرانپارس", "پونک", "یوسف‌آباد", "اکباتان", "ستارخان", "شهرک غرب", "ونک", "جنت‌آباد"], "stations": ["مترو صادقیه", "مترو ونک", "مترو میدان صنعت", "مترو نوبنیاد", "مترو تهرانپارس"]},
    "مشهد": {"center": (36.2972, 59.6067), "neighborhoods": ["احمدآباد", "قاسم‌آباد", "وکیل‌آباد", "الهیه", "سجاد", "طبرسی"], "stations": ["ایستگاه مترو شریعتی", "ایستگاه مترو وکیل‌آباد", "ایستگاه مترو کوهسنگی"]},
    "اصفهان": {"center": (32.6546, 51.6680), "neighborhoods": ["مرداویج", "خانه اصفهان", "ملک‌شهر", "سپاهان‌شهر", "جلفا", "چهارباغ بالا"], "stations": ["ایستگاه مترو آزادی", "ایستگاه مترو امام حسین", "ایستگاه مترو صفه"]},
    "شیراز": {"center": (29.5918, 52.5837), "neighborhoods": ["معالی‌آباد", "قصرالدشت", "فرهنگ‌شهر", "عفیف‌آباد", "صدرا", "بلوار رحمت"], "stations": ["ایستگاه مترو احسان", "ایستگاه مترو نمازی", "ایستگاه مترو زندیه"]},
    "کرج": {"center": (35.8327, 50.9915), "neighborhoods": ["گوهردشت", "جهانشهر", "عظیمیه", "مهرشهر", "گلشهر", "فردیس"], "stations": ["ایستگاه مترو گلشهر", "ایستگاه مترو کرج", "ایستگاه مترو شهید سلطانی"]},
    "تبریز": {"center": (38.0962, 46.2738), "neighborhoods": ["ائل‌گلی", "ولیعصر", "رشدیه", "آبرسان", "منظریه", "مرزداران"], "stations": ["ایستگاه مترو آبرسان", "ایستگاه مترو ائل‌گلی", "ایستگاه مترو میدان ساعت"]},
    "قم": {"center": (34.6416, 50.8746), "neighborhoods": ["سالاریه", "پردیسان", "زنبیل‌آباد", "بلوار امین", "نیروگاه"], "stations": ["ایستگاه اتوبوس مرکزی", "پایانه مسافربری", "ایستگاه BRT میدان مطهری"]},
    "اهواز": {"center": (31.3183, 48.6706), "neighborhoods": ["کیانپارس", "گلستان", "زیتون کارمندی", "کوی ملت", "پادادشهر"], "stations": ["ایستگاه اتوبوس کیانپارس", "پایانه تندگویان", "ایستگاه BRT نادری"]},
    "رشت": {"center": (37.2808, 49.5832), "neighborhoods": ["گلسار", "منظریه", "حمیدیان", "معلم", "بلوار دیلمان"], "stations": ["ایستگاه اتوبوس گلسار", "میدان شهرداری", "پایانه مرکزی"]},
    "یزد": {"center": (31.8974, 54.3569), "neighborhoods": ["صفائیه", "آزادشهر", "کوی دانشگاه", "بلوار جمهوری", "محمودآباد"], "stations": ["ایستگاه اتوبوس صفائیه", "پایانه غدیر", "میدان آزادی"]},
}

SYNTHETIC_SOURCES = ["نمونه‌فایل املاک الف", "آگهی‌نما (داده‌ی آزمایشی)", "خانه‌داده‌ی نمایشی", "آگهی‌بان آزمایشی", "نمونه‌منبع املاک"]
NEIGHBORHOOD_INFO = [
    "دسترسی روزمره به فروشگاه‌ها و خدمات محلی؛ توضیح نمایشی.",
    "بافت عمدتاً مسکونی با دسترسی به خیابان‌های اصلی؛ داده‌ی نمونه.",
    "ترکیبی از واحدهای آپارتمانی و خدمات محلی؛ اطلاعات محله تقریبی است.",
    "دسترسی مناسب به خریدهای روزانه و حمل‌ونقل اطراف؛ توضیح ساختگی برای دمو.",
]
DESCRIPTIONS = [
    "واحد خوش‌نقشه با نورگیری مناسب و دسترسی به امکانات روزمره.",
    "فروش فوری، بازدید با هماهنگی؛ اطلاعات این آگهی ساختگی است.",
    "ساختمان کم‌واحد در محدوده‌ای مسکونی با دسترسی محلی.",
    "واحد بازسازی‌شده با آشپزخانه‌ی کاربردی و فضای نشیمن روشن.",
    "مناسب سکونت خانوادگی؛ جزئیات برای نمایش قابلیت جست‌وجو تولید شده‌اند.",
    "دسترسی به ایستگاه حمل‌ونقل عمومی و فروشگاه‌های اطراف.",
]


def _make_record(i: int, rng: random.Random) -> dict:
    city = rng.choice(list(CITY_DATA.keys()))
    data = CITY_DATA[city]
    tx = "sale" if rng.random() < 0.68 else "rent"
    ptype = rng.choices(["apartment", "house", "villa"], [0.73, 0.17, 0.10])[0]
    area = rng.choice([55, 62, 68, 72, 78, 82, 85, 90, 94, 98, 105, 112, 125, 145, 170, 210])
    bedrooms = 0 if area < 48 else rng.choices([1, 2, 3, 4], [0.18, 0.44, 0.30, 0.08])[0]
    age = rng.randint(0, 24)
    floor = rng.randint(1, 9) if ptype == "apartment" else None
    floors = rng.randint(max(1, floor or 1), 12) if ptype == "apartment" else None
    parking = rng.random() < (0.76 if area >= 80 else 0.52)
    elevator = (ptype == "apartment" and floors is not None and floors >= 4 and rng.random() < 0.8) or rng.random() < 0.28
    storage = rng.random() < 0.65
    walk = rng.choice([3, 5, 7, 9, 12, 15, 18, 22, 28])
    distance = walk * rng.randint(60, 85)
    lat0, lon0 = data["center"]
    lat = lat0 + rng.uniform(-0.075, 0.075)
    lon = lon0 + rng.uniform(-0.085, 0.085)
    if tx == "sale":
        city_factor = {"تهران": 1.0, "کرج": .52, "مشهد": .57, "اصفهان": .62, "شیراز": .62, "تبریز": .48, "قم": .42, "اهواز": .38, "رشت": .45, "یزد": .39}[city]
        ppsqm = int(rng.randint(58, 145) * 1_000_000 * city_factor)
        sale_price = int(area * ppsqm / 10_000_000) * 10_000_000
        deposit = monthly = None
    else:
        sale_price = None
        city_factor = {"تهران": 1.0, "کرج": .58, "مشهد": .62, "اصفهان": .64, "شیراز": .63, "تبریز": .48, "قم": .45, "اهواز": .40, "رشت": .45, "یزد": .40}[city]
        deposit = int(rng.randint(250, 1100) * 1_000_000 * city_factor * max(.6, area / 90))
        monthly = int(rng.randint(5, 28) * 1_000_000 * city_factor * max(.65, area / 90))
    source = rng.choice(SYNTHETIC_SOURCES)
    title_type = {"apartment": "آپارتمان", "house": "خانه", "villa": "ویلا"}[ptype]
    tx_label = "فروش" if tx == "sale" else "رهن و اجاره"
    title = f"{tx_label} {title_type} {bedrooms} خوابه، {area} متر در {data['neighborhoods'][i % len(data['neighborhoods'])]}"
    neighborhood = data["neighborhoods"][i % len(data["neighborhoods"])]
    return {
        "group_key": f"demo-{i:04d}", "transaction_type": tx, "property_type": ptype,
        "city": city, "neighborhood": neighborhood, "latitude": round(lat, 5), "longitude": round(lon, 5),
        "area_sqm": float(area), "bedrooms": bedrooms, "sale_price_toman": sale_price,
        "deposit_toman": deposit, "monthly_rent_toman": monthly, "floor_number": floor,
        "total_floors": floors, "building_age_years": age, "parking": parking,
        "elevator": elevator, "storage": storage, "transit_mode": "مترو" if city in ["تهران", "مشهد", "اصفهان", "شیراز", "کرج", "تبریز"] else "اتوبوس",
        "transit_station": rng.choice(data["stations"]), "transit_distance_m": distance,
        "transit_walk_minutes": walk, "neighborhood_info": rng.choice(NEIGHBORHOOD_INFO),
        "description": rng.choice(DESCRIPTIONS),
        "images_json": json.dumps([f"/property-{1 + (i % 3)}.svg"], ensure_ascii=False),
        "listing_date": f"2026-{rng.randint(7, 10):02d}-{rng.randint(1, 27):02d}",
        "source_name": source, "source_url": None, "title": title,
    }


def _curated_record(i: int, city: str, neighborhood: str, area: int, bedrooms: int, price_b: float,
                    parking: bool, elevator: bool, storage: bool, walk: int, age: int = 6,
                    ptype: str = "apartment", tx: str = "sale", deposit_m: int = 800, rent_m: int = 20) -> dict:
    data = CITY_DATA[city]
    lat0, lon0 = data["center"]
    lat_offset = ((i % 7) - 3) * 0.004
    lon_offset = ((i % 9) - 4) * 0.005
    title_type = {"apartment": "آپارتمان", "house": "خانه", "villa": "ویلا"}[ptype]
    tx_label = "فروش" if tx == "sale" else "رهن و اجاره"
    sale_price = int(price_b * 1_000_000_000) if tx == "sale" else None
    deposit = deposit_m * 1_000_000 if tx == "rent" else None
    monthly = rent_m * 1_000_000 if tx == "rent" else None
    return {
        "group_key": f"demo-{i:04d}", "transaction_type": tx, "property_type": ptype,
        "city": city, "neighborhood": neighborhood, "latitude": round(lat0 + lat_offset, 5), "longitude": round(lon0 + lon_offset, 5),
        "area_sqm": float(area), "bedrooms": bedrooms, "sale_price_toman": sale_price,
        "deposit_toman": deposit, "monthly_rent_toman": monthly,
        "floor_number": (i % 7) + 1 if ptype == "apartment" else None,
        "total_floors": 8 if ptype == "apartment" else None, "building_age_years": age,
        "parking": parking, "elevator": elevator, "storage": storage,
        "transit_mode": "مترو" if city in ["تهران", "مشهد", "اصفهان", "شیراز", "کرج", "تبریز"] else "اتوبوس",
        "transit_station": data["stations"][i % len(data["stations"])], "transit_distance_m": walk * 72,
        "transit_walk_minutes": walk, "neighborhood_info": NEIGHBORHOOD_INFO[i % len(NEIGHBORHOOD_INFO)],
        "description": DESCRIPTIONS[i % len(DESCRIPTIONS)],
        "images_json": json.dumps([f"/property-{1 + (i % 3)}.svg"], ensure_ascii=False),
        "listing_date": f"2026-09-{(i % 26)+1:02d}", "source_name": SYNTHETIC_SOURCES[i % len(SYNTHETIC_SOURCES)],
        "source_url": None, "title": f"{tx_label} {title_type} {bedrooms} خوابه، {area} متر در {neighborhood}",
    }


def seed_database(db: Session) -> int:
    if db.query(Advertisement).count() > 0:
        return 0
    rng = random.Random(20261017)
    records: list[dict] = []
    curated = [
        ("تهران", "سعادت‌آباد", 85, 2, 14.2, True, True, True, 7, 5, "apartment", "sale"),
        ("تهران", "پونک", 92, 2, 13.4, True, True, False, 5, 9, "apartment", "sale"),
        ("تهران", "نارمک", 78, 2, 12.5, True, False, True, 14, 12, "apartment", "sale"),
        ("تهران", "یوسف‌آباد", 83, 2, 14.9, True, True, True, 9, 4, "apartment", "sale"),
        ("تهران", "اکباتان", 96, 2, 15.8, True, True, True, 6, 15, "apartment", "sale"),
        ("تهران", "تهرانپارس", 88, 2, 11.9, False, True, True, 11, 8, "apartment", "sale"),
        ("تهران", "ستارخان", 75, 2, 10.8, True, False, False, 8, 18, "apartment", "sale"),
        ("تهران", "شهرک غرب", 110, 3, 19.2, True, True, True, 6, 3, "apartment", "sale"),
        ("تهران", "ونک", 68, 1, 9.7, True, True, False, 4, 7, "apartment", "sale"),
        ("تهران", "جنت‌آباد", 102, 3, 14.8, True, True, True, 13, 6, "apartment", "sale"),
        ("تهران", "نارمک", 86, 2, 13.9, False, True, True, 16, 20, "apartment", "sale"),
        ("تهران", "پونک", 89, 2, 14.6, True, True, True, 10, 4, "apartment", "sale"),
        ("مشهد", "احمدآباد", 90, 2, 6.9, True, True, True, 7, 5, "apartment", "sale"),
        ("اصفهان", "مرداویج", 95, 2, 8.3, True, True, True, 8, 6, "apartment", "sale"),
        ("شیراز", "معالی‌آباد", 88, 2, 8.1, True, True, False, 6, 4, "apartment", "sale"),
        ("کرج", "جهانشهر", 105, 2, 7.2, True, True, True, 9, 7, "apartment", "sale"),
        ("تهران", "سعادت‌آباد", 82, 2, 1.2, True, True, True, 7, 5, "apartment", "rent"),
        ("تهران", "تهرانپارس", 75, 2, 650, True, True, False, 5, 11, "apartment", "rent"),
        ("مشهد", "سجاد", 90, 2, 650, True, True, True, 7, 3, "apartment", "rent"),
        ("اصفهان", "جلفا", 80, 2, 500, False, True, True, 10, 8, "apartment", "rent"),
    ]
    for i, item in enumerate(curated):
        city, neighborhood, area, beds, price, parking, elevator, storage, walk, age, ptype, tx = item
        rec = _curated_record(i, city, neighborhood, area, beds, price, parking, elevator, storage, walk, age, ptype, tx,
                              deposit_m=int(price * 1_000) if tx == "rent" else 800,
                              rent_m=int(price * 15) if tx == "rent" else 20)
        if tx == "rent":
            # The compact curated tuple encodes an example deposit value (in millions) in price.
            rec["deposit_toman"] = int(price * 1_000_000) if price > 10 else int(price * 1_000_000_000)
            rec["monthly_rent_toman"] = (18 if i % 2 else 22) * 1_000_000
        records.append(rec)

    # Fill a broad and repeatable synthetic catalog (160 unique properties total).
    for i in range(len(records), 160):
        records.append(_make_record(i, rng))

    for rec in records:
        db.add(Advertisement(**rec))
    db.flush()

    # Twenty-five deliberately near-duplicate advertisements, with small textual/price variations.
    for dup_idx, base_idx in enumerate([0, 1, 2, 3, 5, 7, 8, 12, 13, 14, 16, 17, 20, 25, 31, 38, 42, 49, 57, 66, 74, 81, 96, 112, 133]):
        base = records[base_idx]
        duplicate = dict(base)
        duplicate["source_name"] = SYNTHETIC_SOURCES[(dup_idx + 2) % len(SYNTHETIC_SOURCES)]
        duplicate["title"] = base["title"].replace("،", " ").replace("متر", "متری") + " | آگهی نمونه"
        duplicate["description"] = base["description"] + " متن آگهی با نگارش متفاوت."
        duplicate["latitude"] = round(base["latitude"] + 0.00025, 5)
        duplicate["longitude"] = round(base["longitude"] - 0.00022, 5)
        duplicate["source_url"] = None
        if duplicate["transaction_type"] == "sale" and duplicate["sale_price_toman"]:
            duplicate["sale_price_toman"] = int(duplicate["sale_price_toman"] * (1 + (dup_idx % 3 - 1) * 0.012))
        duplicate["group_key"] = base["group_key"]
        db.add(Advertisement(**duplicate))
    db.commit()
    return len(records) + 25
