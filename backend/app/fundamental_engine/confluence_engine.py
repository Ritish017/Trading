"""
Fundamental Engine — Factor Scorecard & Technical × Fundamental Confluence (Phase 7)
====================================================================================
Generates comprehensive factor scorecards and evaluates multi-layer empirical confluence
between Technical Strategy states and Fundamental Factor profiles.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
import numpy as np

from backend.app.fundamental_engine.models import (
    DataStatus,
    CompanyProfile,
)
from backend.app.fundamental_engine.factors import (
    FACTOR_REGISTRY,
    FactorCategory,
)
from backend.app.fundamental_engine.dependency_engine import (
    FundamentalDependencyContext,
    FundamentalDependencyEngine,
)
from backend.app.fundamental_engine.normalization import (
    calculate_cross_sectional_ranks,
    calculate_sector_relative_factors,
)
from backend.app.fundamental_engine.providers import fundamental_data_hub


@dataclass
class FactorScorecardItem:
    """Detailed evidence item for a single factor in the scorecard."""
    factor_id: str
    name: str
    category: str
    raw_value: Optional[float]
    unit: str
    formula: str
    direction_preference: str
    percentile_rank: Optional[float]
    data_status: str
    publication_date: Optional[str]
    reporting_period: Optional[str]
    source: str


@dataclass
class FactorScorecard:
    """Comprehensive multi-category fundamental evidence scorecard."""
    symbol: str
    company_name: str
    sector: str
    industry: str
    market_cap_crores: Optional[float]
    as_of_date: str
    overall_fundamental_profile: str  # STRONG | MODERATE | WEAK | INSUFFICIENT_DATA
    category_summaries: Dict[str, Dict[str, Any]]
    factors: List[FactorScorecardItem]


@dataclass
class MultiLayerConfluenceMatrix:
    """3x3 Technical x Fundamental empirical evidence matrix."""
    symbol: str
    technical_state: str        # BULLISH | NEUTRAL | BEARISH
    technical_evidence: str
    fundamental_state: str      # STRONG | NEUTRAL | WEAK
    fundamental_evidence: str
    confluence_quadrant: str    # HIGH_CONVICTION_LONG | VALUE_TRAP_RISK | MOMENTUM_WITHOUT_EARNINGS | CONTRARIAN_REVERSAL | AVOID
    evidence_breakdown: List[Dict[str, Any]]


class ConfluenceEngine:
    """
    Evaluates Factor Scorecards and Multi-Layer Confluence.
    """

    @classmethod
    async def generate_scorecard(
        cls,
        symbol: str,
        as_of_timestamp: Optional[int] = None,
        current_price: Optional[float] = None,
    ) -> FactorScorecard:
        ctx = await FundamentalDependencyEngine.build_context(
            symbol=symbol,
            as_of_timestamp=as_of_timestamp,
            current_price=current_price,
        )

        prof = ctx.profile or CompanyProfile(symbol=symbol, company_name=symbol, sector="UNKNOWN", industry="UNKNOWN")

        # Get peer universe for cross-sectional ranking
        peers = await fundamental_data_hub.get_sector_peers(symbol)
        peer_factors: Dict[str, Dict[str, Optional[float]]] = {}

        for p_sym in peers:
            p_ctx = await FundamentalDependencyEngine.build_context(p_sym, as_of_timestamp=ctx.as_of_timestamp)
            peer_factors[p_sym] = p_ctx.factor_cache

        scorecard_items: List[FactorScorecardItem] = []
        category_scores: Dict[str, List[float]] = {}

        latest_inc = ctx.incomes[-1] if ctx.incomes else None
        pub_date = latest_inc.period_end if latest_inc else "N/A"

        for f_id, defn in FACTOR_REGISTRY.items():
            val = ctx.factor_cache.get(f_id)

            # Compute cross-sectional percentile among sector peers
            peer_map = {s: peer_factors.get(s, {}).get(f_id) for s in peers}
            ranks = calculate_cross_sectional_ranks(peer_map, f_id)
            pct = ranks.get(symbol).percentile_rank if ranks.get(symbol) else None

            cat_str = defn.category.value if hasattr(defn.category, "value") else str(defn.category)
            if pct is not None:
                if cat_str not in category_scores:
                    category_scores[cat_str] = []
                category_scores[cat_str].append(pct)

            item = FactorScorecardItem(
                factor_id=f_id,
                name=defn.name,
                category=cat_str,
                raw_value=val,
                unit=defn.unit,
                formula=defn.formula,
                direction_preference=defn.direction_preference.value if hasattr(defn.direction_preference, "value") else str(defn.direction_preference),
                percentile_rank=pct,
                data_status="AVAILABLE" if val is not None else "UNAVAILABLE",
                publication_date=pub_date,
                reporting_period=latest_inc.period_end if latest_inc else None,
                source="AUDITED_ANNUAL_REPORT",
            )
            scorecard_items.append(item)

        # Compute Category Summaries
        cat_summaries: Dict[str, Dict[str, Any]] = {}
        all_pcts: List[float] = []

        for cat, pcts in category_scores.items():
            avg_pct = round(float(np.mean(pcts)), 1) if pcts else 50.0
            all_pcts.extend(pcts)
            rating = "STRONG" if avg_pct >= 65 else ("WEAK" if avg_pct <= 35 else "NEUTRAL")
            cat_summaries[cat] = {
                "average_percentile": avg_pct,
                "rating": rating,
                "factors_available": len(pcts),
            }

        overall_avg = float(np.mean(all_pcts)) if all_pcts else 50.0
        if not all_pcts:
            overall_profile = "INSUFFICIENT_DATA"
        elif overall_avg >= 65:
            overall_profile = "STRONG"
        elif overall_avg <= 35:
            overall_profile = "WEAK"
        else:
            overall_profile = "MODERATE"

        return FactorScorecard(
            symbol=symbol,
            company_name=prof.company_name,
            sector=prof.sector,
            industry=prof.industry,
            market_cap_crores=prof.market_cap_crores,
            as_of_date=pub_date,
            overall_fundamental_profile=overall_profile,
            category_summaries=cat_summaries,
            factors=scorecard_items,
        )

    @classmethod
    def evaluate_technical_fundamental_confluence(
        cls,
        symbol: str,
        technical_active_count: int,
        technical_total_count: int,
        scorecard: FactorScorecard,
    ) -> MultiLayerConfluenceMatrix:
        """
        Synthesizes technical alignment and fundamental factor strength into a 3x3 empirical matrix.
        """
        # Determine Technical Bias
        tech_ratio = technical_active_count / max(1, technical_total_count)
        if tech_ratio >= 0.4:
            tech_state = "BULLISH"
            tech_ev = f"{technical_active_count}/{technical_total_count} technical strategies active (Trend & Momentum aligned)"
        elif tech_ratio == 0:
            tech_state = "BEARISH"
            tech_ev = "Zero technical strategies active (Downward momentum or breakdown)"
        else:
            tech_state = "NEUTRAL"
            tech_ev = f"{technical_active_count}/{technical_total_count} technical strategies active (Partial alignment)"

        fund_state = scorecard.overall_fundamental_profile
        fund_ev = f"Fundamental factor profile: {fund_state} (Sector Percentile composite)"

        # 3x3 Matrix Confluence Classification
        if tech_state == "BULLISH" and fund_state == "STRONG":
            quadrant = "HIGH_CONVICTION_LONG"
        elif tech_state == "BULLISH" and fund_state == "WEAK":
            quadrant = "MOMENTUM_WITHOUT_EARNINGS"
        elif tech_state == "BEARISH" and fund_state == "STRONG":
            quadrant = "VALUE_TRAP_OR_CONTRARIAN_OPPORTUNITY"
        elif tech_state == "BEARISH" and fund_state == "WEAK":
            quadrant = "HIGH_RISK_AVOID"
        else:
            quadrant = "NEUTRAL_MIXED_EVIDENCE"

        evidence_list = [
            {"layer": "TECHNICAL", "state": tech_state, "detail": tech_ev},
            {"layer": "FUNDAMENTAL", "state": fund_state, "detail": fund_ev},
            {
                "layer": "GROWTH_VS_VALUATION",
                "detail": f"Growth: {scorecard.category_summaries.get('GROWTH', {}).get('rating', 'N/A')}, Value: {scorecard.category_summaries.get('VALUE', {}).get('rating', 'N/A')}"
            },
        ]

        return MultiLayerConfluenceMatrix(
            symbol=symbol,
            technical_state=tech_state,
            technical_evidence=tech_ev,
            fundamental_state=fund_state,
            fundamental_evidence=fund_ev,
            confluence_quadrant=quadrant,
            evidence_breakdown=evidence_list,
        )


confluence_engine = ConfluenceEngine()
