"""Free stock research + vertical year chart for Business Insight shorts."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

# Well-known company → ticker fallbacks when Yahoo search is thin
KNOWN_TICKERS = {
    "apple": "AAPL",
    "microsoft": "MSFT",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "amazon": "AMZN",
    "meta": "META",
    "facebook": "META",
    "nvidia": "NVDA",
    "tesla": "TSLA",
    "netflix": "NFLX",
    "disney": "DIS",
    "nike": "NKE",
    "coca cola": "KO",
    "coca-cola": "KO",
    "pepsi": "PEP",
    "walmart": "WMT",
    "costco": "COST",
    "mcdonalds": "MCD",
    "mcdonald's": "MCD",
    "starbucks": "SBUX",
    "intel": "INTC",
    "amd": "AMD",
    "ibm": "IBM",
    "oracle": "ORCL",
    "salesforce": "CRM",
    "adobe": "ADBE",
    "uber": "UBER",
    "airbnb": "ABNB",
    "spotify": "SPOT",
    "blockbuster": "BLIAQ",  # may fail — handled gracefully
    "kodak": "KODK",
    "boeing": "BA",
    "ford": "F",
    "gm": "GM",
    "general motors": "GM",
    "jpmorgan": "JPM",
    "jp morgan": "JPM",
    "goldman sachs": "GS",
    "berkshire": "BRK-B",
    "berkshire hathaway": "BRK-B",
    "visa": "V",
    "mastercard": "MA",
    "paypal": "PYPL",
    "shopify": "SHOP",
    "snap": "SNAP",
    "twitter": "X",
    "x corp": "X",
    "zoom": "ZM",
    "palantir": "PLTR",
    "coinbase": "COIN",
    "robinhood": "HOOD",
}


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] stock: {msg}")


def extract_company_query(prompt: str) -> str:
    """Pull company name from a short prompt (ignore filler words)."""
    text = str(prompt or "").strip()
    text = re.sub(
        r"^(analyze|analyse|explain|cover|research|stock|chart|about|for|the)\s+",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(r"\b(stock|shares|chart|price|history|insights?)\b", "", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip(" .,:-") or str(prompt or "").strip()


def resolve_ticker(company_or_ticker: str) -> dict[str, str]:
    """Resolve a company name or ticker symbol to Yahoo Finance ticker."""
    import yfinance as yf

    raw = extract_company_query(company_or_ticker)
    if not raw:
        raise ValueError("Company name or ticker is required")

    key = raw.lower()
    if key in KNOWN_TICKERS:
        ticker = KNOWN_TICKERS[key]
        name = raw.title()
        try:
            info = yf.Ticker(ticker).info or {}
            name = info.get("shortName") or info.get("longName") or name
        except Exception:
            pass
        return {"ticker": ticker, "name": name, "query": raw}

    # Direct ticker only when input looks like a symbol (all caps or short code)
    candidate = raw.upper().replace(".", "-")
    looks_like_ticker = bool(re.fullmatch(r"[A-Z]{1,5}(-[A-Z])?", candidate)) and (
        raw.isupper() or len(raw) <= 4
    )
    if looks_like_ticker:
        t = yf.Ticker(candidate)
        hist = t.history(period="5d")
        if hist is not None and not hist.empty:
            name = raw
            try:
                name = (t.info or {}).get("shortName") or (t.info or {}).get("longName") or raw
            except Exception:
                pass
            return {"ticker": candidate, "name": name, "query": raw}

    # Yahoo search
    try:
        search = yf.Search(raw, max_results=8)
        quotes = getattr(search, "quotes", None) or []
        for q in quotes:
            sym = str(q.get("symbol") or "").strip()
            quote_type = str(q.get("quoteType") or q.get("typeDisp") or "").upper()
            if not sym:
                continue
            if quote_type and quote_type not in {"EQUITY", "ETF", "STOCK", ""}:
                continue
            name = q.get("shortname") or q.get("longname") or q.get("name") or raw
            return {"ticker": sym, "name": str(name), "query": raw}
        if quotes:
            q0 = quotes[0]
            return {
                "ticker": str(q0.get("symbol")),
                "name": str(q0.get("shortname") or q0.get("longname") or raw),
                "query": raw,
            }
    except Exception as e:
        _log(f"Search failed ({e}), trying ticker guess")

    # Last resort: use cleaned uppercase token
    guess = re.sub(r"[^A-Za-z]", "", raw).upper()[:5]
    if guess:
        return {"ticker": guess, "name": raw.title(), "query": raw}
    raise ValueError(f"Could not resolve ticker for: {raw}")


def _year_end_series(ticker: str, years: int = 10):
    import yfinance as yf
    import pandas as pd

    period = f"{max(years + 1, 5)}y"
    t = yf.Ticker(ticker)
    hist = t.history(period=period, auto_adjust=True)
    if hist is None or hist.empty:
        raise ValueError(f"No price history for {ticker}")

    # Year-end close (last trading day each calendar year)
    closes = hist["Close"].copy()
    closes.index = pd.to_datetime(closes.index).tz_localize(None)
    # pandas <2.2 uses "Y"/"A"; newer uses "YE"
    try:
        yearly = closes.resample("YE").last().dropna()
    except ValueError:
        yearly = closes.resample("Y").last().dropna()
    # Keep last N years
    yearly = yearly.tail(years + 1)
    rows: list[dict[str, Any]] = []
    prev = None
    for ts, price in yearly.items():
        year = int(ts.year)
        price_f = float(price)
        change_pct = None
        if prev is not None and prev > 0:
            change_pct = round(((price_f - prev) / prev) * 100.0, 2)
        rows.append({"year": year, "close": round(price_f, 2), "change_pct": change_pct})
        prev = price_f
    return hist, rows, t


def _fetch_news_headlines(ticker_obj, limit: int = 8) -> list[dict]:
    headlines: list[dict] = []
    try:
        news = ticker_obj.news or []
    except Exception:
        news = []
    for item in news[:limit]:
        # yfinance news shape varies by version
        content = item.get("content") if isinstance(item.get("content"), dict) else item
        title = (
            content.get("title")
            or item.get("title")
            or (item.get("content") or {}).get("title")
            if isinstance(item.get("content"), dict)
            else None
        )
        if not title and isinstance(item, dict):
            title = item.get("title")
        pub = (
            content.get("pubDate")
            or item.get("providerPublishTime")
            or item.get("pubDate")
        )
        if title:
            headlines.append({"title": str(title)[:180], "published": str(pub) if pub else ""})
    return headlines


def build_stock_research(company_or_ticker: str, *, years: int = 10) -> dict:
    """Fetch yearly closes, compute swings, attach recent news headlines."""
    resolved = resolve_ticker(company_or_ticker)
    ticker = resolved["ticker"]
    _log(f"Research {resolved['name']} ({ticker}), {years}y")

    hist, yearly, ticker_obj = _year_end_series(ticker, years=years)
    if len(yearly) < 2:
        raise ValueError(f"Not enough yearly data for {ticker}")

    first = yearly[0]
    last = yearly[-1]
    total_return = None
    if first["close"] > 0:
        total_return = round(((last["close"] - first["close"]) / first["close"]) * 100.0, 2)

    swings = [y for y in yearly if y.get("change_pct") is not None]
    best = max(swings, key=lambda y: y["change_pct"]) if swings else None
    worst = min(swings, key=lambda y: y["change_pct"]) if swings else None

    info: dict = {}
    try:
        info = ticker_obj.info or {}
    except Exception:
        info = {}

    sector = info.get("sector") or ""
    industry = info.get("industry") or ""
    summary = (info.get("longBusinessSummary") or "")[:500]
    currency = info.get("currency") or "USD"

    # Peak / trough in window
    try:
        peak_idx = hist["Close"].idxmax()
        trough_idx = hist["Close"].idxmin()
        peak = {"date": str(peak_idx.date()), "close": round(float(hist.loc[peak_idx, "Close"]), 2)}
        trough = {
            "date": str(trough_idx.date()),
            "close": round(float(hist.loc[trough_idx, "Close"]), 2),
        }
    except Exception:
        peak, trough = None, None

    headlines = _fetch_news_headlines(ticker_obj)

    research = {
        "company": resolved["name"],
        "ticker": ticker,
        "query": resolved["query"],
        "currency": currency,
        "sector": sector,
        "industry": industry,
        "summary": summary,
        "years_requested": years,
        "yearly": yearly,
        "total_return_pct": total_return,
        "best_year": best,
        "worst_year": worst,
        "peak": peak,
        "trough": trough,
        "recent_news": headlines,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
    }
    return research


def research_context_for_llm(research: dict) -> str:
    """Compact grounding pack for the script LLM."""
    lines = [
        f"COMPANY: {research.get('company')} ({research.get('ticker')})",
        f"SECTOR: {research.get('sector')} | INDUSTRY: {research.get('industry')}",
        f"CURRENCY: {research.get('currency')}",
    ]
    if research.get("total_return_pct") is not None:
        y0 = research["yearly"][0]["year"]
        y1 = research["yearly"][-1]["year"]
        lines.append(
            f"TOTAL RETURN {y0}→{y1}: {research['total_return_pct']}% "
            f"(from {research['yearly'][0]['close']} to {research['yearly'][-1]['close']})"
        )
    if research.get("best_year"):
        b = research["best_year"]
        lines.append(f"BEST YEAR: {b['year']} ({b['change_pct']}%) close {b['close']}")
    if research.get("worst_year"):
        w = research["worst_year"]
        lines.append(f"WORST YEAR: {w['year']} ({w['change_pct']}%) close {w['close']}")
    if research.get("peak"):
        lines.append(f"PEAK IN WINDOW: {research['peak']['date']} @ {research['peak']['close']}")
    if research.get("trough"):
        lines.append(
            f"TROUGH IN WINDOW: {research['trough']['date']} @ {research['trough']['close']}"
        )

    lines.append("YEARLY CLOSES (use these exact numbers):")
    for row in research.get("yearly") or []:
        ch = row.get("change_pct")
        ch_s = f"{ch:+.2f}%" if ch is not None else "n/a"
        lines.append(f"  {row['year']}: close {row['close']} ({ch_s})")

    if research.get("recent_news"):
        lines.append("RECENT NEWS HEADLINES (use for event context when relevant):")
        for h in research["recent_news"][:6]:
            lines.append(f"  - {h['title']}")

    if research.get("summary"):
        lines.append(f"BUSINESS SNAPSHOT: {research['summary']}")

    lines.append(
        "INSTRUCTIONS: Narrate the chart story. For major up/down years, explain the likely "
        "real-world news/events that drove the move (earnings shocks, product launches, "
        "regulation, crises, M&A, macro). Do not invent prices. No buy/sell advice."
    )
    return "\n".join(lines)


def render_year_chart(
    research: dict,
    output_path: str,
    *,
    resolution: tuple[int, int] = (1080, 1920),
    colors: dict | None = None,
) -> str:
    """Render a vertical 9:16 year-wise stock chart PNG."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    colors = colors or {}
    bg = colors.get("background", "#070B14")
    primary = colors.get("primary", "#38BDF8")
    accent = colors.get("accent", "#FBBF24")
    text = colors.get("text", "#F8FAFC")
    muted = "#94A3B8"

    yearly = research.get("yearly") or []
    if len(yearly) < 2:
        raise ValueError("Need at least 2 yearly points to chart")

    years = [r["year"] for r in yearly]
    closes = [r["close"] for r in yearly]
    changes = [r.get("change_pct") for r in yearly]

    w, h = resolution
    dpi = 100
    fig_w, fig_h = w / dpi, h / dpi
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(bg)

    # Soft panel behind chart
    ax.set_xlim(-0.5, len(years) - 0.5)
    ymin = min(closes) * 0.85
    ymax = max(closes) * 1.12
    ax.set_ylim(ymin, ymax)

    ax.plot(range(len(years)), closes, color=primary, linewidth=3.2, zorder=3)
    ax.fill_between(range(len(years)), closes, ymin, color=primary, alpha=0.18, zorder=2)
    ax.scatter(range(len(years)), closes, color=accent, s=48, zorder=4, edgecolors=bg, linewidths=1.5)

    # Annotate best / worst YoY
    for i, ch in enumerate(changes):
        if ch is None:
            continue
        if research.get("best_year") and years[i] == research["best_year"]["year"]:
            ax.annotate(
                f"{ch:+.0f}%",
                (i, closes[i]),
                textcoords="offset points",
                xytext=(0, 14),
                ha="center",
                color=accent,
                fontsize=11,
                fontweight="bold",
            )
        elif research.get("worst_year") and years[i] == research["worst_year"]["year"]:
            ax.annotate(
                f"{ch:+.0f}%",
                (i, closes[i]),
                textcoords="offset points",
                xytext=(0, -18),
                ha="center",
                color="#F87171",
                fontsize=11,
                fontweight="bold",
            )

    ax.set_xticks(range(len(years)))
    ax.set_xticklabels([str(y) for y in years], rotation=45, ha="right", color=muted, fontsize=10)
    ax.tick_params(axis="y", colors=muted, labelsize=10)
    for spine in ax.spines.values():
        spine.set_color("#1E293B")
    ax.grid(True, axis="y", color="#1E293B", alpha=0.8, linewidth=0.8)
    ax.set_ylabel(f"Year-end close ({research.get('currency', 'USD')})", color=muted, fontsize=11)

    title = f"{research.get('company')} ({research.get('ticker')})"
    fig.text(0.5, 0.94, title, ha="center", va="top", color=text, fontsize=22, fontweight="bold")
    subtitle = "Year-end stock price"
    if research.get("total_return_pct") is not None:
        subtitle += f"  ·  {research['total_return_pct']:+.1f}% total"
    fig.text(0.5, 0.905, subtitle, ha="center", va="top", color=muted, fontsize=12)

    # Bottom insight strip
    insight_bits = []
    if research.get("best_year"):
        b = research["best_year"]
        insight_bits.append(f"Best: {b['year']} {b['change_pct']:+.0f}%")
    if research.get("worst_year"):
        wrow = research["worst_year"]
        insight_bits.append(f"Worst: {wrow['year']} {wrow['change_pct']:+.0f}%")
    if insight_bits:
        fig.text(
            0.5,
            0.045,
            "   ·   ".join(insight_bits),
            ha="center",
            va="bottom",
            color=muted,
            fontsize=11,
        )

    # Leave room for captions in lower third — chart sits upper-mid
    plt.subplots_adjust(left=0.14, right=0.92, top=0.86, bottom=0.18)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out), facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    _log(f"Chart written -> {out}")
    return str(out)


def save_research_pack(research: dict, job_dir: Path) -> dict[str, str]:
    """Persist research JSON + chart under the job directory."""
    job_dir = Path(job_dir)
    images = job_dir / "images"
    images.mkdir(parents=True, exist_ok=True)
    json_path = job_dir / "stock_research.json"
    json_path.write_text(json.dumps(research, indent=2), encoding="utf-8")
    chart_path = images / "stock_chart.png"
    colors = {
        "background": "#070B14",
        "primary": "#38BDF8",
        "accent": "#FBBF24",
        "text": "#F8FAFC",
    }
    render_year_chart(research, str(chart_path), colors=colors)
    return {"research_json": str(json_path), "chart": str(chart_path)}
