# 🏡 Amy — Autonomous Real Estate Agent

Amy is an autonomous home-hunting agent on a mission: find the perfect home for Paolo's parents in **Old Town Leesburg, VA**. She runs twice a day, scrapes the major listing platforms, and delivers curated results via a Tinder-style swipe webapp — plus a Telegram digest.

---

## 🎯 Search Criteria

| Parameter | Value |
|---|---|
| 📍 **Location** | Within **3 miles** of Key Street Oyster Bar, Old Town Leesburg VA |
| 💰 **Price** | $500,000 – $1,000,000 |
| 🛏️ **Bedrooms** | 3+ |
| 🛁 **Bathrooms** | 2+ |
| 🏠 **Type** | Single-Family Home (SFH) |

---

## 🔍 Data Sources

Amy pulls listings from three platforms simultaneously:

- 🔴 **Realtor.com** — via HomeHarvest scraper
- 🔵 **Zillow** — via HomeHarvest scraper
- 🟢 **Redfin** — via HomeHarvest scraper

All results are deduplicated, filtered, and ranked before output.

---

## 📱 Features

### Swipe Webapp (GitHub Pages)
Amy pushes a fresh **Tinder-style swipe interface** to GitHub Pages after every run:

🌐 **[garciapn.github.io/amy-homes](https://garciapn.github.io/amy-homes/)**

- Swipe right to save, left to skip
- Each card shows: photo, price, beds/baths, HOA, days on market, distance from Old Town
- Updated automatically every run — no manual intervention needed

### Telegram Digest
After each run, Amy sends a digest to Paolo's Telegram channel including:
- 💰 Price
- 🛏️ Beds / 🛁 Baths
- 🏘️ HOA (if applicable)
- 📅 Days listed
- 📍 Distance from Old Town Leesburg

---

## ⏰ Schedule

| Time | Action |
|---|---|
| 8:00 AM | Morning scrape → update webapp → Telegram digest |
| 8:00 PM | Evening scrape → update webapp → Telegram digest |

Scheduled via macOS **launchd** plist. Fully autonomous.

---

## 🛠️ Tech Stack

- **Python 3** — core agent orchestration
- **HomeHarvest** — multi-platform MLS scraper (Realtor.com, Zillow, Redfin)
- **GitHub Pages** — hosts the swipe webapp (auto-deployed each run)
- **Telegram Bot API** — push digests
- **launchd** — macOS native background scheduling
- **Geolocation** — distance calc from Old Town Leesburg anchor point

---

## 📁 Project Structure

```
amy-homes/
├── amy.py              # Core agent — scrapes, filters, formats
├── webapp/             # Tinder-style swipe UI (HTML/JS/CSS)
│   └── index.html      # Auto-generated each run, pushed to Pages
├── data/               # Raw listing cache (JSON)
├── filters.py          # Search criteria and ranking logic
├── deploy.sh           # Push webapp to GitHub Pages
└── launchd/            # macOS scheduler plist
```

---

## 🤖 Fleet Role

Amy is a focused, single-mission agent — she doesn't coordinate with the broader fleet. Her job is to surface housing opportunities and let Paolo's parents decide. Results are delivered to the same Telegram channel used by the rest of the agent crew.

---

## 🚀 Running Manually

```bash
# Trigger a manual scrape + webapp update
python3 amy.py

# Deploy webapp to GitHub Pages only
bash deploy.sh
```

---

*Amy doesn't sleep. So Paolo's parents can find their dream home faster.* 🏡
