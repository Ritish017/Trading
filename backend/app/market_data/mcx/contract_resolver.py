"""
APEX Active MCX Contract Resolver
=================================
Dynamically resolves active Near-Month, Next-Month, and Far-Month commodity futures
contracts from the Upstox MCX Instrument Master dataset.

Key Features:
- Covers all 16 target commodity contracts (Bullion, Energy, Base Metals, and Minis).
- Filters by `expiry >= as_of_ms` (automatic rollover advancement without manual intervention).
- Sorts strictly by ascending `expiry` timestamp.
- Assigns ContractTerm: NEAR_MONTH (index 0), NEXT_MONTH (index 1), FAR_MONTH (index 2).
- Calculates tender/rollover period: `is_in_rollover_window = days_to_expiry <= 5`.
- Full alias resolution (e.g. 'GOLD_MCX', 'GOLD MINI', 'CRUDEOIL_MCX', 'NATGAS').
"""

import math
import time
import datetime
import logging
from typing import List, Dict, Any, Optional

from backend.app.market_data.mcx.models import (
    ContractTerm,
    MCXContract,
    CommodityResolution,
)
from backend.app.market_data.mcx.master_service import (
    MCXInstrumentMasterService,
    mcx_master_service,
)

logger = logging.getLogger(__name__)

# Indian Standard Time (UTC+05:30)
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

# Authoritative specifications for all 16 target MCX commodities
TARGET_COMMODITIES: Dict[str, Dict[str, Any]] = {
    "GOLD": {
        "commodity_code": "GOLD",
        "prefix": "GOLD FUT",
        "display_name": "Gold 1kg Futures (MCX)",
        "unit": "₹/10g",
        "price_quote_unit": "GRMS",
        "asset_class": "PRECIOUS_METALS",
        "instrument_id": "GOLD_MCX",
        "aliases": ["GOLD", "GOLD_MCX", "GOLD FUT", "MCX_GOLD"],
    },
    "GOLDM": {
        "commodity_code": "GOLDM",
        "prefix": "GOLDM FUT",
        "display_name": "Gold Mini Futures (MCX)",
        "unit": "₹/10g",
        "price_quote_unit": "GRMS",
        "asset_class": "PRECIOUS_METALS",
        "instrument_id": "GOLDM_MCX",
        "aliases": ["GOLDM", "GOLD_MINI", "GOLD MINI", "GOLDM_MCX", "MCX_GOLDM"],
    },
    "SILVER": {
        "commodity_code": "SILVER",
        "prefix": "SILVER FUT",
        "display_name": "Silver 30kg Futures (MCX)",
        "unit": "₹/kg",
        "price_quote_unit": "KGS",
        "asset_class": "PRECIOUS_METALS",
        "instrument_id": "SILVER_MCX",
        "aliases": ["SILVER", "SILVER_MCX", "SILVER FUT", "MCX_SILVER"],
    },
    "SILVERM": {
        "commodity_code": "SILVERM",
        "prefix": "SILVERM FUT",
        "display_name": "Silver Mini Futures (MCX)",
        "unit": "₹/kg",
        "price_quote_unit": "KGS",
        "asset_class": "PRECIOUS_METALS",
        "instrument_id": "SILVERM_MCX",
        "aliases": ["SILVERM", "SILVER_MINI", "SILVER MINI", "SILVERM_MCX", "MCX_SILVERM"],
    },
    "CRUDEOIL": {
        "commodity_code": "CRUDEOIL",
        "prefix": "CRUDEOIL FUT",
        "display_name": "Crude Oil Futures (MCX)",
        "unit": "₹/bbl",
        "price_quote_unit": "BBL",
        "asset_class": "ENERGY",
        "instrument_id": "CRUDEOIL_MCX",
        "aliases": ["CRUDEOIL", "CRUDE", "CRUDE OIL", "CRUDEOIL_MCX", "CRUDE_MCX", "MCX_CRUDEOIL"],
    },
    "CRUDEOILM": {
        "commodity_code": "CRUDEOILM",
        "prefix": "CRUDEOILM FUT",
        "display_name": "Crude Oil Mini Futures (MCX)",
        "unit": "₹/bbl",
        "price_quote_unit": "BBL",
        "asset_class": "ENERGY",
        "instrument_id": "CRUDEOILM_MCX",
        "aliases": ["CRUDEOILM", "CRUDE_MINI", "CRUDE OIL MINI", "CRUDEOILM_MCX", "MCX_CRUDEOILM"],
    },
    "NATURALGAS": {
        "commodity_code": "NATURALGAS",
        "prefix": "NATURALGAS FUT",
        "display_name": "Natural Gas Futures (MCX)",
        "unit": "₹/mmBtu",
        "price_quote_unit": "mmBtu",
        "asset_class": "ENERGY",
        "instrument_id": "NATGAS_MCX",
        "aliases": ["NATURALGAS", "NATGAS", "NATURAL GAS", "NATGAS_MCX", "NATURALGAS_MCX", "MCX_NATGAS"],
    },
    "NATGASMINI": {
        "commodity_code": "NATGASMINI",
        "prefix": "NATGASMINI FUT",
        "display_name": "Natural Gas Mini Futures (MCX)",
        "unit": "₹/mmBtu",
        "price_quote_unit": "mmBtu",
        "asset_class": "ENERGY",
        "instrument_id": "NATGASMINI_MCX",
        "aliases": ["NATGASMINI", "NATGAS_MINI", "NATURAL GAS MINI", "NATGASMINI_MCX", "MCX_NATGASMINI"],
    },
    "COPPER": {
        "commodity_code": "COPPER",
        "prefix": "COPPER FUT",
        "display_name": "Copper Futures (MCX)",
        "unit": "₹/kg",
        "price_quote_unit": "KGS",
        "asset_class": "INDUSTRIAL_METALS",
        "instrument_id": "COPPER_MCX",
        "aliases": ["COPPER", "COPPER_MCX", "COPPER FUT", "MCX_COPPER"],
    },
    "ALUMINIUM": {
        "commodity_code": "ALUMINIUM",
        "prefix": "ALUMINIUM FUT",
        "display_name": "Aluminium Futures (MCX)",
        "unit": "₹/kg",
        "price_quote_unit": "KGS",
        "asset_class": "INDUSTRIAL_METALS",
        "instrument_id": "ALUMINIUM_MCX",
        "aliases": ["ALUMINIUM", "ALUMINUM", "ALUMINIUM_MCX", "ALUMINUM_MCX", "MCX_ALUMINIUM"],
    },
    "ALUMINI": {
        "commodity_code": "ALUMINI",
        "prefix": "ALUMINI FUT",
        "display_name": "Aluminium Mini Futures (MCX)",
        "unit": "₹/kg",
        "price_quote_unit": "KGS",
        "asset_class": "INDUSTRIAL_METALS",
        "instrument_id": "ALUMINI_MCX",
        "aliases": ["ALUMINI", "ALUMINIUM_MINI", "ALUMINIUM MINI", "ALUMINI_MCX", "ALUMINUM MINI"],
    },
    "ZINC": {
        "commodity_code": "ZINC",
        "prefix": "ZINC FUT",
        "display_name": "Zinc Futures (MCX)",
        "unit": "₹/kg",
        "price_quote_unit": "KGS",
        "asset_class": "INDUSTRIAL_METALS",
        "instrument_id": "ZINC_MCX",
        "aliases": ["ZINC", "ZINC_MCX", "ZINC FUT", "MCX_ZINC"],
    },
    "ZINCMINI": {
        "commodity_code": "ZINCMINI",
        "prefix": "ZINCMINI FUT",
        "display_name": "Zinc Mini Futures (MCX)",
        "unit": "₹/kg",
        "price_quote_unit": "KGS",
        "asset_class": "INDUSTRIAL_METALS",
        "instrument_id": "ZINCMINI_MCX",
        "aliases": ["ZINCMINI", "ZINC_MINI", "ZINC MINI", "ZINCMINI_MCX"],
    },
    "LEAD": {
        "commodity_code": "LEAD",
        "prefix": "LEAD FUT",
        "display_name": "Lead Futures (MCX)",
        "unit": "₹/kg",
        "price_quote_unit": "KGS",
        "asset_class": "INDUSTRIAL_METALS",
        "instrument_id": "LEAD_MCX",
        "aliases": ["LEAD", "LEAD_MCX", "LEAD FUT", "MCX_LEAD"],
    },
    "LEADMINI": {
        "commodity_code": "LEADMINI",
        "prefix": "LEADMINI FUT",
        "display_name": "Lead Mini Futures (MCX)",
        "unit": "₹/kg",
        "price_quote_unit": "KGS",
        "asset_class": "INDUSTRIAL_METALS",
        "instrument_id": "LEADMINI_MCX",
        "aliases": ["LEADMINI", "LEAD_MINI", "LEAD MINI", "LEADMINI_MCX"],
    },
    "NICKEL": {
        "commodity_code": "NICKEL",
        "prefix": "NICKEL FUT",
        "display_name": "Nickel Futures (MCX)",
        "unit": "₹/kg",
        "price_quote_unit": "KGS",
        "asset_class": "INDUSTRIAL_METALS",
        "instrument_id": "NICKEL_MCX",
        "aliases": ["NICKEL", "NICKEL_MCX", "NICKEL FUT", "MCX_NICKEL"],
    },
}

# Reverse mapping from alias to canonical commodity_code
_ALIAS_TO_CODE: Dict[str, str] = {}
for code, spec in TARGET_COMMODITIES.items():
    _ALIAS_TO_CODE[code.upper()] = code
    for alias in spec.get("aliases", []):
        _ALIAS_TO_CODE[alias.upper()] = code


class ActiveContractResolver:
    """
    Resolves active MCX futures contracts for all target commodities.
    """
    TARGET_COMMODITIES = TARGET_COMMODITIES

    def __init__(self, master_service: Optional[MCXInstrumentMasterService] = None):
        self.master_service = master_service or mcx_master_service

    @staticmethod
    def is_target_commodity(symbol: str) -> bool:
        """Check whether a symbol or alias corresponds to a supported MCX commodity."""
        return ActiveContractResolver.normalize_commodity_code(symbol) is not None

    @staticmethod
    def normalize_commodity_code(symbol: str) -> Optional[str]:
        """
        Normalize any commodity alias, trading symbol prefix, or instrument ID
        to its canonical commodity code (e.g., 'GOLD_MCX' -> 'GOLD').
        """
        if not symbol:
            return None
        clean = symbol.strip().upper()
        if clean in _ALIAS_TO_CODE:
            return _ALIAS_TO_CODE[clean]
        # Also handle prefixes like 'GOLD FUT 04 DEC 26'
        for code, spec in TARGET_COMMODITIES.items():
            if clean.startswith(spec["prefix"]):
                return code
        return None

    @staticmethod
    def get_commodity_config(symbol: str) -> Optional[Dict[str, Any]]:
        """Get commodity specification dictionary for any symbol or alias."""
        code = ActiveContractResolver.normalize_commodity_code(symbol)
        if code and code in TARGET_COMMODITIES:
            return TARGET_COMMODITIES[code]
        return None

    def _build_mcx_contract(
        self,
        raw: Dict[str, Any],
        term: ContractTerm,
        as_of_ms: float,
        commodity_symbol: str,
    ) -> MCXContract:
        """Construct a validated MCXContract model from raw master dict."""
        inst_key = raw.get("instrument_key") or f"MCX_FO|{raw.get('exchange_token', '')}"
        ex_token = str(raw.get("exchange_token", ""))
        ts_symbol = raw.get("trading_symbol", "")
        expiry_ts = int(raw.get("expiry", 0))

        # Format dates in IST
        expiry_dt = datetime.datetime.fromtimestamp(expiry_ts / 1000.0, tz=IST)
        expiry_date = expiry_dt.strftime("%Y-%m-%d")

        ltd_ts = raw.get("last_trading_date")
        if ltd_ts:
            ltd_dt = datetime.datetime.fromtimestamp(int(ltd_ts) / 1000.0, tz=IST)
            last_trading_date = ltd_dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            last_trading_date = f"{expiry_date} 23:59:59"

        # Days to expiry: ceiling of remaining milliseconds / (86400 * 1000)
        remaining_ms = expiry_ts - as_of_ms
        if remaining_ms <= 0:
            days_to_expiry = 0
        else:
            days_to_expiry = math.ceil(remaining_ms / (86400.0 * 1000.0))

        # Tender period: MCX imposes physical delivery margins within 5 days of expiry
        is_in_rollover = days_to_expiry <= 5

        lot_size = int(raw.get("lot_size", 1))
        qty_multiplier = float(raw.get("qty_multiplier", 1.0))
        price_quote_unit = str(raw.get("price_quote_unit", ""))
        tick_size_paise = float(raw.get("tick_size", 5.0))
        tick_size_rupees = tick_size_paise / 100.0

        return MCXContract(
            instrument_key=inst_key,
            exchange_token=ex_token,
            trading_symbol=ts_symbol,
            commodity_symbol=commodity_symbol,
            term=term,
            expiry_timestamp=expiry_ts,
            expiry_date=expiry_date,
            last_trading_date=last_trading_date,
            days_to_expiry=days_to_expiry,
            is_in_rollover_window=is_in_rollover,
            lot_size=lot_size,
            qty_multiplier=qty_multiplier,
            price_quote_unit=price_quote_unit,
            tick_size=tick_size_paise,
            tick_size_rupees=tick_size_rupees,
        )

    def resolve_commodity_sync(
        self,
        commodity_input: str,
        futures_records: Optional[List[Dict[str, Any]]] = None,
        as_of_ms: Optional[float] = None,
    ) -> Optional[CommodityResolution]:
        """
        Synchronously resolve active Near, Next, and Far contracts for a commodity.

        Args:
            commodity_input: Symbol, code, or alias (e.g. 'GOLD', 'GOLD_MCX', 'CRUDEOIL')
            futures_records: Optional pre-filtered list of futures dicts (if None, fetched from master)
            as_of_ms: Optional reference timestamp in ms (defaults to current time * 1000)
        """
        code = self.normalize_commodity_code(commodity_input)
        if not code or code not in TARGET_COMMODITIES:
            logger.warning(f"[CONTRACT RESOLVER] Unknown commodity code for input '{commodity_input}'")
            return None

        spec = TARGET_COMMODITIES[code]
        prefix = spec["prefix"]

        if as_of_ms is None:
            as_of_ms = time.time() * 1000.0

        if futures_records is None:
            futures_records = self.master_service.get_futures_contracts_sync()

        # Filter futures matching prefix and expiry >= as_of_ms
        active = [
            f for f in futures_records
            if f.get("trading_symbol", "").startswith(prefix)
            and f.get("expiry", 0) >= as_of_ms
        ]

        if not active:
            logger.warning(
                f"[CONTRACT RESOLVER] No active unexpired futures found for '{code}' (prefix '{prefix}', as_of_ms={as_of_ms})"
            )
            return None

        # Sort ascending by expiry timestamp
        active.sort(key=lambda x: x.get("expiry", 0))

        # Build Near contract (index 0)
        near = self._build_mcx_contract(active[0], ContractTerm.NEAR_MONTH, as_of_ms, code)

        # Build Next contract (index 1) if present
        next_c = None
        if len(active) > 1:
            next_c = self._build_mcx_contract(active[1], ContractTerm.NEXT_MONTH, as_of_ms, code)

        # Build Far contract (index 2) if present
        far_c = None
        if len(active) > 2:
            far_c = self._build_mcx_contract(active[2], ContractTerm.FAR_MONTH, as_of_ms, code)

        return CommodityResolution(
            commodity_code=code,
            display_name=spec["display_name"],
            unit=spec["unit"],
            near_contract=near,
            next_contract=next_c,
            far_contract=far_c,
            available_contracts_count=len(active),
            resolved_at=time.time(),
        )

    async def resolve_commodity(
        self,
        commodity_input: str,
        futures_records: Optional[List[Dict[str, Any]]] = None,
        as_of_ms: Optional[float] = None,
    ) -> Optional[CommodityResolution]:
        """
        Asynchronously resolve active Near, Next, and Far contracts for a commodity.
        """
        if futures_records is None:
            futures_records = await self.master_service.get_futures_contracts()

        return self.resolve_commodity_sync(
            commodity_input=commodity_input,
            futures_records=futures_records,
            as_of_ms=as_of_ms,
        )

    def resolve_all_sync(
        self,
        futures_records: Optional[List[Dict[str, Any]]] = None,
        as_of_ms: Optional[float] = None,
    ) -> Dict[str, CommodityResolution]:
        """
        Synchronously resolve active contracts for ALL 16 target commodities.
        Returns a dict mapping commodity_code -> CommodityResolution.
        """
        if futures_records is None:
            futures_records = self.master_service.get_futures_contracts_sync()

        if as_of_ms is None:
            as_of_ms = time.time() * 1000.0

        results: Dict[str, CommodityResolution] = {}
        for code in TARGET_COMMODITIES:
            res = self.resolve_commodity_sync(
                commodity_input=code,
                futures_records=futures_records,
                as_of_ms=as_of_ms,
            )
            if res:
                results[code] = res
        return results

    async def resolve_all(
        self,
        futures_records: Optional[List[Dict[str, Any]]] = None,
        as_of_ms: Optional[float] = None,
    ) -> Dict[str, CommodityResolution]:
        """
        Asynchronously resolve active contracts for ALL 16 target commodities.
        Returns a dict mapping commodity_code -> CommodityResolution.
        """
        if futures_records is None:
            futures_records = await self.master_service.get_futures_contracts()

        return self.resolve_all_sync(
            futures_records=futures_records,
            as_of_ms=as_of_ms,
        )

    def get_active_contract(
        self,
        commodity_input: str,
        term: ContractTerm = ContractTerm.NEAR_MONTH,
        as_of_ms: Optional[float] = None,
    ) -> Optional[MCXContract]:
        """Helper to get a specific term contract (NEAR, NEXT, FAR) directly."""
        resolution = self.resolve_commodity_sync(commodity_input, as_of_ms=as_of_ms)
        if not resolution:
            return None
        if term == ContractTerm.NEAR_MONTH:
            return resolution.near_contract
        elif term == ContractTerm.NEXT_MONTH:
            return resolution.next_contract
        elif term == ContractTerm.FAR_MONTH:
            return resolution.far_contract
        return None

    def get_instrument_key(
        self,
        commodity_input: str,
        term: ContractTerm = ContractTerm.NEAR_MONTH,
    ) -> Optional[str]:
        """Directly return the Upstox instrument key (e.g. 'MCX_FO|495213') for a commodity."""
        contract = self.get_active_contract(commodity_input, term=term)
        return contract.instrument_key if contract else None


# Default singleton instance
active_contract_resolver = ActiveContractResolver()
