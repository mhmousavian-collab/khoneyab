import os
import json
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from .models import Advertisement
from .seed import CITY_DATA, seed_database
from .schemas import SearchRequest, InterpretRequest, RefineRequest, CompareSynthesisRequest, SearchCriteria
from .search import interpret_query, refine_query, search_properties, get_group_detail
from .ai import configured_tiers, comparison_summary


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    # The seed function is a no-op once any listing exists; persistent data is never overwritten.
    from .database import SessionLocal
    with SessionLocal() as db:
        seed_database(db)
    yield


app = FastAPI(
    title="Khoneyab API",
    description="Synthetic, intent-aware residential property search demo for Iran.",
    version="1.0.0",
    lifespan=lifespan,
)

origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8081").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    return {"status": "ok", "service": "khoneyab-api", "advertisements": db.query(Advertisement).count(), "synthetic_data": True}


@app.get("/api/meta")
def metadata(db: Session = Depends(get_db)):
    return {
        "cities": list(CITY_DATA.keys()),
        "neighborhoods": {city: data["neighborhoods"] for city, data in CITY_DATA.items()},
        "property_types": [
            {"value": "apartment", "label": "آپارتمان"},
            {"value": "house", "label": "خانه"},
            {"value": "villa", "label": "ویلا"},
        ],
        "amenities": [
            {"value": "parking", "label": "پارکینگ"},
            {"value": "elevator", "label": "آسانسور"},
            {"value": "storage", "label": "انباری"},
        ],
        "ai": configured_tiers(),
        "advertisements": db.query(Advertisement).count(),
        "unique_properties": len({x[0] for x in db.query(Advertisement.group_key).distinct().all()}),
        "synthetic_data": True,
    }


@app.post("/api/search")
def search(payload: SearchRequest, db: Session = Depends(get_db)):
    return search_properties(db, payload.criteria, payload.sort_by, payload.limit)


@app.post("/api/search/interpret")
def interpret(payload: InterpretRequest):
    criteria, parsed_by = interpret_query(payload.query, payload.current_criteria)
    return {"criteria": criteria.model_dump(), "parsed_by": parsed_by, "ai_available": configured_tiers()["cheap"], "message": "criteria extracted; all filtering and ranking is handled by application code"}


@app.post("/api/search/refine")
def refine(payload: RefineRequest):
    criteria, parsed_by = refine_query(payload.message, payload.current_criteria)
    return {"criteria": criteria.model_dump(), "parsed_by": parsed_by, "ai_available": configured_tiers()["standard"]}


@app.get("/api/properties/{property_id}")
def property_detail(property_id: str, criteria: str | None = Query(default=None), db: Session = Depends(get_db)):
    parsed_criteria = None
    if criteria:
        try:
            parsed_criteria = SearchCriteria.model_validate(json.loads(criteria))
        except (ValueError, TypeError):
            parsed_criteria = None
    property_data = get_group_detail(db, property_id, parsed_criteria)
    if not property_data:
        raise HTTPException(status_code=404, detail="Property not found")
    return property_data


@app.get("/api/compare")
def compare_properties(ids: str, db: Session = Depends(get_db)):
    group_ids = list(dict.fromkeys([part.strip() for part in ids.split(",") if part.strip()]))
    if len(group_ids) < 2 or len(group_ids) > 3:
        raise HTTPException(status_code=400, detail="Provide 2 or 3 property IDs")
    result = []
    for property_id in group_ids:
        prop = get_group_detail(db, property_id)
        if prop:
            result.append(prop)
    if len(result) != len(group_ids):
        raise HTTPException(status_code=404, detail="One or more properties were not found")
    return {"properties": result}


@app.post("/api/compare/synthesis")
def compare_synthesis(payload: CompareSynthesisRequest):
    summary, source = comparison_summary(payload.properties, payload.user_goal)
    if summary:
        return {"summary": summary, "generated_by": source}
    return {"summary": None, "generated_by": source, "message": "Premium AI is not configured or unavailable."}


@app.get("/")
def root():
    return {"service": "Khoneyab API", "docs": "/docs", "health": "/api/health"}
