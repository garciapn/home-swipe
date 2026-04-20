"""Daily scraper: realtor.com + Zillow + Redfin for Leesburg VA SFH $500K-$1M.

Dedupes across sources, computes distance to Church & King St in historic
downtown Leesburg, and writes data/listings.json consumed by index.html.
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from homeharvest import scrape_property

# Historic downtown Leesburg — intersection of Church St NE and King St N.
ANCHOR_LAT = 39.1157
ANCHOR_LON = -77.5636

LOCATION = "Leesburg, VA"
MIN_PRICE = 500_000
MAX_PRICE = 1_000_000
SITES = ["realtor.com", "zillow", "redfin"]
PAST_DAYS = 90

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "listings.json"


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def scrape_all() -> pd.DataFrame:
    frames = []
    for site in SITES:
        try:
            df = scrape_property(
                location=LOCATION,
                listing_type="for_sale",
                site_name=site,
                past_days=PAST_DAYS,
            )
            if df is not None and len(df):
                df["_source"] = site
                frames.append(df)
                print(f"[{site}] {len(df)} listings", file=sys.stderr)
        except Exception as exc:
            print(f"[{site}] failed: {exc}", file=sys.stderr)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def filter_sfh_in_price(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df["price"] = pd.to_numeric(df.get("list_price"), errors="coerce")
    if "style" in df.columns:
        is_sfh = df["style"].fillna("").str.upper().str.contains("SINGLE")
    else:
        is_sfh = pd.Series([True] * len(df))
    mask = is_sfh & df["price"].between(MIN_PRICE, MAX_PRICE)
    return df[mask].reset_index(drop=True)


def dedupe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if "mls_id" in df.columns:
        with_mls = df.dropna(subset=["mls_id"]).drop_duplicates(subset=["mls_id"], keep="first")
        without_mls = df[df["mls_id"].isna()]
    else:
        with_mls = df.iloc[0:0]
        without_mls = df
    if "full_street_line" in without_mls.columns:
        without_mls = without_mls.drop_duplicates(subset=["full_street_line"], keep="first")
    return pd.concat([with_mls, without_mls], ignore_index=True)


def to_listing(row: pd.Series) -> dict:
    def g(k, default=None):
        v = row.get(k, default)
        if pd.isna(v):
            return default
        return v

    lat = g("latitude")
    lon = g("longitude")
    distance = (
        round(haversine_miles(ANCHOR_LAT, ANCHOR_LON, float(lat), float(lon)), 2)
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

    price = int(g("list_price")) if g("list_price") is not None else None
    est_value = int(g("estimated_value")) if g("estimated_value") is not None else None
    value_score = None
    if price and est_value:
        value_score = round((est_value - price) / est_value * 100, 1)

    return {
        "address": address,
        "price": price,
        "distance_miles": distance,
        "beds": int(g("beds")) if g("beds") is not None else None,
        "baths": float(g("full_baths")) if g("full_baths") is not None else None,
        "half_baths": int(g("half_baths")) if g("half_baths") is not None else None,
        "sqft": int(g("sqft")) if g("sqft") is not None else None,
        "lot_sqft": int(g("lot_sqft")) if g("lot_sqft") is not None else None,
        "year_built": int(g("year_built")) if g("year_built") is not None else None,
        "stories": int(g("stories")) if g("stories") is not None else None,
        "garage": int(g("parking_garage")) if g("parking_garage") is not None else None,
        "days_on_mls": int(g("days_on_mls")) if g("days_on_mls") is not None else None,
        "hoa_fee": int(g("hoa_fee")) if g("hoa_fee") is not None else None,
        "new_construction": bool(g("new_construction")) if g("new_construction") is not None else None,
        "url": g("property_url"),
        "source": g("_source"),
        "status": g("status"),
        "list_date": str(g("list_date")) if g("list_date") is not None else None,
        "price_per_sqft": int(g("price_per_sqft")) if g("price_per_sqft") is not None else None,
        "estimated_value": est_value,
        "value_score": value_score,
        "last_sold_price": int(g("last_sold_price")) if g("last_sold_price") is not None else None,
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
    distance_penalty = (distance or 10) * 2
    freshness_bonus = max(0, 30 - days) * 0.2
    return value_score + freshness_bonus - distance_penalty


def main() -> int:
    df = scrape_all()
    print(f"scraped: {len(df)}", file=sys.stderr)
    df = filter_sfh_in_price(df)
    print(f"after SFH + price filter: {len(df)}", file=sys.stderr)
    df = dedupe(df)
    print(f"after dedupe: {len(df)}", file=sys.stderr)
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
            "sources": SITES,
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
