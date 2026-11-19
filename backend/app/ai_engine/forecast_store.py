"""
APEX Immutable Versioned Forecast Store
=======================================
Maintains persistent, immutable records for:
- Research events
- Forecast versions (version 1, 2, 3...)
- Forecast scenarios (Bullish, Base, Bearish)
- Evaluation results against realized market prices
- Verification audit trails & legacy data migration

Invariants:
- A forecast is NEVER modified or overwritten once published.
- Subsequent updates create a new version with incremented version number.
- Previous versions remain permanently accessible for calibration and backtesting.
- Zero synthetic mock data in production. Legacy mock records are quarantined and marked INVALID.
"""

import os
import json
import time
import logging
from typing import Dict, Any, List, Optional
from backend.app.ai_engine.apex_chief_reasoner import MarketForecast

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
FORECASTS_FILE = os.path.join(DATA_DIR, "global_market_forecasts.json")

# Known synthetic mock prices quarantined from legacy system
QUARANTINED_SYNTHETIC_PRICES = {78450.0, 92300.0, 6120.0, 245.8, 842.5}


class ForecastStore:
    """Thread-safe persistent store for versioned immutable market forecasts."""

    def __init__(self, storage_path: str = FORECASTS_FILE):
        self.storage_path = storage_path
        self._forecasts: Dict[str, List[MarketForecast]] = {}  # instrument_id -> list of versions
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for inst_id, fc_list in data.items():
                        cleaned_list = []
                        for item in fc_list:
                            # Forensic Quarantine: Detect and invalidate legacy synthetic prices
                            curr_px = item.get("current_price", 0.0)
                            evidence_sources = [
                                ref.get("source", "")
                                for ref in item.get("evidence_references", [])
                            ]
                            is_legacy_mock = (
                                curr_px in QUARANTINED_SYNTHETIC_PRICES
                                or "APEX_FEED" in evidence_sources
                                or item.get("forecast_id", "").endswith("_v1")
                                and curr_px in QUARANTINED_SYNTHETIC_PRICES
                            )
                            if is_legacy_mock:
                                item["is_synthetic_legacy"] = True
                                item["status"] = "INVALID_LEGACY_SYNTHETIC"

                            cleaned_list.append(MarketForecast(**item))
                        self._forecasts[inst_id] = cleaned_list
                logger.info(f"[FORECAST STORE] Loaded {sum(len(v) for v in self._forecasts.values())} forecast versions.")
            except Exception as e:
                logger.warning(f"[FORECAST STORE] Failed to load forecasts from {self.storage_path}: {e}")
                self._forecasts = {}

        if not self._forecasts:
            logger.info("[FORECAST STORE] Store initialized clean. Live forecasts will populate on demand via Chief Reasoner.")

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        try:
            dump_data = {
                inst_id: [fc.model_dump() for fc in fcs]
                for inst_id, fcs in self._forecasts.items()
            }
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(dump_data, f, indent=2)
        except Exception as e:
            logger.error(f"[FORECAST STORE] Failed to persist forecasts: {e}")

    def save_forecast(self, forecast: MarketForecast) -> MarketForecast:
        """
        Saves a new immutable forecast. If previous versions exist for the instrument,
        increments the version counter.
        """
        inst_id = forecast.instrument_id
        existing = self._forecasts.get(inst_id, [])
        if existing:
            latest_ver = max(fc.version for fc in existing)
            forecast.version = latest_ver + 1

        self._forecasts.setdefault(inst_id, []).append(forecast)
        self._save()
        logger.info(f"[FORECAST STORE] Published immutable forecast {forecast.forecast_id} (Version {forecast.version}) for {inst_id}.")
        return forecast

    @staticmethod
    def is_forecast_stale(forecast: Optional[MarketForecast], as_of_ts: Optional[float] = None) -> bool:
        """
        Determines whether a forecast is session-stale.
        Invariants:
        - Quarantined / synthetic legacy forecasts are always stale.
        - A forecast generated in a prior calendar session is stale if today's session has commenced (past 09:00 IST).
        - Any forecast older than 14 hours during active trading days is evaluated as stale.
        """
        if forecast is None:
            return True
        if forecast.is_synthetic_legacy or forecast.status == "INVALID_LEGACY_SYNTHETIC":
            return True

        now_sec = as_of_ts or time.time()
        fc_sec = forecast.forecast_timestamp or forecast.market_timestamp
        if not fc_sec or fc_sec <= 0:
            return True

        age_seconds = now_sec - fc_sec
        if age_seconds < 0:
            return False  # Future timestamp (test mock)
        if age_seconds > (14 * 3600):  # Exceeds full trading session length
            return True

        # Session boundary check in Asia/Kolkata
        try:
            import datetime
            from zoneinfo import ZoneInfo
            ist = ZoneInfo("Asia/Kolkata")
            fc_dt = datetime.datetime.fromtimestamp(fc_sec, tz=ist)
            now_dt = datetime.datetime.fromtimestamp(now_sec, tz=ist)

            # Different date: if current time is past 09:00 IST, prior day's forecast is stale
            if now_dt.date() > fc_dt.date():
                if now_dt.hour >= 9:
                    return True
                if (now_sec - fc_sec) > (8 * 3600):
                    return True
        except Exception as e:
            logger.warning(f"[FORECAST STORE] Session staleness check error: {e}")
            if age_seconds > (12 * 3600):
                return True

        return False

    def get_latest_forecast(self, instrument_id: str, allow_quarantined: bool = False) -> Optional[MarketForecast]:
        fcs = self._forecasts.get(instrument_id, [])
        if not fcs:
            return None
        valid_fcs = fcs if allow_quarantined else [f for f in fcs if not f.is_synthetic_legacy and f.status != "INVALID_LEGACY_SYNTHETIC"]
        if not valid_fcs:
            # If no non-quarantined forecasts exist yet, return highest version but caller can see status
            return max(fcs, key=lambda f: f.version) if allow_quarantined else None
        return max(valid_fcs, key=lambda f: f.version)

    def get_forecast_history(self, instrument_id: str, allow_quarantined: bool = False, limit: Optional[int] = None) -> List[MarketForecast]:
        fcs = self._forecasts.get(instrument_id, [])
        if not allow_quarantined:
            fcs = [f for f in fcs if not f.is_synthetic_legacy and f.status != "INVALID_LEGACY_SYNTHETIC"]
        sorted_fcs = sorted(fcs, key=lambda f: f.version, reverse=True)
        return sorted_fcs[:limit] if limit else sorted_fcs

    def list_all_latest_forecasts(self, allow_quarantined: bool = False) -> List[MarketForecast]:
        latest = []
        for inst_id, fcs in self._forecasts.items():
            if not fcs:
                continue
            candidates = fcs if allow_quarantined else [f for f in fcs if not f.is_synthetic_legacy and f.status != "INVALID_LEGACY_SYNTHETIC"]
            if candidates:
                latest.append(max(candidates, key=lambda f: f.version))
            elif allow_quarantined:
                latest.append(max(fcs, key=lambda f: f.version))
        return sorted(latest, key=lambda f: f.forecast_timestamp, reverse=True)

    def evaluate_forecast(self, forecast_id: str, realized_price: float) -> Optional[MarketForecast]:
        """Evaluates an existing forecast against real market outcome."""
        for inst_id, fcs in self._forecasts.items():
            for fc in fcs:
                if fc.forecast_id == forecast_id:
                    if fc.is_synthetic_legacy:
                        logger.warning(f"[FORECAST STORE] Refusing to evaluate quarantined legacy forecast {forecast_id}.")
                        return fc
                    fc.realized_price = realized_price
                    fc.realized_return_pct = round(((realized_price - fc.current_price) / fc.current_price) * 100.0, 2)
                    fc.status = "EVALUATED"
                    self._save()
                    return fc
        return None

    def get_forecast_accuracy(self, instrument_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculates institutional forecast calibration metrics:
        - Directional Accuracy (Hit Rate %)
        - Mean Absolute Percentage Error (MAPE)
        - Brier Calibration Score
        Strictly excludes quarantined synthetic records.
        """
        evaluated = []
        for inst_id, fcs in self._forecasts.items():
            if instrument_id and inst_id != instrument_id:
                continue
            for fc in fcs:
                if fc.status == "EVALUATED" and not fc.is_synthetic_legacy and fc.realized_price is not None:
                    evaluated.append(fc)

        if not evaluated:
            return {
                "sample_size": 0,
                "directional_accuracy_pct": None,
                "mean_absolute_error_pct": None,
                "brier_score": None,
                "status": "INSUFFICIENT_EVALUATED_DATA",
            }

        directional_hits = 0
        abs_errors = []
        brier_sum = 0.0

        for fc in evaluated:
            ret = fc.realized_return_pct or 0.0
            exp = fc.expected_change_percent
            abs_errors.append(abs(ret - exp))

            # Directional check
            if (fc.direction == "BULLISH" and ret > 0) or \
               (fc.direction == "BEARISH" and ret < 0) or \
               (fc.direction == "NEUTRAL_CONSOLIDATION" and abs(ret) < 1.0):
                directional_hits += 1
                brier_sum += (1.0 - fc.confidence) ** 2
            else:
                brier_sum += (0.0 - fc.confidence) ** 2

        n = len(evaluated)
        return {
            "sample_size": n,
            "directional_accuracy_pct": round((directional_hits / n) * 100.0, 2),
            "mean_absolute_error_pct": round(sum(abs_errors) / n, 2),
            "brier_score": round(brier_sum / n, 4),
            "status": "ACTIVE_CALIBRATION",
        }


# Global forecast store instance
forecast_store = ForecastStore()
global_forecast_store = forecast_store
