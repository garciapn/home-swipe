"""Daily scraper: Realtor.com for Leesburg VA single-family homes $500K-$1M.

Dedupes by MLS ID then address, computes distance to Church & King St in
historic downtown Leesburg, and writes data/listings.json consumed by
index.html.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from homeharvest import scrape_property

# Historic downtown Leesburg — Church St NE × King St N.
ANCHOR_LAT = 39.1157
ANCHOR_LON = -77.5636

LOCATION = "Leesburg, VA"
MIN_PRICE = 500_000
MAX_PRICE = 1_000_000
PAST_DAYS = 90
MAX_RESULTS = 500

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "listings.json"


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def scrape() -> pd.DataFrame:
    df = scrape_property(
        location=LOCATION,
        listing_type="for_sale",
        property_type=["single_family"],
        price_min=MIN_PRICE,
        price_max=MAX_PRICE,
        past_days=PAST_DAYS,
        mls_only=False,
        extra_property_data=True,
        exclude_pending=True,
        limit=MAX_RESULTS,
    )
    print(f"scraped: {0 if df is None else len(df)}", file=sys.stderr)
    return df if df is not None else pd.DataFrame()


def dedupe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    before = len(df)
    if "mls_id" in df.columns:
        df = df.sort_values(by="list_date", na_position="last").drop_duplicates(
            subset=["mls_id"], keep="first"
        )
    if "full_street_line" in df.columns:
        df = df.drop_duplicates(subset=["full_street_line"], keep="first")
    if "property_url" in df.columns:
        df = df.drop_duplicates(subset=["property_url"], keep="first")
    print(f"after dedupe: {len(df)} (removed {before - len(df)})", file=sys.stderr)
    return df.reset_index(drop=True)


def _num(value, caster=float):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return caster(value)
    except (TypeError, ValueError):
        return None


def to_listing(row: pd.Series) -> dict:
    def g(key, default=None):
        v = row.get(key, default)
        return default if (v is None or (isinstance(v, float) and pd.isna(v))) else v

    lat = _num(g("latitude"))
    lon = _num(g("longitude"))
    distance = (
        round(haversine_miles(ANCHOR_LAT, ANCHOR_LON, lat, lon), 2)
        if lat is not None and lon is not None
        else None
    )

    address_parts = [
        g("full_street_line"),
        g("city"),
        g("state"),
        str(g("zip_code")) if g("zip_code") is not None else None,
    ]
    address = ", ".join(p for p in address_parts if p)

    alt_photos = g("alt_photos")
    if isinstance(alt_photos, str):
        alt_photos = [p.strip() for p in alt_photos.split(",") if p.strip()]

    price = _num(g("list_price"), int)
    est_value = _num(g("estimated_value"), int)
    value_score = None
    if price and est_value:
        value_score = round((est_value - price) / est_value * 100, 1)

    return {
        "address": address,
        "price": price,
        "distance_miles": distance,
        "beds": _num(g("beds"), int),
        "baths": _num(g("full_baths"), float),
        "half_baths": _num(g("half_baths"), int),
        "sqft": _num(g("sqft"), int),
        "lot_sqft": _num(g("lot_sqft"), int),
        "year_built": _num(g("year_built"), int),
        "stories": _num(g("stories"), int),
        "garage": _num(g("parking_garage"), int),
        "days_on_mls": _num(g("days_on_mls"), int),
        "hoa_fee": _num(g("hoa_fee"), int),
        "new_construction": bool(g("new_construction")) if g("new_construction") is not None else None,
        "url": g("property_url"),
        "source": "realtor.com",
        "status": g("status"),
        "list_date": str(g("list_date")) if g("list_date") is not None else None,
        "price_per_sqft": _num(g("price_per_sqft"), int),
        "estimated_value": est_value,
        "value_score": value_score,
        "last_sold_price": _num(g("last_sold_price"), int),
        "last_sold_date": str(g("last_sold_date")) if g("last_sold_date") is not None else None,
        "photo": g("primary_photo"),
        "alt_photos": alt_photos,
        "description": g("text"),
        "agent_name": g("agent"),
        "mls_id": g("mls_id"),
    }


def rank(listing: dict) -> float:
    distance = listing.get("distance_miles")
    value_score = listing.get("value_score") or 0
    days = listing.get("days_on_mls") or 0
    distance_penalty = (distance if distance is not None else 10) * 2
    freshness_bonus = max(0, 30 - days) * 0.2
    return value_score + freshness_bonus - distance_penalty


def main() -> int:
    df = scrape()
    df = dedupe(df)
    if df.empty:
        print("no listings found — leaving existing data untouched", file=sys.stderr)
        return 1

    listings = [to_listing(row) for _, row in df.iterrows()]
    listings = [l for l in listings if l["price"] and l["url"]]
    for l in listings:
        l["_rank"] = round(rank(l), 2)
    listings.sort(key=lambda l: l["_rank"], reverse=True)

    payload = {
        "generated_at": date.today().isoformat(),
        "anchor": {"lat": ANCHOR_LAT, "lon": ANCHOR_LON, "name": "Church & King St, Leesburg VA"},
        "criteria": {
            "location": LOCATION,
            "min_price": MIN_PRICE,
            "max_price": MAX_PRICE,
            "type": "single_family",
            "past_days": PAST_DAYS,
        },
        "count": len(listings),
        "listings": listings,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, default=str))
    print(f"wrote {len(listings)} listings to {OUT_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
