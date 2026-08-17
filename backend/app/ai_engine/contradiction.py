from typing import List, Dict
from backend.app.ai_engine.contracts import DomainAssessment, SignalStance, ContradictionReport

def detect_contradictions(assessments: List[DomainAssessment]) -> ContradictionReport:
    """
    Compares domain analyst assessments and detects conflicting bullish vs bearish signals.
    Excludes UNAVAILABLE domains from neutral consensus.
    """
    active_assessments = [a for a in assessments if a.stance != SignalStance.UNAVAILABLE]
    unavailable_domains = [a.domain for a in assessments if a.stance == SignalStance.UNAVAILABLE]

    if not active_assessments:
        return ContradictionReport(
            has_contradiction=False,
            consensus_stance=SignalStance.UNAVAILABLE,
            conflicting_signals=[],
            synthesis_note="Market data is currently unavailable across evaluated analytical domains."
        )

    bullish_domains = [a.domain for a in active_assessments if a.stance == SignalStance.BULLISH]
    bearish_domains = [a.domain for a in active_assessments if a.stance == SignalStance.BEARISH]
    
    has_conflict = len(bullish_domains) > 0 and len(bearish_domains) > 0
    conflicts: List[str] = []

    unavail_suffix = f" (Unmonitored/Unavailable: {', '.join(unavailable_domains)})" if unavailable_domains else ""

    if has_conflict:
        conflicts.append(f"Bullish stance in [{', '.join(bullish_domains)}] contradicted by Bearish signals in [{', '.join(bearish_domains)}].")
        consensus = SignalStance.MIXED
        synthesis = f"Price and technicals are not fully corroborated across active domains.{unavail_suffix}"
    elif len(bullish_domains) > len(bearish_domains):
        consensus = SignalStance.BULLISH
        synthesis = f"Consensus aligns constructively across active domains.{unavail_suffix}"
    elif len(bearish_domains) > len(bullish_domains):
        consensus = SignalStance.BEARISH
        synthesis = f"Consensus confirms distribution pressure across active domains.{unavail_suffix}"
    else:
        consensus = SignalStance.NEUTRAL
        synthesis = f"Balanced signals across active domains.{unavail_suffix}"

    return ContradictionReport(
        has_contradiction=has_conflict,
        consensus_stance=consensus,
        conflicting_signals=conflicts,
        synthesis_note=synthesis
    )
