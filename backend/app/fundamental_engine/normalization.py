"""
Fundamental Engine — Cross-Sectional Normalization & Correlation Engine (Phase 7)
=================================================================================
Calculates cross-sectional percentiles, z-scores, sector-relative spreads,
and factor correlation/redundancy matrices across Indian equity universes.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

from backend.app.fundamental_engine.factors import (
    FACTOR_REGISTRY,
    FactorCategory,
    DirectionPreference,
)


@dataclass
class CrossSectionalRank:
    """Normalized cross-sectional rank for a single symbol and factor."""
    symbol: str
    factor_id: str
    raw_value: Optional[float]
    percentile_rank: Optional[float]  # 0.0 to 100.0 (100 = best according to DirectionPreference)
    z_score: Optional[float]
    universe_size: int
    data_status: str


@dataclass
class SectorRelativeSummary:
    """Sector-relative factor comparison summary."""
    symbol: str
    sector: str
    peer_count: int
    factor_id: str
    raw_value: Optional[float]
    sector_median: Optional[float]
    sector_mean: Optional[float]
    sector_percentile_rank: Optional[float]
    sector_spread_pct: Optional[float]


def calculate_cross_sectional_ranks(
    symbol_factor_map: Dict[str, Optional[float]],
    factor_id: str,
) -> Dict[str, CrossSectionalRank]:
    """
    Computes cross-sectional percentile ranks (0-100) and Z-scores across symbols.
    Respects FactorDefinition.direction_preference (HIGHER_IS_BETTER vs LOWER_IS_BETTER).
    """
    defn = FACTOR_REGISTRY.get(factor_id)
    higher_is_better = True
    if defn:
        higher_is_better = (defn.direction_preference == DirectionPreference.HIGHER_IS_BETTER)

    valid_pairs = [(sym, val) for sym, val in symbol_factor_map.items() if val is not None and not np.isnan(val)]
    n_valid = len(valid_pairs)
    n_total = len(symbol_factor_map)

    if n_valid == 0:
        return {
            sym: CrossSectionalRank(
                symbol=sym, factor_id=factor_id, raw_value=None, percentile_rank=None,
                z_score=None, universe_size=n_total, data_status="UNAVAILABLE"
            )
            for sym in symbol_factor_map
        }

    symbols = [p[0] for p in valid_pairs]
    vals = np.array([p[1] for p in valid_pairs], dtype=float)

    mean_v = float(np.mean(vals))
    std_v = float(np.std(vals)) if len(vals) > 1 else 0.0

    # Sort values for percentile ranking
    if higher_is_better:
        order = np.argsort(vals)
    else:
        order = np.argsort(-vals)

    ranks = np.empty_like(order)
    ranks[order] = np.arange(n_valid)

    pct_ranks = (ranks / max(1, n_valid - 1)) * 100.0 if n_valid > 1 else np.array([50.0])

    result: Dict[str, CrossSectionalRank] = {}

    for i, sym in enumerate(symbols):
        raw = float(vals[i])
        pct = round(float(pct_ranks[i]), 1)
        z = round(float((raw - mean_v) / (std_v + 1e-6)), 2) if std_v > 0 else 0.0

        result[sym] = CrossSectionalRank(
            symbol=sym,
            factor_id=factor_id,
            raw_value=raw,
            percentile_rank=pct,
            z_score=z,
            universe_size=n_valid,
            data_status="AVAILABLE",
        )

    # Missing symbols
    for sym, val in symbol_factor_map.items():
        if sym not in result:
            result[sym] = CrossSectionalRank(
                symbol=sym,
                factor_id=factor_id,
                raw_value=None,
                percentile_rank=None,
                z_score=None,
                universe_size=n_valid,
                data_status="UNAVAILABLE",
            )

    return result


def calculate_sector_relative_factors(
    target_symbol: str,
    sector: str,
    peer_symbols_map: Dict[str, Optional[float]],
    factor_id: str,
) -> SectorRelativeSummary:
    """
    Computes sector-relative performance and spread for a specific target equity.
    """
    ranks = calculate_cross_sectional_ranks(peer_symbols_map, factor_id)
    target_rank = ranks.get(target_symbol)

    valid_vals = [v for v in peer_symbols_map.values() if v is not None and not np.isnan(v)]
    if not valid_vals or not target_rank or target_rank.raw_value is None:
        return SectorRelativeSummary(
            symbol=target_symbol,
            sector=sector,
            peer_count=len(peer_symbols_map),
            factor_id=factor_id,
            raw_value=None,
            sector_median=None,
            sector_mean=None,
            sector_percentile_rank=None,
            sector_spread_pct=None,
        )

    med_v = float(np.median(valid_vals))
    mean_v = float(np.mean(valid_vals))
    spread = round(((target_rank.raw_value - med_v) / (abs(med_v) + 1e-6)) * 100.0, 2)

    return SectorRelativeSummary(
        symbol=target_symbol,
        sector=sector,
        peer_count=len(valid_vals),
        factor_id=factor_id,
        raw_value=target_rank.raw_value,
        sector_median=round(med_v, 2),
        sector_mean=round(mean_v, 2),
        sector_percentile_rank=target_rank.percentile_rank,
        sector_spread_pct=spread,
    )


def calculate_factor_correlations(
    symbol_factor_matrix: Dict[str, Dict[str, Optional[float]]],
) -> Dict[str, Any]:
    """
    Calculates pairwise Pearson correlation across all factors in the universe.
    """
    df = pd.DataFrame.from_dict(symbol_factor_matrix, orient="index")
    df = df.dropna(how="all", axis=1)

    corr_matrix = df.corr(method="pearson").round(3).to_dict()
    return corr_matrix


def identify_redundant_factors(
    corr_matrix: Dict[str, Dict[str, float]],
    threshold: float = 0.85,
) -> List[Dict[str, Any]]:
    """
    Identifies pairs of factors with absolute correlation >= threshold (redundant information).
    """
    redundant_pairs: List[Dict[str, Any]] = []
    seen: set = set()

    for f1, row in corr_matrix.items():
        for f2, val in row.items():
            if f1 != f2 and val is not None and not np.isnan(val):
                pair_key = tuple(sorted([f1, f2]))
                if pair_key not in seen and abs(val) >= threshold:
                    seen.add(pair_key)
                    redundant_pairs.append({
                        "factor_1": f1,
                        "factor_2": f2,
                        "correlation": float(val),
                        "recommendation": "High multi-collinearity: Avoid weighting both factors equally in composite models.",
                    })

    return redundant_pairs
