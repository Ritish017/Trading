from typing import List, Dict
from backend.app.ai_engine.contracts import DomainAssessment, SignalStance, ContradictionReport

def detect_contradictions(assessments: List[DomainAssessment]) -> ContradictionReport:
    """
    Compares domain analyst assessments and detects conflicting bullish vs bearish signals.
    """
    bullish_domains = [a.domain for a in assessments if a.stance == SignalStance.BULLISH]
    bearish_domains = [a.domain for a in assessments if a.stance == SignalStance.BEARISH]
    
    has_conflict = len(bullish_domains) > 0 and len(bearish_domains) > 0
    conflicts: List[str] = []

    if has_conflict:
        conflicts.append(f"Bullish stance in [{', '.join(bullish_domains)}] contradicted by Bearish signals in [{', '.join(bearish_domains)}].")
        consensus = SignalStance.MIXED
        synthesis = f"Price and technicals are not fully corroborated by institutional or derivative flows. Exercise caution around key breakout/breakdown thresholds."
    elif len(bullish_domains) > len(bearish_domains):
        consensus = SignalStance.BULLISH
        synthesis = "Consensus aligns constructively across primary technical, sector, and derivative metrics."
    elif len(bearish_domains) > len(bullish_domains):
        consensus = SignalStance.BEARISH
        synthesis = "Consensus confirms persistent distribution pressure across price, volume, and sector metrics."
    else:
        consensus = SignalStance.NEUTRAL
        synthesis = "Balanced signals across all monitored analytical pillars. Market awaits a decisive catalyst."

    return ContradictionReport(
        has_contradiction=has_conflict,
        consensus_stance=consensus,
        conflicting_signals=conflicts,
        synthesis_note=synthesis
    )
