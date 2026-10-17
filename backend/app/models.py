from sqlalchemy import Boolean, Column, Float, Integer, String, Text, Index
from .database import Base


class Advertisement(Base):
    __tablename__ = "advertisements"
    id = Column(Integer, primary_key=True, index=True)
    group_key = Column(String(80), index=True, nullable=False)
    transaction_type = Column(String(12), nullable=False, index=True)  # sale | rent
    property_type = Column(String(20), nullable=False, index=True)
    city = Column(String(40), nullable=False, index=True)
    neighborhood = Column(String(60), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    area_sqm = Column(Float, nullable=False)
    bedrooms = Column(Integer, nullable=False)
    sale_price_toman = Column(Integer, nullable=True)
    deposit_toman = Column(Integer, nullable=True)
    monthly_rent_toman = Column(Integer, nullable=True)
    floor_number = Column(Integer, nullable=True)
    total_floors = Column(Integer, nullable=True)
    building_age_years = Column(Integer, nullable=True)
    parking = Column(Boolean, default=False, nullable=False)
    elevator = Column(Boolean, default=False, nullable=False)
    storage = Column(Boolean, default=False, nullable=False)
    transit_mode = Column(String(30), nullable=True)
    transit_station = Column(String(80), nullable=True)
    transit_distance_m = Column(Integer, nullable=True)
    transit_walk_minutes = Column(Integer, nullable=True)
    neighborhood_info = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    images_json = Column(Text, nullable=False, default="[]")
    listing_date = Column(String(10), nullable=False)
    source_name = Column(String(80), nullable=False)
    source_url = Column(String(500), nullable=True)
    title = Column(String(200), nullable=False)

    __table_args__ = (
        Index("ix_ads_group_transaction", "group_key", "transaction_type"),
    )
