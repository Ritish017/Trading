"""
APEX Global Research & News Ingestion System
============================================
Autonomous multi-source research ingestion engine covering:
- Global Financial Markets & Macro
- Precious Metals: Gold, Silver, Platinum
- Energy: Crude Oil (Brent & WTI), Natural Gas
- Industrial Metals: Copper, Aluminium, Zinc
- Agriculture: Wheat, Cotton, Soybeans, Corn
- Central Banks: RBI, US Fed, ECB
- Commodity Inventory & Trade Reports: EIA, USDA

Features:
- Source Registry with Credibility Ratings (1-10)
- SHA-256 Article Deduplication
- Timestamp Normalization (publication and event timestamps)
- Asset Relevance Mapping (mapping to Universal Instrument Registry)
- Prompt-Injection Sanitization (treating raw web text as untrusted data)
- Provenance & Traceable URLs
"""

import hashlib
import re
import time
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import httpx

from backend.app.market_data.instrument_registry import instrument_registry, AssetClass

logger = logging.getLogger(__name__)


class SourceCredibility(BaseModel):
    source_name: str
    category: str
    credibility_score: float  # 1.0 to 10.0
    is_official_regulatory: bool = False
    url: str


class ResearchArticle(BaseModel):
    article_id: str
    title: str
    summary: str
    source: str
    url: str
    published_at: str
    published_timestamp: float
    event_timestamp: Optional[float] = None
    credibility_score: float = 7.0
    relevant_instruments: List[str] = Field(default_factory=list)
    asset_classes: List[str] = Field(default_factory=list)
    importance: str = "NORMAL"  # LOW, NORMAL, HIGH, CRITICAL
    sentiment_hint: float = 0.0  # -1.0 to +1.0
    is_breaking: bool = False
    sanitized: bool = True
    raw_hash: str


# Authoritative Source Registry
RESEARCH_SOURCES: List[Dict[str, Any]] = [
    # Indian Financial
    {
        "name": "Economic Times Markets",
        "category": "INDIAN_EQUITY_MACRO",
        "url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "credibility": 8.5,
        "is_official": False,
    },
    {
        "name": "Moneycontrol Markets",
        "category": "INDIAN_EQUITY_MACRO",
        "url": "https://www.moneycontrol.com/rss/marketreports.xml",
        "credibility": 8.0,
        "is_official": False,
    },
    {
        "name": "Livemint Markets",
        "category": "INDIAN_EQUITY_MACRO",
        "url": "https://www.livemint.com/rss/markets",
        "credibility": 8.5,
        "is_official": False,
    },
    # Global Macro & Commodities
    {
        "name": "MarketWatch Top Stories",
        "category": "GLOBAL_MACRO",
        "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "credibility": 8.5,
        "is_official": False,
    },
    {
        "name": "Kitco Metals News",
        "category": "PRECIOUS_METALS",
        "url": "https://www.kitco.com/rss/KitcoNewsRSS.xml",
        "credibility": 8.0,
        "is_official": False,
    },
    {
        "name": "OilPrice Energy News",
        "category": "ENERGY",
        "url": "https://oilprice.com/rss/main",
        "credibility": 8.0,
        "is_official": False,
    },
    {
        "name": "USDA Agriculture Releases",
        "category": "AGRICULTURE",
        "url": "https://www.usda.gov/rss/latest-releases.xml",
        "credibility": 9.5,
        "is_official": True,
    },
    {
        "name": "Federal Reserve Press Releases",
        "category": "CENTRAL_BANK",
        "url": "https://www.federalreserve.gov/feeds/press_all.xml",
        "credibility": 10.0,
        "is_official": True,
    },
]

# Asset Keyword Mapper
ASSET_KEYWORD_MAP = {
    "GOLD_MCX": ["gold", "xau", "bullion", "yellow metal", "sovereign gold"],
    "SILVER_MCX": ["silver", "xag", "white metal"],
    "CRUDEOIL_MCX": ["crude", "oil", "brent", "wti", "opec", "petroleum", "rig count"],
    "NATGAS_MCX": ["natural gas", "natgas", "henry hub", "lng", "eia gas storage"],
    "COPPER_MCX": ["copper", "red metal", "comex copper", "lme copper"],
    "WHEAT_CBOT": ["wheat", "grain", "cbot wheat", "wasde"],
    "COTTON_MCX": ["cotton", "yarn", "textile exports"],
    "NIFTY50_NSE": ["nifty", "nse", "dalal street", "sensex", "bse", "fii flows"],
    "USDINR_NSE": ["rupee", "usdinr", "rbi intervention", "dollar rupee", "dxy"],
}

# Prompt Injection Patterns to strip
INJECTION_PATTERNS = [
    r"ignore previous instructions",
    r"disregard all previous",
    r"you are now in developer mode",
    r"system prompt:",
    r"assistant:",
    r"dan mode",
    r"<\|.*?\|>",
    r"```(?:python|bash|sh|cmd|powershell)?",
]


def sanitize_untrusted_text(text: str) -> str:
    """
    Sanitizes raw external news and HTML/text to prevent prompt injection attacks.
    Treats all incoming news strictly as data.
    """
    if not text:
        return ""
    clean = text
    for pattern in INJECTION_PATTERNS:
        clean = re.sub(pattern, "[FILTERED]", clean, flags=re.IGNORECASE)
    # Strip HTML tags
    clean = re.sub(r"<[^>]+>", " ", clean)
    # Strip excessive newlines and whitespace
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:1000]  # Cap at 1000 chars per excerpt


class GlobalResearchEngine:
    """
    Continuous live research scraper, deduplicator, and relevance router.
    """

    def __init__(self):
        self.sources = RESEARCH_SOURCES
        self._dedup_cache: Dict[str, float] = {}  # hash -> timestamp
        self._article_cache: List[ResearchArticle] = []
        self._last_scrape_time: float = 0.0

    @classmethod
    def compute_hash(cls, title: str, link: str) -> str:
        raw = f"{title.strip().lower()}_{link.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def map_relevance(self, title: str, summary: str) -> List[str]:
        """Maps an article to registered instrument IDs based on taxonomy keywords."""
        content = f"{title} {summary}".lower()
        matched = []
        for inst_id, keywords in ASSET_KEYWORD_MAP.items():
            if any(re.search(r"\b" + re.escape(kw) + r"\b", content) for kw in keywords):
                matched.append(inst_id)
        return matched

    async def fetch_all_sources(self, timeout: float = 5.0) -> List[ResearchArticle]:
        """
        Polls configured RSS sources, deduplicates, sanitizes, and returns fresh articles.
        """
        now = time.time()
        new_articles: List[ResearchArticle] = []

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            for src in self.sources:
                try:
                    res = await client.get(
                        src["url"],
                        headers={"User-Agent": "APEX-Global-Research/2.0 (+https://apex-trading-lab.vercel.app)"},
                    )
                    if res.status_code != 200:
                        continue

                    root = ET.fromstring(res.content)
                    items = root.findall(".//item")
                    if not items:
                        # Atom feed fallback
                        items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

                    for item in items[:8]:
                        title = item.findtext("title") or item.findtext("{http://www.w3.org/2005/Atom}title") or ""
                        link = item.findtext("link") or item.findtext("{http://www.w3.org/2005/Atom}link") or ""
                        desc = (
                            item.findtext("description")
                            or item.findtext("summary")
                            or item.findtext("{http://www.w3.org/2005/Atom}summary")
                            or ""
                        )
                        pub_date = (
                            item.findtext("pubDate")
                            or item.findtext("{http://www.w3.org/2005/Atom}updated")
                            or datetime.now(timezone.utc).isoformat()
                        )

                        if not title:
                            continue

                        art_hash = self.compute_hash(title, link)
                        if art_hash in self._dedup_cache:
                            continue

                        # Sanitize untrusted text
                        clean_title = sanitize_untrusted_text(title)
                        clean_summary = sanitize_untrusted_text(desc)

                        relevant_insts = self.map_relevance(clean_title, clean_summary)

                        # Determine importance
                        is_official = src.get("is_official", False)
                        is_breaking = any(w in clean_title.lower() for w in ["breaking", "urgent", "emergency", "rate hike", "rate cut", "embargo", "sanction"])
                        importance = "CRITICAL" if (is_official and is_breaking) else ("HIGH" if (is_official or is_breaking) else "NORMAL")

                        article = ResearchArticle(
                            article_id=f"art_{art_hash[:12]}",
                            title=clean_title,
                            summary=clean_summary,
                            source=src["name"],
                            url=link,
                            published_at=pub_date,
                            published_timestamp=now,
                            event_timestamp=now,
                            credibility_score=src.get("credibility", 7.0),
                            relevant_instruments=relevant_insts,
                            asset_classes=[src.get("category", "MACRO")],
                            importance=importance,
                            is_breaking=is_breaking,
                            sanitized=True,
                            raw_hash=art_hash,
                        )

                        self._dedup_cache[art_hash] = now
                        new_articles.append(article)
                        self._article_cache.append(article)

                except Exception as e:
                    logger.debug(f"[RESEARCH INGESTION] Source {src['name']} fetch skipped: {e}")

        # Keep cache bounded to last 500 articles
        if len(self._article_cache) > 500:
            self._article_cache = self._article_cache[-500:]

        self._last_scrape_time = now
        return new_articles

    def search_articles(
        self,
        instrument_id: Optional[str] = None,
        asset_class: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 10,
    ) -> List[ResearchArticle]:
        """Search local research cache by instrument, asset class, or text query."""
        results = self._article_cache

        if instrument_id:
            results = [a for a in results if instrument_id in a.relevant_instruments]
        if asset_class:
            results = [a for a in results if asset_class in a.asset_classes]
        if query:
            q = query.lower()
            results = [a for a in results if q in a.title.lower() or q in a.summary.lower()]

        return sorted(results, key=lambda a: a.published_timestamp, reverse=True)[:limit]


# Global research engine instance
global_research_engine = GlobalResearchEngine()
