from app.search import fallback_parse_query, group_ads, search_properties
from app.schemas import SearchCriteria
from app.database import Base, engine, SessionLocal
from app.seed import seed_database
from app.models import Advertisement


def test_query_parser_extracts_persian_criteria():
    c = fallback_parse_query("آپارتمان دو خوابه برای خرید در تهران تا ۱۵ میلیارد تومان، نزدیک مترو و دارای پارکینگ")
    assert c.transaction_type == "sale"
    assert c.city == "تهران"
    assert c.property_type == "apartment"
    assert c.bedrooms == 2
    assert c.max_price_toman == 15_000_000_000
    assert "parking" in c.preferred_amenities
    assert c.transit_preference_minutes == 10


def test_duplicate_grouping_and_search():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.query(Advertisement).count() == 0:
            seed_database(db)
        response = search_properties(db, SearchCriteria(transaction_type="sale", city="تهران", bedrooms=2, max_price_toman=15_000_000_000, preferred_amenities=["parking"], transit_preference_minutes=10))
        assert response["total"] >= 1
        assert all(x["city"] == "تهران" and x["transaction_type"] == "sale" for x in response["results"])
        grouped = [x for x in response["results"] if x["advertisement_count"] > 1]
        assert grouped, "seed should include visible duplicate groups"


def test_strict_constraints_and_near_matches():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.query(Advertisement).count() == 0:
            seed_database(db)
        response = search_properties(db, SearchCriteria(transaction_type="sale", city="تهران", bedrooms=2, max_price_toman=1), "relevance")
        assert response["results"] == []
        assert response["near_matches"]
        assert all(x["transaction_type"] == "sale" and x["city"] == "تهران" for x in response["near_matches"])
        assert "بودجه خرید" in response["near_matches"][0]["failed_constraints"]


def test_query_parser_normalizes_neighborhood_names():
    criteria = fallback_parse_query("آپارتمان دو خوابه در تهران، محله سعادت‌آباد")
    assert criteria.city == "تهران"
    assert criteria.neighborhood == "سعادت‌آباد"


def test_conservative_deduplication_without_shared_group_key():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.query(Advertisement).count() == 0:
            seed_database(db)
        base = db.query(Advertisement).filter(Advertisement.group_key == "demo-0000").first()
        values = {column.name: getattr(base, column.name) for column in Advertisement.__table__.columns if column.name != "id"}
        values["group_key"] = "independent-source-id"
        values["title"] = base.title + " | آگهی نمونه"
        values["description"] = base.description + " متن آگهی با نگارش متفاوت."
        values["latitude"] = base.latitude + 0.0002
        values["longitude"] = base.longitude - 0.0002
        inferred_duplicate = Advertisement(id=100000, **values)
        grouped = group_ads([base, inferred_duplicate])
        assert len(grouped) == 1
        assert len(grouped[0]) == 2


def test_rial_and_rent_amounts_normalize_to_toman():
    sale = fallback_parse_query("آپارتمان برای خرید در تهران تا ۱۵۰ میلیارد ریال")
    assert sale.max_price_toman == 15_000_000_000
    rent = fallback_parse_query("آپارتمان برای اجاره در تهران با ودیعه ۸۰۰ میلیون تومان و اجاره ماهانه ۲۰ میلیون تومان")
    assert rent.max_deposit_toman == 800_000_000
    assert rent.max_monthly_rent_toman == 20_000_000


def test_simple_query_avoids_llm_call(monkeypatch):
    from app.search import interpret_query

    def unexpected_call(*args, **kwargs):
        raise AssertionError("simple, well-structured search should stay deterministic")

    monkeypatch.setattr("app.search.chat_json", unexpected_call)
    criteria, source = interpret_query("آپارتمان دو خوابه برای خرید در تهران تا ۱۵ میلیارد تومان، نزدیک مترو")
    assert source == "rules"
    assert criteria.bedrooms == 2


def test_complex_query_uses_cheap_tier_when_configured(monkeypatch):
    import os
    from app.search import interpret_query

    monkeypatch.setenv("AI_CHEAP_BASE_URL", "http://model.example/v1")
    monkeypatch.setenv("AI_CHEAP_MODEL", "cheap-model")
    called = []

    def mock_chat(tier, system_prompt, user_prompt, timeout=22.0):
        called.append(tier)
        return None

    monkeypatch.setattr("app.search.chat_json", mock_chat)
    _, source = interpret_query("بهترین انتخاب برای یک خانواده، ترجیحاً در محله‌ای آرام و با رفت‌وآمد راحت")
    assert called == ["cheap"]
    assert source == "rules"
