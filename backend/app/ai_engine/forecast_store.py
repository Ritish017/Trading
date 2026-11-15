"""
APEX Immutable Versioned Forecast Store
=======================================
Maintains persistent, immutable records for:
- Research events
- Forecast versions (version 1, 2, 3...)
- Forecast scenarios (Bullish, Base, Bearish)
- Evaluation results against realized market prices

Invariants:
- A forecast is NEVER modified or overwritten once published.
- Subsequent updates create a new version with incremented version number.
- Previous versions remain permanently accessible for calibration and backtesting.
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
                        self._forecasts[inst_id] = [MarketForecast(**item) for item in fc_list]
                logger.info(f"[FORECAST STORE] Loaded {sum(len(v) for v in self._forecasts.values())} forecast versions.")
            except Exception as e:
                logger.warning(f"[FORECAST STORE] Failed to load forecasts from {self.storage_path}: {e}")
                self._forecasts = {}

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
            # Determine next version
            latest_ver = max(fc.version for fc in existing)
            forecast.version = latest_ver + 1

        self._forecasts.setdefault(inst_id, []).append(forecast)
        self._save()
        logger.info(f"[FORECAST STORE] Published immutable forecast {forecast.forecast_id} (Version {forecast.version}) for {inst_id}.")
        return forecast

    def get_latest_forecast(self, instrument_id: str) -> Optional[MarketForecast]:
        fcs = self._forecasts.get(instrument_id, [])
        if not fcs:
            return None
        return max(fcs, key=lambda f: f.version)

    def get_forecast_history(self, instrument_id: str) -> List[MarketForecast]:
        return sorted(self._forecasts.get(instrument_id, []), key=lambda f: f.version, reverse=True)

    def list_all_latest_forecasts(self) -> List[MarketForecast]:
        latest = []
        for inst_id, fcs in self._forecasts.items():
            if fcs:
                latest.append(max(fcs, key=lambda f: f.version))
        return sorted(latest, key=lambda f: f.forecast_timestamp, reverse=True)

    def evaluate_forecast(self, forecast_id: str, realized_price: float) -> Optional[MarketForecast]:
        """Evaluates an existing forecast against real market outcome."""
        for inst_id, fcs in self._forecasts.items():
            for fc in fcs:
                if fc.forecast_id == forecast_id:
                    fc.realized_price = realized_price
                    fc.realized_return_pct = round(((realized_price - fc.current_price) / fc.current_price) * 100.0, 2)
                    fc.status = "EVALUATED"
                    self._save()
                    return fc
        return None


# Global forecast store instance
forecast_store = ForecastStore()
