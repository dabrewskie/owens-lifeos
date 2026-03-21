#!/usr/bin/env python3
"""
Investment Intelligence Dashboard Updater — v3 (Deep Profiles + Sentiment)
Pulls live market data via yfinance, calculates technical signals,
scores opportunities, fetches fundamentals, and calls Claude API for
natural language analysis + stock profiles with sentiment intelligence.
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# S6 Alert System for notifications
try:
    sys.path.insert(0, str(Path.home() / "Documents" / "S6_COMMS_TECH" / "scripts"))
    from s6_alert import alert, CRITICAL, HIGH, MEDIUM, LOW, INFO
    HAS_ALERTS = True
except ImportError:
    HAS_ALERTS = False
    print("WARN: s6_alert not available — notifications disabled")

try:
    import yfinance as yf
except ImportError:
    print("ERROR: yfinance not installed. Run: pip3 install yfinance")
    sys.exit(1)

try:
    import anthropic
except ImportError:
    print("WARN: anthropic SDK not installed — analysis will be quantitative only")
    anthropic = None

# ─── Configuration ───────────────────────────────────────────────
DASHBOARD_DIR = Path.home() / "Documents" / "S6_COMMS_TECH" / "dashboard"
OUTPUT_FILE = DASHBOARD_DIR / "invest_intel_data.json"

# API key from WealthBuilder .env.local
ENV_FILE = Path.home() / "wealth-builder" / "backend" / ".env.local"

def load_api_key():
    """Load Anthropic API key from WealthBuilder env."""
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("ANTHROPIC_API_KEY")


# Watchlist organized by thesis
WATCHLIST = {
    "vertical_ecosystems": {
        "label": "Vertical Ecosystems",
        "tickers": {
            "TSLA": "Tesla — Vehicles/Energy/Robotics/AI flywheel",
            "AMZN": "Amazon — E-comm/AWS/Logistics/Health data layers",
            "GOOG": "Alphabet — Search/Android/Waymo/DeepMind ecosystem",
            "AAPL": "Apple — Devices/Services/Health/Spatial Computing",
            "MSFT": "Microsoft — Azure/Office/GitHub/Copilot/LinkedIn, deepest AI integration",
            "DE": "Deere — Equipment/Precision Ag/Autonomy platform",
            "META": "Meta — Social/VR-AR/AI Models/Commerce engine",
        }
    },
    "realworld_data": {
        "label": "Real-World Data Moats",
        "tickers": {
            "ISRG": "Intuitive Surgical — 44K+ da Vinci systems, surgical AI data",
            "UNH": "UnitedHealth — 150M+ lives, claims + Optum data platform",
            "TMO": "Thermo Fisher — Instruments in every major research lab",
            "HON": "Honeywell — Industrial IoT sensors, Forge platform",
            "PLTR": "Palantir — Defense/intel data integration (Foundry/Gotham)",
            "CAT": "Caterpillar — Construction/mining telemetry, autonomous trucks",
            "V": "Visa — 65K transactions/sec, sees global spending in real-time",
            "CRM": "Salesforce — Enterprise CRM data moat, Agentforce AI platform",
        }
    },
    "picks_and_shovels": {
        "label": "Picks & Shovels (AI Infra)",
        "tickers": {
            "NVDA": "NVIDIA — GPU monopoly for AI training/inference, CUDA lock-in",
            "AVGO": "Broadcom — Custom AI chips (Google TPUs), networking, VMware",
            "TSM": "TSMC — Fabricates every advanced AI chip. Taiwan risk.",
            "ASML": "ASML — Only EUV lithography maker. Monopoly.",
            "AMD": "AMD — GPU alternative, EPYC server CPUs, Xilinx FPGAs",
            "ARM": "Arm Holdings — Architecture in everything, phones to data centers",
            "MRVL": "Marvell — Custom AI silicon, data center networking",
            "ETN": "Eaton — Power management, data center electrical infrastructure",
            "VST": "Vistra — Power generation, nuclear fleet for data centers",
            "CEG": "Constellation — Largest US nuclear fleet, clean baseload",
            "GEV": "GE Vernova — Gas turbines, grid equipment, electrification",
            "PWR": "Quanta — Builds transmission lines, substations, grid",
            "VRT": "Vertiv — Data center cooling, power, infrastructure",
            "DLR": "Digital Realty — Data center REIT, physical AI space",
            "EQIX": "Equinix — Global data center interconnection",
        }
    },
    "digital_security": {
        "label": "Digital Security & Cyber",
        "tickers": {
            "CRWD": "CrowdStrike — Endpoint security, attack data flywheel from every breach",
            "PANW": "Palo Alto Networks — Platform consolidation, acquiring everything",
            "ZS": "Zscaler — Zero-trust cloud security, every remote worker needs this",
        }
    },
    "healthcare_ai": {
        "label": "Healthcare AI & Pharma",
        "tickers": {
            "LLY": "Eli Lilly — GLP-1 dominance (Mounjaro/Zepbound), $327M portfolio insider view",
            "VRTX": "Vertex — Gene editing + CRISPR pipeline, pain/rare disease",
            "DXCM": "Dexcom — Continuous glucose monitoring, metabolic health data moat",
            "VEEV": "Veeva Systems — Cloud platform for pharma, owns clinical trial data layer",
        }
    },
    "defense_aerospace": {
        "label": "Defense & Aerospace",
        "tickers": {
            "LMT": "Lockheed Martin — F-35, hypersonics, space systems, autonomous defense",
            "RTX": "Raytheon — Defense electronics, Pratt & Whitney engines, missiles",
            "LHX": "L3Harris — ISR, tactical comms, space payloads",
        }
    },
    "raw_materials": {
        "label": "Raw Materials & Commodities",
        "tickers": {
            "FCX": "Freeport-McMoRan — Copper (wiring, grid, EVs, data centers)",
            "SCCO": "Southern Copper — Pure copper play, massive reserves",
            "ALB": "Albemarle — Lithium for EVs and grid storage batteries",
            "MP": "MP Materials — Only US rare earth mine, magnet supply",
            "CCJ": "Cameco — Uranium for nuclear renaissance / AI power demand",
            "AA": "Alcoa — Aluminum for data center construction and EVs",
            "AWK": "American Water Works — Water utility, data centers + chip fabs need massive water",
        }
    }
}

MACRO_TICKERS = {
    "sp500": {"symbol": "^GSPC", "label": "S&P 500", "fmt": ",.0f"},
    "nasdaq": {"symbol": "^IXIC", "label": "NASDAQ", "fmt": ",.0f"},
    "dxy": {"symbol": "DX-Y.NYB", "label": "US Dollar (DXY)", "fmt": ".2f"},
    "oil_wti": {"symbol": "CL=F", "label": "Oil (WTI)", "fmt": ".2f", "prefix": "$"},
    "gold": {"symbol": "GC=F", "label": "Gold", "fmt": ",.0f", "prefix": "$"},
    "vix": {"symbol": "^VIX", "label": "VIX", "fmt": ".2f"},
    "us10y": {"symbol": "^TNX", "label": "10Y Treasury", "fmt": ".2f", "suffix": "%"},
    "copper": {"symbol": "HG=F", "label": "Copper", "fmt": ".4f", "prefix": "$"},
    # ── Extended Macro (regime detection) ──
    "us2y": {"symbol": "^TWO", "label": "2Y Treasury", "fmt": ".2f", "suffix": "%"},
    "us30y": {"symbol": "^TYX", "label": "30Y Treasury", "fmt": ".2f", "suffix": "%"},
    "russell2000": {"symbol": "^RUT", "label": "Russell 2000", "fmt": ",.0f"},
    "tip": {"symbol": "TIP", "label": "TIPS (Inflation Exp)", "fmt": ".2f", "prefix": "$"},
    "hyg": {"symbol": "HYG", "label": "High Yield Corp", "fmt": ".2f", "prefix": "$"},
    "lqd": {"symbol": "LQD", "label": "Inv Grade Corp", "fmt": ".2f", "prefix": "$"},
    # ── Sector Rotation ETFs ──
    "xlk": {"symbol": "XLK", "label": "Tech Sector", "fmt": ".2f", "prefix": "$"},
    "xle": {"symbol": "XLE", "label": "Energy Sector", "fmt": ".2f", "prefix": "$"},
    "xlf": {"symbol": "XLF", "label": "Financials", "fmt": ".2f", "prefix": "$"},
    "xlv": {"symbol": "XLV", "label": "Healthcare", "fmt": ".2f", "prefix": "$"},
    "xli": {"symbol": "XLI", "label": "Industrials", "fmt": ".2f", "prefix": "$"},
    "xlu": {"symbol": "XLU", "label": "Utilities", "fmt": ".2f", "prefix": "$"},
    "xlb": {"symbol": "XLB", "label": "Materials", "fmt": ".2f", "prefix": "$"},
    "xlp": {"symbol": "XLP", "label": "Consumer Staples", "fmt": ".2f", "prefix": "$"},
    "xly": {"symbol": "XLY", "label": "Consumer Disc", "fmt": ".2f", "prefix": "$"},
}


# ─── Technical Analysis ─────────────────────────────────────────

def calc_rsi(prices, period=14):
    """Calculate RSI from a price series."""
    if len(prices) < period + 1:
        return None
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def calc_sma(prices, period):
    """Simple moving average."""
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period


def fetch_extended_data(symbol):
    """Fetch 6 months of data for technical analysis."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="6mo")
        if hist.empty:
            return None
        return hist
    except Exception as e:
        print(f"  WARN: Extended data failed for {symbol}: {e}")
        return None


def fetch_fundamentals(symbol):
    """Get key fundamental data from yfinance for stock profiles."""
    try:
        info = yf.Ticker(symbol).info
        mc = info.get("marketCap")
        return {
            "market_cap": mc,
            "market_cap_fmt": f"${mc/1e12:.2f}T" if mc and mc >= 1e12 else (
                f"${mc/1e9:.1f}B" if mc and mc >= 1e9 else (
                    f"${mc/1e6:.0f}M" if mc else None)),
            "pe_ratio": round(info.get("trailingPE"), 1) if info.get("trailingPE") else None,
            "forward_pe": round(info.get("forwardPE"), 1) if info.get("forwardPE") else None,
            "revenue_growth_pct": round(info.get("revenueGrowth", 0) * 100, 1) if info.get("revenueGrowth") else None,
            "profit_margin_pct": round(info.get("profitMargins", 0) * 100, 1) if info.get("profitMargins") else None,
            "dividend_yield_pct": round(info.get("dividendYield", 0) * 100, 2) if info.get("dividendYield") else None,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "employees": info.get("fullTimeEmployees"),
            "summary": info.get("longBusinessSummary"),
            "website": info.get("website"),
        }
    except Exception as e:
        print(f"    WARN: Fundamentals failed for {symbol}: {e}")
        return {}


def analyze_ticker(symbol, description, thesis_key, thesis_label):
    """Full technical + fundamental analysis for a single ticker."""
    hist = fetch_extended_data(symbol)
    if hist is None or len(hist) < 5:
        return {
            "ticker": symbol,
            "description": description,
            "thesis": thesis_label,
            "thesis_key": thesis_key,
            "price": None,
            "daily_change_pct": None,
            "weekly_change_pct": None,
            "trend": "unknown",
            "technicals": {},
            "fundamentals": {},
            "opportunity_score": 0,
            "signal": "NO DATA",
        }

    closes = list(hist['Close'].astype(float))
    volumes = list(hist['Volume'].astype(float))
    current = closes[-1]
    prev = closes[-2] if len(closes) >= 2 else current

    # Daily change
    daily_chg = round(((current - prev) / prev) * 100, 2)

    # Weekly change (5 trading days)
    five_ago = closes[-5] if len(closes) >= 5 else closes[0]
    weekly_chg = round(((current - five_ago) / five_ago) * 100, 2)

    # Monthly change (21 trading days)
    month_ago = closes[-21] if len(closes) >= 21 else closes[0]
    monthly_chg = round(((current - month_ago) / month_ago) * 100, 2)

    # 3-month change
    three_mo = closes[-63] if len(closes) >= 63 else closes[0]
    three_mo_chg = round(((current - three_mo) / three_mo) * 100, 2)

    # Moving averages
    sma_20 = calc_sma(closes, 20)
    sma_50 = calc_sma(closes, 50)
    sma_200 = calc_sma(closes, 200) if len(closes) >= 200 else None

    # RSI
    rsi = calc_rsi(closes)

    # Distance from 52-week high/low
    high_52w = max(closes) if closes else current
    low_52w = min(closes) if closes else current
    dist_from_high = round(((current - high_52w) / high_52w) * 100, 1)
    dist_from_low = round(((current - low_52w) / low_52w) * 100, 1)

    # Volume trend (last 5 days vs 20-day avg)
    if len(volumes) >= 20:
        vol_5d_avg = sum(volumes[-5:]) / 5
        vol_20d_avg = sum(volumes[-20:]) / 20
        vol_ratio = round(vol_5d_avg / vol_20d_avg, 2) if vol_20d_avg > 0 else 1.0
    else:
        vol_ratio = 1.0

    # Price vs SMA position
    above_20 = current > sma_20 if sma_20 else None
    above_50 = current > sma_50 if sma_50 else None
    above_200 = current > sma_200 if sma_200 else None

    # ─── Opportunity Scoring (0-100) ─────────────
    score = 50  # neutral baseline

    # RSI: oversold = opportunity, overbought = caution
    if rsi is not None:
        if rsi < 30:
            score += 20  # heavily oversold — strong buy signal
        elif rsi < 40:
            score += 10  # approaching oversold
        elif rsi > 70:
            score -= 15  # overbought
        elif rsi > 80:
            score -= 25  # heavily overbought

    # Distance from high: bigger drawdown = more opportunity (for thesis-supported names)
    if dist_from_high < -20:
        score += 15  # >20% off highs
    elif dist_from_high < -10:
        score += 8   # 10-20% off highs

    # Price vs moving averages (pullback to support = opportunity)
    if sma_50:
        pct_from_50 = ((current - sma_50) / sma_50) * 100
        if -5 < pct_from_50 < 0:
            score += 10  # sitting on 50-day support
        elif pct_from_50 < -10:
            score += 5   # well below — could be falling knife, partial credit

    # Volume spike on down days = capitulation (bullish contrarian)
    if vol_ratio > 1.5 and weekly_chg < -3:
        score += 8

    # Monthly momentum — reward mean reversion setups
    if monthly_chg < -10:
        score += 10  # big monthly drop = potential bounce
    elif monthly_chg > 15:
        score -= 5   # extended — less attractive entry

    # Clamp score
    score = max(0, min(100, score))

    # Signal determination
    if score >= 75:
        signal = "STRONG BUY"
    elif score >= 60:
        signal = "BUY"
    elif score >= 45:
        signal = "HOLD"
    elif score >= 30:
        signal = "TRIM"
    else:
        signal = "SELL"

    technicals = {
        "rsi": rsi,
        "sma_20": round(sma_20, 2) if sma_20 else None,
        "sma_50": round(sma_50, 2) if sma_50 else None,
        "sma_200": round(sma_200, 2) if sma_200 else None,
        "above_sma20": above_20,
        "above_sma50": above_50,
        "above_sma200": above_200,
        "dist_from_52w_high_pct": dist_from_high,
        "dist_from_52w_low_pct": dist_from_low,
        "monthly_change_pct": monthly_chg,
        "three_month_change_pct": three_mo_chg,
        "volume_ratio_5d_vs_20d": vol_ratio,
    }

    return {
        "ticker": symbol,
        "description": description,
        "thesis": thesis_label,
        "thesis_key": thesis_key,
        "price": round(current, 2),
        "daily_change_pct": daily_chg,
        "weekly_change_pct": weekly_chg,
        "trend": "up" if weekly_chg > 1 else ("down" if weekly_chg < -1 else "stable"),
        "technicals": technicals,
        "fundamentals": {},
        "opportunity_score": score,
        "signal": signal,
    }


# ─── Macro Fetching ─────────────────────────────────────────────

def fetch_macro():
    """Fetch all macro indicators with trend data."""
    print("Fetching macro indicators...")
    macro = {}
    for key, info in MACRO_TICKERS.items():
        hist = fetch_extended_data(info["symbol"])
        if hist is not None and len(hist) >= 2:
            closes = list(hist['Close'].astype(float))
            current = closes[-1]
            prev = closes[-2]
            daily_chg = round(((current - prev) / prev) * 100, 2)
            five_ago = closes[-5] if len(closes) >= 5 else closes[0]
            weekly_pct = round(((current - five_ago) / five_ago) * 100, 2)
            month_ago = closes[-21] if len(closes) >= 21 else closes[0]
            monthly_pct = round(((current - month_ago) / month_ago) * 100, 2)
            trend = "up" if weekly_pct > 1 else ("down" if weekly_pct < -1 else "stable")
            print(f"  {info['label']}: {current:.2f} ({daily_chg:+.2f}%)")
        else:
            current, daily_chg, weekly_pct, monthly_pct, trend = None, None, None, None, "unknown"
            print(f"  {info['label']}: FAILED")

        macro[key] = {
            "label": info["label"],
            "value": current,
            "change_pct": daily_chg,
            "weekly_pct": weekly_pct,
            "monthly_pct": monthly_pct,
            "trend": trend,
            "fmt": info.get("fmt", ".2f"),
            "prefix": info.get("prefix", ""),
            "suffix": info.get("suffix", ""),
        }
    return macro


# ─── Thesis Health ───────────────────────────────────────────────

def assess_thesis_health(watchlist_data):
    """Assess each thesis with detailed metrics."""
    thesis_groups = {}
    for item in watchlist_data:
        key = item["thesis_key"]
        if key not in thesis_groups:
            thesis_groups[key] = []
        thesis_groups[key].append(item)

    health = {}
    for key, items in thesis_groups.items():
        weekly_changes = [i["weekly_change_pct"] for i in items if i.get("weekly_change_pct") is not None]
        scores = [i["opportunity_score"] for i in items if i.get("opportunity_score")]

        if not weekly_changes:
            health[key] = {"status": "UNKNOWN", "signal": "No data", "avg_weekly": None}
            continue

        avg_weekly = sum(weekly_changes) / len(weekly_changes)
        avg_score = sum(scores) / len(scores) if scores else 50
        positive = sum(1 for c in weekly_changes if c > 0)
        breadth = positive / len(weekly_changes)

        # Top movers
        sorted_items = sorted(items, key=lambda x: x.get("weekly_change_pct") or 0)
        best = sorted_items[-1]
        worst = sorted_items[0]

        if avg_weekly > 2.0 and breadth > 0.6:
            status = "STRENGTHENING"
        elif avg_weekly < -2.0 and breadth < 0.4:
            status = "WEAKENING"
        else:
            status = "STABLE"

        signal = (
            f"Avg {avg_weekly:+.1f}% (5d) | Breadth {breadth:.0%} | "
            f"Avg Score {avg_score:.0f}/100 | "
            f"Best: {best['ticker']} {best.get('weekly_change_pct', 0):+.1f}% | "
            f"Worst: {worst['ticker']} {worst.get('weekly_change_pct', 0):+.1f}%"
        )

        # Top opportunities in this thesis
        top_opps = sorted(items, key=lambda x: x.get("opportunity_score", 0), reverse=True)[:3]
        top_opportunities = [
            {"ticker": t["ticker"], "score": t["opportunity_score"], "signal": t["signal"]}
            for t in top_opps
        ]

        health[key] = {
            "status": status,
            "signal": signal,
            "avg_weekly": round(avg_weekly, 2),
            "breadth": round(breadth, 2),
            "avg_score": round(avg_score, 1),
            "top_opportunities": top_opportunities,
        }

    return health


# ─── Macro Regime Analyzer ───────────────────────────────────────

def analyze_macro_regime(macro):
    """Determine the current macro economic regime from market data.
    Returns regime classification, signals, and thesis weight recommendations."""

    signals = []
    regime_scores = {
        "risk_on": 0,      # Growth/bull: overweight tech, ecosystems, picks & shovels
        "risk_off": 0,     # Defensive/bear: overweight healthcare, defense, utilities
        "inflationary": 0, # Rising prices: overweight commodities, energy, materials
        "deflationary": 0, # Falling prices: overweight bonds, quality growth
        "recession": 0,    # Economic contraction: cash, defensive, short duration
    }

    # ── Yield Curve Analysis ──
    us10y = macro.get("us10y", {}).get("value")
    us2y = macro.get("us2y", {}).get("value")
    if us10y and us2y:
        spread = us10y - us2y
        if spread < 0:
            signals.append({"indicator": "Yield Curve", "reading": f"{spread:+.2f}%", "interpretation": "INVERTED — recession signal active", "severity": "HIGH"})
            regime_scores["recession"] += 3
            regime_scores["risk_off"] += 2
        elif spread < 0.5:
            signals.append({"indicator": "Yield Curve", "reading": f"{spread:+.2f}%", "interpretation": "FLAT — late cycle, growth slowing", "severity": "MEDIUM"})
            regime_scores["recession"] += 1
            regime_scores["risk_off"] += 1
        elif spread > 1.5:
            signals.append({"indicator": "Yield Curve", "reading": f"{spread:+.2f}%", "interpretation": "STEEP — early cycle expansion, growth ahead", "severity": "LOW"})
            regime_scores["risk_on"] += 2
        else:
            signals.append({"indicator": "Yield Curve", "reading": f"{spread:+.2f}%", "interpretation": "Normal — mid-cycle", "severity": "LOW"})

    # ── VIX (Fear Gauge) ──
    vix = macro.get("vix", {}).get("value")
    if vix:
        if vix > 30:
            signals.append({"indicator": "VIX", "reading": f"{vix:.1f}", "interpretation": "EXTREME FEAR — panic selling, contrarian opportunity", "severity": "HIGH"})
            regime_scores["risk_off"] += 2
        elif vix > 20:
            signals.append({"indicator": "VIX", "reading": f"{vix:.1f}", "interpretation": "ELEVATED — uncertainty, hedging active", "severity": "MEDIUM"})
            regime_scores["risk_off"] += 1
        elif vix < 13:
            signals.append({"indicator": "VIX", "reading": f"{vix:.1f}", "interpretation": "COMPLACENT — low fear, potential for snap correction", "severity": "MEDIUM"})
            regime_scores["risk_on"] += 1
        else:
            signals.append({"indicator": "VIX", "reading": f"{vix:.1f}", "interpretation": "Normal range", "severity": "LOW"})

    # ── Dollar Strength ──
    dxy = macro.get("dxy", {})
    dxy_val = dxy.get("value")
    dxy_trend = dxy.get("monthly_pct")
    if dxy_val and dxy_trend is not None:
        if dxy_val > 105 and dxy_trend > 2:
            signals.append({"indicator": "US Dollar (DXY)", "reading": f"{dxy_val:.1f} ({dxy_trend:+.1f}% mo)", "interpretation": "STRONG & RISING — headwind for multinationals, commodities pressured", "severity": "MEDIUM"})
            regime_scores["deflationary"] += 1
        elif dxy_val < 100 and dxy_trend < -2:
            signals.append({"indicator": "US Dollar (DXY)", "reading": f"{dxy_val:.1f} ({dxy_trend:+.1f}% mo)", "interpretation": "WEAK & FALLING — tailwind for commodities, emerging markets, multinationals", "severity": "MEDIUM"})
            regime_scores["inflationary"] += 1
            regime_scores["risk_on"] += 1

    # ── Treasury Yields (Rate Environment) ──
    if us10y:
        us10y_trend = macro.get("us10y", {}).get("monthly_pct")
        if us10y > 4.5 and us10y_trend and us10y_trend > 0:
            signals.append({"indicator": "10Y Yield", "reading": f"{us10y:.2f}% ({us10y_trend:+.1f}% mo)", "interpretation": "RISING RATES — headwind for growth/tech, tailwind for financials", "severity": "HIGH"})
            regime_scores["risk_off"] += 1
            regime_scores["inflationary"] += 1
        elif us10y < 3.5 and us10y_trend and us10y_trend < 0:
            signals.append({"indicator": "10Y Yield", "reading": f"{us10y:.2f}% ({us10y_trend:+.1f}% mo)", "interpretation": "FALLING RATES — tailwind for growth/tech, QE expectations", "severity": "MEDIUM"})
            regime_scores["risk_on"] += 2

    # ── Credit Spreads (HYG vs LQD) ──
    hyg = macro.get("hyg", {})
    lqd = macro.get("lqd", {})
    if hyg.get("weekly_pct") is not None and lqd.get("weekly_pct") is not None:
        spread_move = (hyg.get("weekly_pct") or 0) - (lqd.get("weekly_pct") or 0)
        if spread_move < -2:
            signals.append({"indicator": "Credit Spreads", "reading": f"HY underperforming IG by {abs(spread_move):.1f}%", "interpretation": "WIDENING — risk appetite declining, credit stress", "severity": "HIGH"})
            regime_scores["recession"] += 2
            regime_scores["risk_off"] += 2
        elif spread_move > 1:
            signals.append({"indicator": "Credit Spreads", "reading": f"HY outperforming IG by {spread_move:.1f}%", "interpretation": "TIGHTENING — risk appetite expanding, credit confidence", "severity": "LOW"})
            regime_scores["risk_on"] += 1

    # ── Commodity Complex (Inflation Signal) ──
    oil = macro.get("oil_wti", {})
    copper_data = macro.get("copper", {})
    gold_data = macro.get("gold", {})

    commodity_up = 0
    if oil.get("monthly_pct") and oil["monthly_pct"] > 5: commodity_up += 1
    if copper_data.get("monthly_pct") and copper_data["monthly_pct"] > 5: commodity_up += 1
    if gold_data.get("monthly_pct") and gold_data["monthly_pct"] > 3: commodity_up += 1

    if commodity_up >= 2:
        signals.append({"indicator": "Commodity Complex", "reading": f"{commodity_up}/3 commodities rising", "interpretation": "INFLATIONARY — broad commodity strength, input costs rising", "severity": "MEDIUM"})
        regime_scores["inflationary"] += 2

    commodity_down = 0
    if oil.get("monthly_pct") and oil["monthly_pct"] < -5: commodity_down += 1
    if copper_data.get("monthly_pct") and copper_data["monthly_pct"] < -5: commodity_down += 1
    if commodity_down >= 2:
        signals.append({"indicator": "Commodity Complex", "reading": f"{commodity_down}/2 commodities falling", "interpretation": "DEFLATIONARY — demand destruction or oversupply", "severity": "MEDIUM"})
        regime_scores["deflationary"] += 2

    # ── Small Cap Health (Russell 2000) ──
    rut = macro.get("russell2000", {})
    sp500 = macro.get("sp500", {})
    if rut.get("monthly_pct") is not None and sp500.get("monthly_pct") is not None:
        small_vs_large = (rut.get("monthly_pct") or 0) - (sp500.get("monthly_pct") or 0)
        if small_vs_large > 3:
            signals.append({"indicator": "Small vs Large Cap", "reading": f"Russell outperforming S&P by {small_vs_large:.1f}%", "interpretation": "BROADENING — risk appetite expanding to smaller names, healthy bull", "severity": "LOW"})
            regime_scores["risk_on"] += 2
        elif small_vs_large < -3:
            signals.append({"indicator": "Small vs Large Cap", "reading": f"Russell underperforming S&P by {abs(small_vs_large):.1f}%", "interpretation": "NARROWING — flight to mega-cap safety, late cycle", "severity": "MEDIUM"})
            regime_scores["risk_off"] += 1
            regime_scores["recession"] += 1

    # ── Sector Rotation Analysis ──
    sector_performance = {}
    sector_keys = {
        "xlk": "Tech", "xle": "Energy", "xlf": "Financials", "xlv": "Healthcare",
        "xli": "Industrials", "xlu": "Utilities", "xlb": "Materials",
        "xlp": "Consumer Staples", "xly": "Consumer Disc"
    }
    for key, label in sector_keys.items():
        sec = macro.get(key, {})
        if sec.get("weekly_pct") is not None:
            sector_performance[label] = sec["weekly_pct"]

    if sector_performance:
        sorted_sectors = sorted(sector_performance.items(), key=lambda x: x[1], reverse=True)
        leading = [f"{s[0]} ({s[1]:+.1f}%)" for s in sorted_sectors[:3]]
        lagging = [f"{s[0]} ({s[1]:+.1f}%)" for s in sorted_sectors[-3:]]
        signals.append({
            "indicator": "Sector Rotation",
            "reading": f"Leading: {', '.join(leading)} | Lagging: {', '.join(lagging)}",
            "interpretation": "See thesis weight recommendations for positioning",
            "severity": "INFO"
        })

        # Sector rotation → regime signals
        defensive = sum(sector_performance.get(s, 0) for s in ["Utilities", "Consumer Staples", "Healthcare"])
        cyclical = sum(sector_performance.get(s, 0) for s in ["Tech", "Consumer Disc", "Industrials"])
        if defensive > cyclical + 3:
            regime_scores["risk_off"] += 2
            regime_scores["recession"] += 1
        elif cyclical > defensive + 3:
            regime_scores["risk_on"] += 2

    # ── Determine Dominant Regime ──
    max_regime = max(regime_scores, key=regime_scores.get)
    max_score = regime_scores[max_regime]
    total_score = sum(regime_scores.values()) or 1
    confidence = round(max_score / total_score * 100) if total_score > 0 else 0

    regime_labels = {
        "risk_on": "GROWTH / RISK-ON",
        "risk_off": "DEFENSIVE / RISK-OFF",
        "inflationary": "INFLATIONARY",
        "deflationary": "DEFLATIONARY / DISINFLATIONARY",
        "recession": "RECESSIONARY / LATE CYCLE",
    }

    # ── Thesis Weight Recommendations ──
    # Base weights: equal (each thesis starts at 1.0)
    thesis_weights = {
        "vertical_ecosystems": 1.0,
        "realworld_data": 1.0,
        "picks_and_shovels": 1.0,
        "digital_security": 1.0,
        "healthcare_ai": 1.0,
        "defense_aerospace": 1.0,
        "raw_materials": 1.0,
    }

    # Adjust weights based on regime
    if regime_scores["risk_on"] >= 3:
        thesis_weights["vertical_ecosystems"] += 0.4
        thesis_weights["picks_and_shovels"] += 0.3
        thesis_weights["realworld_data"] += 0.2
        thesis_weights["raw_materials"] += 0.1

    if regime_scores["risk_off"] >= 3:
        thesis_weights["healthcare_ai"] += 0.4
        thesis_weights["defense_aerospace"] += 0.3
        thesis_weights["digital_security"] += 0.2
        thesis_weights["vertical_ecosystems"] -= 0.2
        thesis_weights["picks_and_shovels"] -= 0.1

    if regime_scores["inflationary"] >= 3:
        thesis_weights["raw_materials"] += 0.5
        thesis_weights["realworld_data"] += 0.1
        thesis_weights["picks_and_shovels"] -= 0.2

    if regime_scores["deflationary"] >= 3:
        thesis_weights["picks_and_shovels"] += 0.3
        thesis_weights["healthcare_ai"] += 0.2
        thesis_weights["raw_materials"] -= 0.3

    if regime_scores["recession"] >= 3:
        thesis_weights["defense_aerospace"] += 0.4
        thesis_weights["healthcare_ai"] += 0.3
        thesis_weights["digital_security"] += 0.2
        thesis_weights["vertical_ecosystems"] -= 0.3
        thesis_weights["picks_and_shovels"] -= 0.2
        thesis_weights["raw_materials"] -= 0.2

    # Sector rotation adjustments
    if sector_performance:
        if sector_performance.get("Tech", 0) > 2:
            thesis_weights["picks_and_shovels"] += 0.2
            thesis_weights["vertical_ecosystems"] += 0.1
        if sector_performance.get("Energy", 0) > 2:
            thesis_weights["raw_materials"] += 0.2
        if sector_performance.get("Healthcare", 0) > 2:
            thesis_weights["healthcare_ai"] += 0.2
        if sector_performance.get("Industrials", 0) > 2:
            thesis_weights["realworld_data"] += 0.2
        if sector_performance.get("Materials", 0) > 2:
            thesis_weights["raw_materials"] += 0.2
        if sector_performance.get("Utilities", 0) > 2:
            thesis_weights["picks_and_shovels"] += 0.1  # Data center power demand

    # Normalize weights to recommendations
    weight_labels = {
        "vertical_ecosystems": "Vertical Ecosystems",
        "realworld_data": "Real-World Data Moats",
        "picks_and_shovels": "Picks & Shovels (AI Infra)",
        "digital_security": "Digital Security & Cyber",
        "healthcare_ai": "Healthcare AI & Pharma",
        "defense_aerospace": "Defense & Aerospace",
        "raw_materials": "Raw Materials & Commodities",
    }

    thesis_recs = []
    for key, weight in sorted(thesis_weights.items(), key=lambda x: x[1], reverse=True):
        if weight >= 1.3:
            stance = "OVERWEIGHT"
        elif weight >= 1.1:
            stance = "LEAN OVERWEIGHT"
        elif weight <= 0.7:
            stance = "UNDERWEIGHT"
        elif weight <= 0.9:
            stance = "LEAN UNDERWEIGHT"
        else:
            stance = "MARKET WEIGHT"

        thesis_recs.append({
            "thesis": weight_labels[key],
            "thesis_key": key,
            "stance": stance,
            "weight": round(weight, 2),
            "rationale": _get_thesis_rationale(key, regime_scores, sector_performance, macro),
        })

    return {
        "regime": regime_labels.get(max_regime, "UNKNOWN"),
        "regime_scores": regime_scores,
        "confidence_pct": confidence,
        "signals": signals,
        "sector_performance": sector_performance,
        "thesis_recommendations": thesis_recs,
        "yield_curve_spread": round(us10y - us2y, 2) if us10y and us2y else None,
    }


def _get_thesis_rationale(thesis_key, regime_scores, sector_perf, macro):
    """Generate a plain-English rationale for each thesis recommendation."""
    parts = []

    r = regime_scores
    sp = sector_perf or {}
    vix = macro.get("vix", {}).get("value")
    us10y = macro.get("us10y", {}).get("value")
    copper = macro.get("copper", {}).get("monthly_pct")
    oil = macro.get("oil_wti", {}).get("monthly_pct")

    if thesis_key == "vertical_ecosystems":
        if r["risk_on"] >= 3: parts.append("Growth regime favors multi-layer platform plays")
        if r["recession"] >= 3: parts.append("Recession risk — these have pricing power but face multiple compression")
        if sp.get("Tech", 0) > 2: parts.append("Tech sector leadership supports ecosystem valuations")

    elif thesis_key == "realworld_data":
        if r["risk_on"] >= 2: parts.append("Expanding economy = more data generation across industries")
        if sp.get("Industrials", 0) > 1: parts.append("Industrial strength drives data moat companies (Deere, CAT, HON)")
        if r["inflationary"] >= 2: parts.append("Data-moat companies have pricing power through inflation")

    elif thesis_key == "picks_and_shovels":
        if r["risk_on"] >= 2: parts.append("AI capex cycle accelerating — infrastructure demand strong")
        if us10y and us10y > 4.5: parts.append("High rates pressure growth multiples on chip stocks — selectivity needed")
        if sp.get("Utilities", 0) > 1: parts.append("Utilities strength = data center power demand story playing out")
        if sp.get("Tech", 0) > 2: parts.append("Tech momentum supports semiconductor spending")

    elif thesis_key == "digital_security":
        if r["risk_off"] >= 2: parts.append("Defensive tech — security spend is non-discretionary in downturns")
        if r["risk_on"] >= 2: parts.append("Expanding digital surface = more attack vectors = more spend")
        parts.append("Secular growth regardless of cycle — breaches don't stop in recessions")

    elif thesis_key == "healthcare_ai":
        if r["recession"] >= 2: parts.append("Healthcare is recession-resistant — GLP-1 demand is inelastic")
        if r["risk_off"] >= 2: parts.append("Defensive positioning favors pharma + medical devices")
        if sp.get("Healthcare", 0) > 1: parts.append("Sector rotation into healthcare confirms defensive positioning")

    elif thesis_key == "defense_aerospace":
        if r["recession"] >= 2: parts.append("Government spend is counter-cyclical — defense budgets don't shrink in recessions")
        if r["risk_off"] >= 2: parts.append("Geopolitical risk premium supports defense names")
        parts.append("Multi-year order backlogs provide earnings visibility regardless of macro")

    elif thesis_key == "raw_materials":
        if r["inflationary"] >= 2: parts.append("Inflationary regime favors hard assets — copper, uranium, lithium")
        if copper and copper > 3: parts.append(f"Copper up {copper:+.1f}% mo — infrastructure + electrification demand signal")
        if oil and oil > 5: parts.append(f"Oil up {oil:+.1f}% mo — energy tightness supports commodity complex")
        if r["deflationary"] >= 2: parts.append("Deflation risk — demand destruction pressures commodity prices")
        if r["recession"] >= 3: parts.append("Recession = demand drop — underweight until cycle turns")

    return ". ".join(parts) if parts else "Maintain baseline allocation — no strong directional signal"


# ─── Dynamic Thesis Generator (AI-Recommended) ──────────────────

def generate_dynamic_theses(macro, macro_regime):
    """Use Claude to recommend NEW investment theses based on current macro/micro conditions.
    These go beyond the 7 core Owens Doctrine pillars."""
    api_key = load_api_key()
    if not api_key or not anthropic:
        print("  SKIP: No API key — dynamic theses unavailable")
        return []

    print("Generating AI-recommended theses...")

    # Build macro context
    macro_lines = []
    for key in ["sp500", "nasdaq", "vix", "us10y", "us2y", "us30y", "dxy",
                 "oil_wti", "gold", "copper", "russell2000", "tip", "hyg", "lqd"]:
        m = macro.get(key, {})
        if m.get("value"):
            macro_lines.append(f"{m['label']}: {m['value']:.2f} (day: {m.get('change_pct', 0):+.2f}%, week: {m.get('weekly_pct', 0):+.2f}%, month: {m.get('monthly_pct', 0):+.2f}%)")

    sector_lines = []
    for key in ["xlk", "xle", "xlf", "xlv", "xli", "xlu", "xlb", "xlp", "xly"]:
        m = macro.get(key, {})
        if m.get("value"):
            sector_lines.append(f"{m['label']}: week {m.get('weekly_pct', 0):+.2f}%, month {m.get('monthly_pct', 0):+.2f}%")

    regime_info = ""
    if macro_regime:
        regime_info = f"Current regime: {macro_regime['regime']} ({macro_regime['confidence_pct']}% confidence)"
        if macro_regime.get("yield_curve_spread") is not None:
            regime_info += f"\nYield curve 10Y-2Y spread: {macro_regime['yield_curve_spread']}%"

    existing_theses = ", ".join([t["label"] for t in WATCHLIST.values()])

    prompt = f"""You are a macro strategist analyzing current economic conditions to recommend investment themes.

The investor already holds 7 thesis pillars: {existing_theses}

Your job: recommend 3-5 NEW theses the investor should consider RIGHT NOW based on the macro/micro environment. These should be theses NOT covered by the existing 7 — areas where current conditions create specific, actionable opportunities.

Today: {datetime.now().strftime('%Y-%m-%d')}

MACRO REGIME:
{regime_info}

MACRO INDICATORS:
{chr(10).join(macro_lines)}

SECTOR ROTATION (weekly + monthly performance):
{chr(10).join(sector_lines)}

Think about:
- What economic forces are creating NEW opportunities (rate cuts, reshoring, AI regulation, energy transition, geopolitical shifts)?
- What sectors/themes are being MISPRICED by the market right now?
- What macro conditions favor specific industries that aren't in the existing 7 theses?
- What is the market consensus WRONG about?

Return JSON array. For each recommended thesis:
{{
  "thesis_name": "Short, punchy name (3-5 words)",
  "thesis_key": "snake_case_key",
  "conviction": "HIGH / MEDIUM / LOW",
  "macro_driver": "What specific macro/micro condition creates this opportunity",
  "why_now": "Why is this the right time — what changed in the last 30-90 days?",
  "sector_alignment": "Which sector ETFs confirm this thesis and current performance",
  "risks": "What could invalidate this thesis",
  "time_horizon": "3-6 months / 6-12 months / 1-3 years",
  "recommended_tickers": [
    {{
      "symbol": "TICKER",
      "name": "Company Name",
      "why": "One sentence — why this specific company for this thesis"
    }}
  ],
  "connection_to_existing": "How this thesis complements or hedges the existing 7 pillars"
}}

Be bold. Don't recommend things already covered by the 7 pillars. Think about what the market is missing. Max 5 theses, min 3. Each thesis must have 2-5 tickers."""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        theses = json.loads(text.strip())
        if isinstance(theses, dict) and "theses" in theses:
            theses = theses["theses"]
        if not isinstance(theses, list):
            theses = [theses]

        print(f"  Dynamic theses generated: {len(theses)}")
        for t in theses:
            print(f"    [{t.get('conviction', '?')}] {t.get('thesis_name', '?')} — {len(t.get('recommended_tickers', []))} tickers")
        return theses

    except json.JSONDecodeError as e:
        print(f"  WARN: Failed to parse dynamic theses JSON: {e}")
        return []
    except Exception as e:
        print(f"  WARN: Dynamic thesis generation failed: {e}")
        return []


# ─── Alert Engine ────────────────────────────────────────────────

def generate_alerts(macro, watchlist_data, thesis_health):
    """Generate event-driven alerts."""
    alerts = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    vix = macro.get("vix", {})
    if vix.get("value") and vix["value"] > 25:
        level = "CRITICAL" if vix["value"] > 30 else "WARNING"
        alerts.append({
            "type": level,
            "message": f"VIX at {vix['value']:.1f} — elevated fear. Opportunity scanner active: thesis-supported names on sale.",
            "timestamp": now,
        })

    oil = macro.get("oil_wti", {})
    if oil.get("weekly_pct") and abs(oil["weekly_pct"]) > 10:
        direction = "surged" if oil["weekly_pct"] > 0 else "plunged"
        alerts.append({"type": "WARNING", "message": f"Oil {direction} {oil['weekly_pct']:+.1f}% this week.", "timestamp": now})

    copper = macro.get("copper", {})
    if copper.get("weekly_pct") and abs(copper["weekly_pct"]) > 5:
        direction = "surging" if copper["weekly_pct"] > 0 else "dropping"
        alerts.append({"type": "INFO", "message": f"Copper {direction} {copper['weekly_pct']:+.1f}% — infrastructure thesis signal.", "timestamp": now})

    for key, h in thesis_health.items():
        if h.get("status") == "WEAKENING":
            label = WATCHLIST.get(key, {}).get("label", key)
            alerts.append({"type": "WARNING", "message": f"Thesis WEAKENING: {label} — avg {h.get('avg_weekly', 0):+.1f}% (5d). Review positions.", "timestamp": now})

    # Strong buy alerts
    strong_buys = [w for w in watchlist_data if w.get("signal") == "STRONG BUY"]
    for sb in strong_buys:
        rsi = sb.get("technicals", {}).get("rsi", "?")
        dist = sb.get("technicals", {}).get("dist_from_52w_high_pct", "?")
        alerts.append({
            "type": "OPPORTUNITY",
            "message": f"STRONG BUY: {sb['ticker']} — Score {sb['opportunity_score']}/100 | RSI {rsi} | {dist}% from 52w high | {sb['thesis']}",
            "timestamp": now,
        })

    # Big movers
    for item in watchlist_data:
        if item.get("weekly_change_pct") and abs(item["weekly_change_pct"]) > 10:
            direction = "up" if item["weekly_change_pct"] > 0 else "down"
            alerts.append({"type": "INFO", "message": f"{item['ticker']} {direction} {item['weekly_change_pct']:+.1f}% this week ({item['thesis']}).", "timestamp": now})

    # Projection drift detection
    history = load_projection_history()
    if history and history.get("snapshots"):
        # Build current signal lookup
        current_signals = {}
        current_prices = {}
        for item in watchlist_data:
            current_signals[item["ticker"]] = item.get("signal", "")
            if item.get("price"):
                current_prices[item["ticker"]] = item["price"]

        # Check most recent snapshot for drift
        for snapshot in history["snapshots"][-5:]:
            snap_date = snapshot.get("date", "?")
            for proj in snapshot.get("projections", []):
                ticker = proj.get("ticker")
                past_action = (proj.get("action") or "").upper()
                current_signal = current_signals.get(ticker, "").upper()

                if not ticker or not past_action or not current_signal:
                    continue

                # Signal flip detection
                bullish_past = past_action in ("STRONG BUY", "BUY", "ACCUMULATE")
                bearish_now = current_signal in ("TRIM", "SELL")
                if bullish_past and bearish_now:
                    alerts.append({
                        "type": "WARNING",
                        "message": f"PROJECTION DRIFT: {ticker} was '{past_action}' on {snap_date} but now signals '{current_signal}'. Review thesis.",
                        "timestamp": now,
                    })

                # Target price drift (>20% wrong direction)
                target_str = proj.get("target_price", "")
                entry_price = proj.get("entry_price")
                current_price = current_prices.get(ticker)
                if target_str and entry_price and current_price:
                    match = re.search(r'\$?([\d,]+\.?\d*)', str(target_str))
                    if match:
                        try:
                            target = float(match.group(1).replace(",", ""))
                            # If target was above entry (bullish) but price dropped >20% below entry
                            if target > entry_price:
                                drift_pct = ((current_price - entry_price) / entry_price) * 100
                                if drift_pct < -20:
                                    alerts.append({
                                        "type": "CRITICAL",
                                        "message": f"TARGET DRIFT: {ticker} projected ${target:.0f} from ${entry_price:.2f} but now ${current_price:.2f} ({drift_pct:.1f}%). Major miss.",
                                        "timestamp": now,
                                    })
                        except ValueError:
                            pass

    if not alerts:
        alerts.append({"type": "INFO", "message": "No alert triggers fired. All systems nominal.", "timestamp": now})

    return alerts


# ─── Claude AI Analysis ─────────────────────────────────────────

def run_ai_analysis(macro, watchlist_data, thesis_health, alerts, macro_regime=None):
    """Call Claude to generate natural language investment analysis."""
    api_key = load_api_key()
    if not api_key or not anthropic:
        print("  SKIP: No API key or anthropic SDK — returning quantitative analysis only")
        return None

    print("Running Claude AI analysis...")

    # Build top opportunities
    top_opps = sorted(
        [w for w in watchlist_data if w.get("opportunity_score", 0) >= 55],
        key=lambda x: x["opportunity_score"],
        reverse=True
    )[:10]

    # Build macro summary
    macro_summary = []
    for key in ["sp500", "nasdaq", "vix", "us10y", "dxy", "oil_wti", "gold", "copper"]:
        m = macro.get(key, {})
        if m.get("value"):
            macro_summary.append(f"{m['label']}: {m['value']:.2f} (day: {m.get('change_pct', 0):+.2f}%, week: {m.get('weekly_pct', 0):+.2f}%, month: {m.get('monthly_pct', 0):+.2f}%)")

    # Build thesis summary
    thesis_summary = []
    for key, h in thesis_health.items():
        label = WATCHLIST.get(key, {}).get("label", key)
        thesis_summary.append(f"{label}: {h['status']} — {h['signal']}")

    # Build opportunity details
    opp_details = []
    for o in top_opps:
        t = o.get("technicals", {})
        f = o.get("fundamentals", {})
        opp_details.append(
            f"{o['ticker']} ({o['thesis']}) — Score: {o['opportunity_score']}/100 | "
            f"${o['price']} | Day: {o.get('daily_change_pct', 0):+.2f}% | Week: {o.get('weekly_change_pct', 0):+.2f}% | "
            f"RSI: {t.get('rsi', '?')} | {t.get('dist_from_52w_high_pct', '?')}% from 52w high | "
            f"Month: {t.get('monthly_change_pct', '?')}% | 3M: {t.get('three_month_change_pct', '?')}% | "
            f"Above 50d SMA: {t.get('above_sma50', '?')} | Vol ratio: {t.get('volume_ratio_5d_vs_20d', '?')} | "
            f"Market Cap: {f.get('market_cap_fmt', '?')} | P/E: {f.get('pe_ratio', '?')} | Rev Growth: {f.get('revenue_growth_pct', '?')}%"
        )

    # Build regime summary for prompt
    regime_summary = []
    if macro_regime:
        regime_summary.append(f"CURRENT REGIME: {macro_regime['regime']} (confidence: {macro_regime['confidence_pct']}%)")
        regime_summary.append(f"Yield Curve Spread: {macro_regime.get('yield_curve_spread', 'N/A')}")
        for sig in macro_regime.get("signals", []):
            if sig.get("severity") in ("HIGH", "MEDIUM"):
                regime_summary.append(f"  {sig['indicator']}: {sig['reading']} — {sig['interpretation']}")
        regime_summary.append("")
        regime_summary.append("THESIS WEIGHT RECOMMENDATIONS (from macro regime):")
        for rec in macro_regime.get("thesis_recommendations", []):
            regime_summary.append(f"  {rec['stance']}: {rec['thesis']} — {rec['rationale']}")

    prompt = f"""You are an investment analyst for a systems-thinking investor (The Owens Doctrine).
The investor focuses on 7 thesis pillars:
1. Vertical Ecosystems — companies controlling multiple data-generating layers (Tesla, Palantir, Microsoft archetype)
2. Real-World Data Moats — companies physically gathering data AI models need (Deere, Visa, Salesforce)
3. Picks & Shovels — chips, power, cooling, connectivity for AI scaling (NVIDIA, AMD, Vertiv)
4. Digital Security & Cyber — companies protecting the expanding digital surface (CrowdStrike, Palo Alto, Zscaler)
5. Healthcare AI & Pharma — AI-driven drug discovery + medical devices (Lilly, Vertex, Dexcom, Veeva)
6. Defense & Aerospace — next-gen defense systems, AI-integrated platforms (Lockheed, Raytheon, L3Harris)
7. Raw Materials & Commodities — copper, lithium, rare earths, uranium, water feeding scaling industries

Today's date: {datetime.now().strftime('%Y-%m-%d')}

MACRO REGIME ANALYSIS:
{chr(10).join(regime_summary)}

MACRO INDICATORS:
{chr(10).join(macro_summary)}

THESIS HEALTH:
{chr(10).join(thesis_summary)}

TOP OPPORTUNITIES (by quantitative score):
{chr(10).join(opp_details)}

ACTIVE ALERTS:
{chr(10).join(a['message'] for a in alerts)}

Generate a concise investment intelligence analysis in JSON format with these exact keys:
{{
  "market_narrative": "2-3 sentence summary of what the market is telling us today and why",
  "macro_assessment": "2-3 sentences on macro conditions and what they mean for the 7 theses",
  "top_recommendations": [
    {{
      "ticker": "SYMBOL",
      "action": "STRONG BUY / BUY / ACCUMULATE / HOLD / TRIM",
      "thesis_alignment": "which thesis and why this is a systems play",
      "why_now": "specific technical + macro reasons this is the right entry point",
      "risk": "what could go wrong",
      "target_horizon": "short-term trade or long-term accumulate",
      "hold_duration": "e.g. '3-6 months', '1-2 weeks', '12+ months'",
      "target_price": "specific dollar target based on technicals + fundamentals",
      "sell_trigger": "specific condition that means it's time to sell — in plain English",
      "projected_sell_date": "approximate date range to consider selling, e.g. 'Q3 2026'",
      "confidence": "HIGH / MEDIUM / LOW — how confident in this projection"
    }}
  ],
  "thesis_outlook": {{
    "vertical_ecosystems": "1-2 sentence outlook",
    "realworld_data": "1-2 sentence outlook",
    "picks_and_shovels": "1-2 sentence outlook",
    "digital_security": "1-2 sentence outlook",
    "healthcare_ai": "1-2 sentence outlook",
    "defense_aerospace": "1-2 sentence outlook",
    "raw_materials": "1-2 sentence outlook"
  }},
  "key_risk": "the single biggest risk across all positions right now",
  "action_summary": "1-2 sentence bottom line — what should the investor DO this week"
}}

Give max 5 recommendations. Focus on the highest conviction ideas. Be specific about entry points and reasoning. This investor thinks in systems — connect the dots between macro, geopolitics, and company-level data flywheels. Be direct, no hedging language. For each recommendation, give a SPECIFIC hold duration and target sell price. Be concrete — 'hold for 3-6 months targeting $185' not 'medium-term hold'. Include a clear sell trigger — what would make you exit this position."""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse JSON from response
        text = response.content[0].text
        # Try to extract JSON from the response
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        analysis = json.loads(text.strip())
        print(f"  AI analysis complete — {len(analysis.get('top_recommendations', []))} recommendations")
        return analysis

    except json.JSONDecodeError as e:
        print(f"  WARN: Failed to parse AI response as JSON: {e}")
        # Return raw text as fallback
        return {"market_narrative": text[:500], "parse_error": True}
    except Exception as e:
        print(f"  WARN: AI analysis failed: {e}")
        return None


# ─── Stock Profiles + Sentiment Intelligence ────────────────────

def run_stock_profiles(top_stocks, macro, thesis_health):
    """Generate detailed stock profiles with sentiment intelligence via Claude."""
    api_key = load_api_key()
    if not api_key or not anthropic:
        print("  SKIP: No API key — stock profiles unavailable")
        return {}

    print("Generating stock profiles + sentiment intelligence...")

    # Build detailed stock summaries for the prompt
    stock_summaries = []
    for s in top_stocks:
        f = s.get("fundamentals", {})
        t = s.get("technicals", {})
        stock_summaries.append(
            f"{s['ticker']} — {s['description']} | Thesis: {s['thesis']}\n"
            f"  Price: ${s['price']} | Score: {s['opportunity_score']}/100 | Signal: {s['signal']}\n"
            f"  RSI: {t.get('rsi')} | From 52w High: {t.get('dist_from_52w_high_pct')}% | "
            f"Week: {s.get('weekly_change_pct')}% | Month: {t.get('monthly_change_pct')}%\n"
            f"  Market Cap: {f.get('market_cap_fmt', '?')} | P/E: {f.get('pe_ratio', '?')} | "
            f"Fwd P/E: {f.get('forward_pe', '?')} | Rev Growth: {f.get('revenue_growth_pct', '?')}% | "
            f"Profit Margin: {f.get('profit_margin_pct', '?')}%\n"
            f"  Sector: {f.get('sector', '?')} | Industry: {f.get('industry', '?')} | "
            f"Employees: {f.get('employees', '?')}"
        )

    prompt = f"""You are a financial intelligence analyst writing stock profiles for a smart retail investor.
Write in PLAIN ENGLISH — like a Goldman Sachs analyst explaining to a sharp friend. No jargon without explanation.

Think about VIRAL product momentum. Example: Anthropic's Claude — people are going crazy seeing AI coding build entire apps. THAT is the social signal preceding revenue growth. Find that signal for each stock.

Today: {datetime.now().strftime('%Y-%m-%d')}

STOCKS:
{chr(10).join(stock_summaries)}

Return JSON keyed by ticker. For EACH stock:
{{
  "TICKER": {{
    "plain_english": "2 sentences: What does this company DO? Explain for your neighbor.",
    "why_it_matters": "1 sentence: Why important in AI/energy/tech revolution?",
    "key_products": [{{"name": "Name", "description": "Plain English", "momentum": "HOT/GROWING/STABLE/COOLING", "buzz": "Why care"}}],
    "social_sentiment": {{
      "buzz_level": "VIRAL/HIGH/MEDIUM/LOW",
      "whats_buzzing": "What specific thing are people discussing on Reddit/Twitter/YouTube?",
      "consumer_love": "What product generates word-of-mouth?",
      "red_flags": "Negative sentiment or concerns?"
    }},
    "growth_engine": {{
      "hottest_product": "ONE product with most momentum",
      "adoption_signal": "Real-world evidence you can see",
      "scale_potential": "What could 10x and why",
      "competitive_edge": "Why can't competitors copy them?"
    }},
    "the_opportunity": {{
      "why_this_price": "Why is current price attractive? Plain English.",
      "what_wall_street_misses": "What is market not pricing in?",
      "catalysts": ["Upcoming events that could move stock"],
      "biggest_risk": "ONE thing that could go wrong"
    }},
    "bottom_line": "One punchy sentence: should I buy? Why?"
  }}
}}

Be SPECIFIC about social sentiment — reference actual trends. Max 3 key_products per stock. Max 2 catalysts. Keep descriptions concise."""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        profiles = json.loads(text.strip())
        print(f"  Stock profiles complete — {len(profiles)} tickers profiled")
        return profiles

    except json.JSONDecodeError as e:
        print(f"  WARN: Failed to parse stock profiles JSON: {e}")
        return {}
    except Exception as e:
        print(f"  WARN: Stock profiles failed: {e}")
        return {}


# ─── Projection History & Accuracy ─────────────────────────────

PROJECTION_HISTORY_FILE = DASHBOARD_DIR / "projection_history.json"


def load_projection_history():
    """Load projection history from disk, return empty structure if missing."""
    if PROJECTION_HISTORY_FILE.exists():
        try:
            return json.loads(PROJECTION_HISTORY_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            print("  WARN: Could not read projection_history.json, starting fresh")
    return {"snapshots": []}


def update_projection_history(ai_analysis, watchlist):
    """Append current projections to history file, keep max 90 days."""
    print("Updating projection history...")
    history = load_projection_history()

    # Build current price lookup
    price_lookup = {}
    for w in watchlist:
        if w.get("price"):
            price_lookup[w["ticker"]] = w["price"]

    # Build projection snapshot from AI recommendations
    projections = []
    for rec in ai_analysis.get("top_recommendations", []):
        projections.append({
            "ticker": rec.get("ticker"),
            "action": rec.get("action"),
            "target_price": rec.get("target_price"),
            "sell_trigger": rec.get("sell_trigger"),
            "hold_duration": rec.get("hold_duration"),
            "projected_sell_date": rec.get("projected_sell_date"),
            "confidence": rec.get("confidence"),
            "entry_price": price_lookup.get(rec.get("ticker")),
        })

    snapshot = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "projections": projections,
    }

    history["snapshots"].append(snapshot)

    # Trim to 90 days
    cutoff = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    history["snapshots"] = [s for s in history["snapshots"] if s["date"] >= cutoff]

    # Write back
    os.makedirs(DASHBOARD_DIR, exist_ok=True)
    with open(PROJECTION_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)
    print(f"  Projection history: {len(history['snapshots'])} snapshots saved")


def check_projection_accuracy(history, watchlist):
    """Compare past projections to current prices, calculate accuracy."""
    if not history or not history.get("snapshots"):
        return None

    # Current price lookup
    price_lookup = {}
    for w in watchlist:
        if w.get("price"):
            price_lookup[w["ticker"]] = w["price"]

    total = 0
    correct = 0
    notable_calls = []

    for snapshot in history["snapshots"]:
        snap_date = snapshot.get("date", "?")
        for proj in snapshot.get("projections", []):
            ticker = proj.get("ticker")
            entry_price = proj.get("entry_price")
            current_price = price_lookup.get(ticker)
            action = proj.get("action", "")

            if not entry_price or not current_price or not ticker:
                continue

            total += 1
            price_change_pct = ((current_price - entry_price) / entry_price) * 100
            bullish = action.upper() in ("STRONG BUY", "BUY", "ACCUMULATE")
            bearish = action.upper() in ("TRIM", "SELL")

            direction_correct = False
            if bullish and price_change_pct > 0:
                direction_correct = True
            elif bearish and price_change_pct < 0:
                direction_correct = True

            if bullish or bearish:
                if direction_correct:
                    correct += 1

                # Track notable calls (big moves)
                if abs(price_change_pct) > 5:
                    notable_calls.append({
                        "ticker": ticker,
                        "action": action,
                        "date": snap_date,
                        "entry_price": entry_price,
                        "current_price": current_price,
                        "change_pct": round(price_change_pct, 1),
                        "correct": direction_correct,
                    })

    accuracy_pct = round((correct / total) * 100, 1) if total > 0 else 0

    # Sort notable calls by magnitude
    notable_calls.sort(key=lambda x: abs(x["change_pct"]), reverse=True)

    return {
        "total_projections": total,
        "correct_direction": correct,
        "accuracy_pct": accuracy_pct,
        "notable_calls": notable_calls[:10],
    }


def fetch_earnings_calendar(watchlist):
    """Check upcoming earnings dates for watchlist stocks."""
    print("Checking earnings calendar...")
    earnings = []
    today = datetime.now().date()
    cutoff = today + timedelta(days=30)

    # Collect all tickers
    tickers = set()
    for w in watchlist:
        if w.get("ticker"):
            tickers.add(w["ticker"])

    for symbol in sorted(tickers):
        try:
            ticker = yf.Ticker(symbol)
            cal = ticker.calendar
            if cal is None:
                continue

            # yfinance calendar can be a dict or DataFrame
            earnings_date = None
            if isinstance(cal, dict):
                ed = cal.get("Earnings Date")
                if ed:
                    if isinstance(ed, list) and len(ed) > 0:
                        earnings_date = ed[0]
                    else:
                        earnings_date = ed
            elif hasattr(cal, 'columns'):
                # DataFrame format
                if "Earnings Date" in cal.columns:
                    vals = cal["Earnings Date"].tolist()
                    if vals:
                        earnings_date = vals[0]
                elif len(cal.columns) > 0:
                    # Sometimes it's a single-column DataFrame
                    try:
                        vals = cal.iloc[0].tolist()
                        if vals:
                            earnings_date = vals[0]
                    except Exception:
                        pass

            if earnings_date is None:
                continue

            # Parse the date
            if hasattr(earnings_date, 'date'):
                ed = earnings_date.date()
            elif isinstance(earnings_date, str):
                ed = datetime.strptime(earnings_date[:10], "%Y-%m-%d").date()
            else:
                continue

            if today <= ed <= cutoff:
                days_until = (ed - today).days
                earnings.append({
                    "ticker": symbol,
                    "earnings_date": ed.strftime("%Y-%m-%d"),
                    "days_until": days_until,
                })
        except Exception:
            continue

    earnings.sort(key=lambda x: x["earnings_date"])
    print(f"  Found {len(earnings)} stocks with earnings in next 30 days")
    return earnings


def check_price_alerts(history, watchlist):
    """Generate alerts when stocks approach or hit projection targets."""
    if not history or not history.get("snapshots"):
        return []

    # Current price and signal lookup
    price_lookup = {}
    signal_lookup = {}
    technicals_lookup = {}
    for w in watchlist:
        if w.get("ticker"):
            if w.get("price"):
                price_lookup[w["ticker"]] = w["price"]
            signal_lookup[w["ticker"]] = w.get("signal", "")
            technicals_lookup[w["ticker"]] = w.get("technicals", {})

    alerts = []
    seen = set()  # avoid duplicate alerts per ticker

    for snapshot in history["snapshots"]:
        for proj in snapshot.get("projections", []):
            ticker = proj.get("ticker")
            if not ticker or ticker in seen:
                continue

            current_price = price_lookup.get(ticker)
            entry_price = proj.get("entry_price")
            target_price_str = proj.get("target_price", "")
            sell_trigger = proj.get("sell_trigger", "")

            if not current_price:
                continue

            # Parse target price (extract first dollar amount from string)
            target_price = None
            if target_price_str:
                match = re.search(r'\$?([\d,]+\.?\d*)', str(target_price_str))
                if match:
                    try:
                        target_price = float(match.group(1).replace(",", ""))
                    except ValueError:
                        pass

            if target_price and target_price > 0:
                # Check if target hit
                if current_price >= target_price:
                    alerts.append({
                        "ticker": ticker,
                        "alert_type": "TARGET_HIT",
                        "message": f"{ticker} hit target ${target_price:.2f} — current ${current_price:.2f}. REVIEW POSITION.",
                        "current_price": current_price,
                        "target_price": target_price,
                    })
                    seen.add(ticker)
                    continue

                # Check if approaching target (within 5%)
                distance_pct = ((target_price - current_price) / target_price) * 100
                if 0 < distance_pct <= 5:
                    alerts.append({
                        "ticker": ticker,
                        "alert_type": "APPROACHING",
                        "message": f"{ticker} approaching target ${target_price:.2f} — current ${current_price:.2f} ({distance_pct:.1f}% away).",
                        "current_price": current_price,
                        "target_price": target_price,
                    })
                    seen.add(ticker)
                    continue

            # Stop loss check (>10% below entry)
            if entry_price and entry_price > 0:
                loss_pct = ((current_price - entry_price) / entry_price) * 100
                if loss_pct < -10:
                    alerts.append({
                        "ticker": ticker,
                        "alert_type": "STOP_LOSS",
                        "message": f"{ticker} down {loss_pct:.1f}% from entry ${entry_price:.2f} — current ${current_price:.2f}. STOP LOSS WARNING.",
                        "current_price": current_price,
                        "target_price": target_price,
                    })
                    seen.add(ticker)
                    continue

            # Simple sell trigger keyword matching
            if sell_trigger and ticker not in seen:
                trigger_lower = sell_trigger.lower()
                rsi = technicals_lookup.get(ticker, {}).get("rsi")
                weekly_chg = None
                for w in watchlist:
                    if w["ticker"] == ticker:
                        weekly_chg = w.get("weekly_change_pct")
                        break

                triggered = False
                if "rsi" in trigger_lower and "above 70" in trigger_lower and rsi and rsi > 70:
                    triggered = True
                if "rsi" in trigger_lower and "above 80" in trigger_lower and rsi and rsi > 80:
                    triggered = True
                if "drops below" in trigger_lower and "sma" in trigger_lower:
                    above_50 = technicals_lookup.get(ticker, {}).get("above_sma50")
                    if above_50 is False:
                        triggered = True
                if "decline" in trigger_lower or "drops" in trigger_lower:
                    if weekly_chg and weekly_chg < -10:
                        triggered = True

                if triggered:
                    alerts.append({
                        "ticker": ticker,
                        "alert_type": "SELL_TRIGGER",
                        "message": f"{ticker} sell trigger may be materializing: '{sell_trigger}'",
                        "current_price": current_price,
                        "target_price": target_price,
                    })
                    seen.add(ticker)

    print(f"  Price alerts: {len(alerts)} generated")
    return alerts


# ─── Notification Engine ──────────────────────────────────────

def fire_notifications(watchlist, ai_analysis, price_alerts, alerts, market_status):
    """Send macOS notifications + iMessage for actionable signals."""
    if not HAS_ALERTS:
        print("  Notifications: DISABLED (s6_alert not available)")
        return

    print("\nFiring notifications...")
    fired = 0

    # 1. PRICE TARGET ALERTS — these are the most actionable
    for pa in (price_alerts or []):
        if pa["alert_type"] == "TARGET_HIT":
            alert(HIGH, f"TARGET HIT: {pa['ticker']}",
                  f"{pa['message']}\nReview your position — target price reached.",
                  send_text=True)
            fired += 1
        elif pa["alert_type"] == "STOP_LOSS":
            alert(HIGH, f"STOP LOSS: {pa['ticker']}",
                  pa["message"], send_text=True)
            fired += 1
        elif pa["alert_type"] == "APPROACHING":
            alert(MEDIUM, f"Approaching Target: {pa['ticker']}",
                  pa["message"], send_text=False)
            fired += 1
        elif pa["alert_type"] == "SELL_TRIGGER":
            alert(HIGH, f"SELL TRIGGER: {pa['ticker']}",
                  pa["message"], send_text=True)
            fired += 1

    # 2. NEW STRONG BUY signals (score >= 75)
    strong_buys = [w for w in watchlist if w.get("signal") == "STRONG BUY"]
    if strong_buys:
        tickers = ", ".join(f"{w['ticker']} (${w['price']:.0f})" for w in strong_buys)
        alert(MEDIUM, f"{len(strong_buys)} STRONG BUY Signals",
              f"Today's strong buys: {tickers}",
              send_text=False)
        fired += 1

    # 3. MARKET REGIME CHANGE — fear spike or major shift
    if market_status == "FEAR":
        alert(HIGH, "MARKET FEAR — VIX Elevated",
              "VIX above 30. Market is in fear mode. Review thesis-aligned names for buying opportunity.",
              send_text=True)
        fired += 1

    # 4. SIGNAL CHANGES from projection drift (BUY → SELL)
    drift_alerts = [a for a in (alerts or [])
                    if "PROJECTION DRIFT" in a.get("message", "").upper()
                    or "projection drift" in a.get("message", "").lower()]
    for da in drift_alerts:
        alert(HIGH, "Projection Drift Detected",
              da["message"], send_text=True)
        fired += 1

    # 5. AI ACTION SUMMARY — lightweight daily notification
    if ai_analysis and ai_analysis.get("action_summary"):
        alert(INFO, "Invest-Intel Daily Brief",
              ai_analysis["action_summary"][:200],
              send_text=False)
        fired += 1

    print(f"  Notifications fired: {fired}")


# ─── Main ────────────────────────────────────────────────────────

def run():
    """Main execution."""
    print("=" * 60)
    print(f"INVEST-INTEL UPDATER v3 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Fetch macro
    macro = fetch_macro()

    # Analyze every watchlist ticker
    print("\nAnalyzing watchlist (technicals + scoring)...")
    watchlist = []
    for thesis_key, thesis in WATCHLIST.items():
        for ticker, description in thesis["tickers"].items():
            result = analyze_ticker(ticker, description, thesis_key, thesis["label"])
            watchlist.append(result)
            if result["price"]:
                print(f"  {ticker}: ${result['price']:.2f} | RSI {result['technicals'].get('rsi', '?')} | Score {result['opportunity_score']}/100 [{result['signal']}]")
            else:
                print(f"  {ticker}: FAILED")

    # Fetch fundamentals for top-scored stocks
    print("\nFetching fundamentals...")
    top_scored = sorted(
        [w for w in watchlist if w.get("opportunity_score", 0) >= 50],
        key=lambda x: x["opportunity_score"],
        reverse=True
    )
    for item in top_scored:
        item["fundamentals"] = fetch_fundamentals(item["ticker"])
        mc = item["fundamentals"].get("market_cap_fmt")
        if mc:
            print(f"  {item['ticker']}: {mc} | P/E {item['fundamentals'].get('pe_ratio', '?')} | Rev Growth {item['fundamentals'].get('revenue_growth_pct', '?')}%")

    # Thesis health
    thesis_health = assess_thesis_health(watchlist)

    # Macro regime analysis
    print("\nAnalyzing macro regime...")
    macro_regime = analyze_macro_regime(macro)
    print(f"  Regime: {macro_regime['regime']} (confidence: {macro_regime['confidence_pct']}%)")
    print(f"  Signals: {len(macro_regime['signals'])} indicators analyzed")
    for rec in macro_regime.get("thesis_recommendations", []):
        if rec["stance"] != "MARKET WEIGHT":
            print(f"  {rec['stance']}: {rec['thesis']}")

    # Alerts
    alerts = generate_alerts(macro, watchlist, thesis_health)

    # AI analysis (now includes macro regime)
    ai_analysis = run_ai_analysis(macro, watchlist, thesis_health, alerts, macro_regime)

    # Dynamic AI-recommended theses
    dynamic_theses = generate_dynamic_theses(macro, macro_regime)

    # ── Ingest dynamic thesis tickers into watchlist ──
    # These get the same technical analysis + scoring as core tickers
    existing_tickers = {w["ticker"] for w in watchlist}
    dynamic_added = 0
    if dynamic_theses:
        print("\nAnalyzing dynamic thesis tickers...")
        for dt in dynamic_theses:
            thesis_key = dt.get("thesis_key", "ai_recommended")
            thesis_label = dt.get("thesis_name", "AI Recommended")
            for tk in dt.get("recommended_tickers", []):
                symbol = tk.get("symbol", "")
                if symbol and symbol not in existing_tickers:
                    desc = f"{tk.get('name', symbol)} — {tk.get('why', 'AI-recommended')}"
                    result = analyze_ticker(symbol, desc, f"dynamic_{thesis_key}", f"[AI] {thesis_label}")
                    result["is_dynamic"] = True  # Flag so dashboard can distinguish
                    watchlist.append(result)
                    existing_tickers.add(symbol)
                    dynamic_added += 1
                    if result["price"]:
                        print(f"  {symbol}: ${result['price']:.2f} | Score {result['opportunity_score']}/100 [{result['signal']}]")
                    else:
                        print(f"  {symbol}: FAILED")
        print(f"  Added {dynamic_added} dynamic tickers to watchlist")

        # Fetch fundamentals for high-scoring dynamic tickers
        dynamic_top = sorted(
            [w for w in watchlist if w.get("is_dynamic") and w.get("opportunity_score", 0) >= 50],
            key=lambda x: x["opportunity_score"],
            reverse=True
        )
        for item in dynamic_top:
            item["fundamentals"] = fetch_fundamentals(item["ticker"])

    # Stock profiles with sentiment intelligence (for top stocks)
    profile_candidates = sorted(
        [w for w in watchlist if w.get("opportunity_score", 0) >= 65],
        key=lambda x: x["opportunity_score"],
        reverse=True
    )[:8]
    stock_profiles = run_stock_profiles(profile_candidates, macro, thesis_health)

    # Projection history tracking
    if ai_analysis and ai_analysis.get('top_recommendations'):
        update_projection_history(ai_analysis, watchlist)

    # Projection accuracy
    history = load_projection_history()
    projection_accuracy = check_projection_accuracy(history, watchlist) if history else None

    # Earnings calendar
    print("\nChecking earnings calendar...")
    earnings = fetch_earnings_calendar(watchlist)

    # Price alerts from projections
    price_alerts = check_price_alerts(history, watchlist)

    # Market status
    sp = macro.get("sp500", {})
    vix_val = macro.get("vix", {}).get("value")
    if sp.get("change_pct") is not None:
        if vix_val and vix_val > 30:
            market_status = "FEAR"
        elif sp["change_pct"] > 1:
            market_status = "RISK-ON"
        elif sp["change_pct"] < -1:
            market_status = "RISK-OFF"
        else:
            market_status = "NEUTRAL"
    else:
        market_status = "UNKNOWN"

    # Summary stats
    summary = {
        "total_tickers": len(watchlist),
        "up": sum(1 for w in watchlist if (w.get("daily_change_pct") or 0) > 0),
        "down": sum(1 for w in watchlist if (w.get("daily_change_pct") or 0) < 0),
        "flat": sum(1 for w in watchlist if w.get("daily_change_pct") is None or abs(w["daily_change_pct"]) < 0.1),
        "strong_buys": sum(1 for w in watchlist if w.get("signal") == "STRONG BUY"),
        "buys": sum(1 for w in watchlist if w.get("signal") == "BUY"),
        "holds": sum(1 for w in watchlist if w.get("signal") == "HOLD"),
        "avg_score": round(sum(w.get("opportunity_score", 50) for w in watchlist) / len(watchlist), 1) if watchlist else 50,
    }

    # Assemble output
    data = {
        "last_updated": datetime.now().isoformat(),
        "market_status": market_status,
        "macro_regime": macro_regime,
        "dynamic_theses": dynamic_theses,
        "macro": macro,
        "thesis_health": thesis_health,
        "watchlist": watchlist,
        "alerts": alerts,
        "watchlist_summary": summary,
        "ai_analysis": ai_analysis,
        "stock_profiles": stock_profiles,
        "projection_accuracy": projection_accuracy,
        "earnings_calendar": earnings,
        "price_alerts": price_alerts,
        "projection_history": history.get("snapshots", [])[-30:] if history else [],
    }

    # ─── HELD POSITIONS (RSU tracking for Our Future dashboard) ───
    print("\nTracking held positions...")
    held_positions = {}
    try:
        lly_ticker = yf.Ticker("LLY")
        lly_hist = lly_ticker.history(period="5d")
        if len(lly_hist) >= 1:
            lly_price = round(lly_hist["Close"].iloc[-1], 2)
            lly_prev = lly_hist["Close"].iloc[-2] if len(lly_hist) >= 2 else lly_price
            lly_daily_change = round(lly_price - lly_prev, 2)
            lly_daily_change_pct = round((lly_daily_change / lly_prev) * 100, 2) if lly_prev else 0

            # Weekly change: compare to 5 days ago if available
            lly_week_ago = lly_hist["Close"].iloc[0] if len(lly_hist) >= 5 else lly_hist["Close"].iloc[0]
            lly_weekly_change = round(lly_price - lly_week_ago, 2)
            lly_weekly_change_pct = round((lly_weekly_change / lly_week_ago) * 100, 2) if lly_week_ago else 0

            rsu_shares = 22.552
            rsu_value = round(rsu_shares * lly_price, 2)

            held_positions["LLY"] = {
                "name": "Eli Lilly",
                "price": lly_price,
                "daily_change": lly_daily_change,
                "daily_change_pct": lly_daily_change_pct,
                "weekly_change": lly_weekly_change,
                "weekly_change_pct": lly_weekly_change_pct,
                "rsu_shares": rsu_shares,
                "rsu_value": rsu_value,
                "as_of": datetime.now().isoformat(),
            }
            print(f"  LLY: ${lly_price} ({lly_daily_change_pct:+.2f}% day) | RSU Value: ${rsu_value:,.2f} ({rsu_shares} shares)")
        else:
            print("  LLY: No price data available")
    except Exception as e:
        print(f"  LLY held position tracking failed: {e}")

    data["held_positions"] = held_positions

    # Write JSON — sanitize NaN/Infinity (invalid in JSON spec)
    import math
    def sanitize(obj):
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        if isinstance(obj, dict):
            return {k: sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [sanitize(v) for v in obj]
        return obj

    data = sanitize(data)
    os.makedirs(DASHBOARD_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f, indent=2)

    # Write JSON
    print(f"\nData written to {OUTPUT_FILE}")
    print(f"Market: {market_status} | Score Avg: {summary['avg_score']}/100")
    print(f"Signals: {summary['strong_buys']} STRONG BUY, {summary['buys']} BUY, {summary['holds']} HOLD")
    print(f"Alerts: {len(alerts)}")
    print(f"Stock profiles: {len(stock_profiles)} tickers")
    if ai_analysis and not ai_analysis.get("parse_error"):
        print(f"AI Summary: {ai_analysis.get('action_summary', 'N/A')}")

    # ─── FIRE NOTIFICATIONS ───────────────────────────────────
    fire_notifications(watchlist, ai_analysis, price_alerts, alerts, market_status)

    # ─── MORNING AUTO-OPEN DASHBOARD ──────────────────────────
    if datetime.now().hour < 12:
        print("Morning run — opening dashboard in browser...")
        subprocess.Popen(["open", "http://localhost:8078/invest-intel.html"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print("=" * 60)


if __name__ == "__main__":
    run()
