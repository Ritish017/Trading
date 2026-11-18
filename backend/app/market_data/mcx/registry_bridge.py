"""
APEX MCX Universal Instrument Registry Bridge
============================================
Bridges dynamically resolved MCX commodity futures contracts into:
1. `UniversalInstrumentRegistry` (`backend/app/market_data/instrument_registry.py`)
2. Master `INSTRUMENT_MAP` in `backend/app/market/instruments.py`

This ensures that whenever any system component requests a quote or metadata
for 'GOLD', 'GOLD_MCX', 'CRUDEOIL', 'SILVER', etc., it resolves to the verified,
live Upstox `MCX_FO|<token>` key with accurate contract specifications.
"""

import logging
from typing import Dict, Any, Optional

from backend.app.market_data.mcx.models import CommodityResolution
from backend.app.market_data.mcx.contract_resolver import (
    ActiveContractResolver,
    active_contract_resolver,
    TARGET_COMMODITIES,
)
from backend.app.market_data.instrument_registry import (
    UniversalInstrumentRegistry,
    instrument_registry as default_registry,
    InstrumentDefinition,
    Exchange,
    AssetClass,
)
from backend.app.market.instruments import register_instrument

logger = logging.getLogger(__name__)

# Map asset_class string to AssetClass enum
_ASSET_CLASS_MAP = {
    "PRECIOUS_METALS": AssetClass.PRECIOUS_METALS,
    "ENERGY": AssetClass.ENERGY,
    "INDUSTRIAL_METALS": AssetClass.INDUSTRIAL_METALS,
}


class MCXRegistryBridge:
    """
    Coordinates populating registry and instrument lookup tables with
    resolved active MCX futures contracts.
    """

    def __init__(
        self,
        resolver: Optional[ActiveContractResolver] = None,
        registry: Optional[UniversalInstrumentRegistry] = None,
    ):
        self.resolver = resolver or active_contract_resolver
        self.registry = registry or default_registry

    def sync_mcx_contracts_to_registry(
        self,
        resolutions: Optional[Dict[str, CommodityResolution]] = None,
        as_of_ms: Optional[float] = None,
    ) -> Dict[str, CommodityResolution]:
        """
        Synchronously resolve all target commodities and register them into
        both UniversalInstrumentRegistry and instruments.py's INSTRUMENT_MAP.
        """
        if resolutions is None:
            resolutions = self.resolver.resolve_all_sync(as_of_ms=as_of_ms)

        logger.info(f"[REGISTRY BRIDGE] Syncing {len(resolutions)} resolved MCX commodities to registry...")

        for code, res in resolutions.items():
            near = res.near_contract
            spec = TARGET_COMMODITIES.get(code, {})
            inst_id = spec.get("instrument_id", f"{code}_MCX")
            asset_cls = _ASSET_CLASS_MAP.get(spec.get("asset_class", "PRECIOUS_METALS"), AssetClass.INDUSTRIAL_METALS)

            # 1. Update or create InstrumentDefinition in UniversalInstrumentRegistry
            existing_def = self.registry.get_by_id(inst_id)
            if existing_def:
                # Update existing definition with live dynamic fields
                updated_def = existing_def.model_copy(
                    update={
                        "instrument_key": near.instrument_key,
                        "expiry_date": near.expiry_date,
                        "near_trading_symbol": near.trading_symbol,
                        "contract_multiplier": near.qty_multiplier,
                        "lot_size": near.lot_size,
                        "tick_size": near.tick_size_rupees,
                        "is_tradable": True,
                    }
                )
            else:
                updated_def = InstrumentDefinition(
                    instrument_id=inst_id,
                    symbol=code,
                    name=spec.get("display_name", near.trading_symbol),
                    exchange=Exchange.MCX,
                    asset_class=asset_cls,
                    currency="INR",
                    price_unit=spec.get("unit", "INR"),
                    contract_multiplier=near.qty_multiplier,
                    lot_size=near.lot_size,
                    tick_size=near.tick_size_rupees,
                    is_tradable=True,
                    is_benchmark=False,
                    data_source="UPSTOX",
                    trading_calendar="INDIAN_MCX",
                    description=f"{spec.get('display_name', code)} active front contract",
                    instrument_key=near.instrument_key,
                    expiry_date=near.expiry_date,
                    near_trading_symbol=near.trading_symbol,
                )

            self.registry.register(updated_def)

            # Also ensure NATGAS_MCX and NATURALGAS_MCX are both registered if resolving Natural Gas
            if code == "NATURALGAS":
                alt_def = updated_def.model_copy(update={"instrument_id": "NATGAS_MCX"})
                self.registry.register(alt_def)

            # 2. Update INSTRUMENT_MAP in instruments.py
            metadata: Dict[str, Any] = {
                "instrument_key": near.instrument_key,
                "exchange": "MCX",
                "segment": "MCX_FO",
                "instrument_type": "FUT",
                "display_name": res.display_name,
                "trading_symbol": near.trading_symbol,
                "commodity_code": code,
                "expiry_date": near.expiry_date,
                "lot_size": near.lot_size,
                "qty_multiplier": near.qty_multiplier,
                "price_quote_unit": near.price_quote_unit,
                "tick_size": near.tick_size,
                "tick_size_rupees": near.tick_size_rupees,
                "is_in_rollover_window": near.is_in_rollover_window,
                "days_to_expiry": near.days_to_expiry,
            }

            # Register standard aliases
            aliases_to_register = set(spec.get("aliases", []))
            aliases_to_register.add(code)
            aliases_to_register.add(f"{code}_MCX")
            aliases_to_register.add(inst_id)
            aliases_to_register.add(near.trading_symbol)

            for alias in aliases_to_register:
                register_instrument(alias, metadata)

        logger.info(f"[REGISTRY BRIDGE] Successfully bridged {len(resolutions)} commodities.")
        return resolutions

    async def async_sync_mcx_contracts_to_registry(
        self,
        resolutions: Optional[Dict[str, CommodityResolution]] = None,
        as_of_ms: Optional[float] = None,
    ) -> Dict[str, CommodityResolution]:
        """Asynchronously resolve and bridge active MCX contracts."""
        if resolutions is None:
            resolutions = await self.resolver.resolve_all(as_of_ms=as_of_ms)
        return self.sync_mcx_contracts_to_registry(resolutions=resolutions, as_of_ms=as_of_ms)


# Default bridge singleton
mcx_registry_bridge = MCXRegistryBridge()


def sync_mcx_contracts(
    resolver: Optional[ActiveContractResolver] = None,
    registry: Optional[UniversalInstrumentRegistry] = None,
    as_of_ms: Optional[float] = None,
) -> Dict[str, CommodityResolution]:
    """Convenience functional interface for synchronizing MCX contracts."""
    bridge = MCXRegistryBridge(resolver=resolver, registry=registry)
    return bridge.sync_mcx_contracts_to_registry(as_of_ms=as_of_ms)
