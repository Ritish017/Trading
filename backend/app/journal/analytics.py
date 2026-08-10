from typing import List, Dict, Any

def compute_journal_statistics(journal_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes performance and behavioral metrics over journal logs.
    """
    if not journal_entries:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "best_performing_setup": "N/A",
            "worst_performing_setup": "N/A"
        }

    total = len(journal_entries)
    winners = [e for e in journal_entries if e.get("pnl", 0) > 0]
    losers = [e for e in journal_entries if e.get("pnl", 0) <= 0]

    win_rate = round(len(winners) / total * 100, 1)
    gross_profit = sum(e.get("pnl", 0) for e in winners)
    gross_loss = abs(sum(e.get("pnl", 0) for e in losers))

    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)
    avg_win = gross_profit / len(winners) if winners else 0.0
    avg_loss = gross_loss / len(losers) if losers else 0.0
    expectancy = round((win_rate / 100.0 * avg_win) - ((1.0 - win_rate / 100.0) * avg_loss), 2)

    # Group by setup
    setup_pnl = {}
    for e in journal_entries:
        s = e.get("setup_name", "UNCLASSIFIED")
        setup_pnl[s] = setup_pnl.get(s, 0.0) + e.get("pnl", 0)

    best_setup = max(setup_pnl, key=setup_pnl.get) if setup_pnl else "N/A"
    worst_setup = min(setup_pnl, key=setup_pnl.get) if setup_pnl else "N/A"

    return {
        "total_trades": total,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "best_performing_setup": best_setup,
        "worst_performing_setup": worst_setup
    }
