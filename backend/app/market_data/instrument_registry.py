"""
Universal Instrument Registry & Asset Class Taxonomy
====================================================
Defines the authoritative catalog of tradable instruments and research-only global benchmarks:
- Precious Metals: Gold, Silver, Platinum, Palladium
- Energy: Crude Oil (Brent & WTI), Natural Gas, Heating Oil, Gasoline
- Industrial Metals: Copper, Aluminium, Zinc, Nickel, Lead, Tin
- Agriculture: Wheat, Rice, Cotton, Soybeans, Corn, Sugar, Coffee
- Equities & Indices: NIFTY 50, BANKNIFTY, Bluechips
- Currencies: USD/INR, EUR/USD, GBP/USD, USD/JPY, DXY
- Crypto: BTC/USD, ETH/USD

Strictly preserves exchange units, lot sizes, tick sizes, and distinguishes
tradable contracts (e.g., MCX Gold ₹/10g) from research benchmarks (COMEX Gold $/oz).
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class AssetClass(str, Enum):
    PRECIOUS_METALS = "PRECIOUS_METALS"
    ENERGY = "ENERGY"
    INDUSTRIAL_METALS = "INDUSTRIAL_METALS"
    AGRICULTURE = "AGRICULTURE"
    EQUITY = "EQUITY"
    INDEX = "INDEX"
    CURRENCY = "CURRENCY"
    CRYPTO = "CRYPTO"


class Exchange(str, Enum):
    NSE = "NSE"
    BSE = "BSE"
    MCX = "MCX"
    NCDEX = "NCDEX"
    COMEX = "COMEX"
    NYMEX = "NYMEX"
    ICE = "ICE"
    LME = "LME"
    FOREX = "FOREX"
    GLOBAL_INDEX = "GLOBAL_INDEX"


class InstrumentDefinition(BaseModel):
    instrument_id: str
    symbol: str
    name: str
    exchange: Exchange
    asset_class: AssetClass
    currency: str = "INR"
    price_unit: str
    contract_multiplier: float = 1.0
    lot_size: int = 1
    tick_size: float = 0.05
    is_tradable: bool = False
    is_benchmark: bool = False
    data_source: str = "UPSTOX"
    trading_calendar: str = "INDIAN_MCX"  # INDIAN_MCX, INDIAN_NSE, US_GLOBAL, 24_7
    description: str = ""
    fallback_spot_symbol: Optional[str] = None
    instrument_key: Optional[str] = None
    expiry_date: Optional[str] = None
    near_trading_symbol: Optional[str] = None


# Pre-populated authoritative registry
UNIVERSAL_INSTRUMENTS: List[InstrumentDefinition] = [
    # --- PRECIOUS METALS ---
    InstrumentDefinition(
        instrument_id="GOLD_MCX",
        symbol="GOLD",
        name="Gold 1kg Futures (MCX)",
        exchange=Exchange.MCX,
        asset_class=AssetClass.PRECIOUS_METALS,
        currency="INR",
        price_unit="INR/10g",
        contract_multiplier=100.0,
        lot_size=1,
        tick_size=1.0,
        is_tradable=True,
        is_benchmark=False,
        data_source="UPSTOX",
        trading_calendar="INDIAN_MCX",
        description="Standard 1kg gold futures traded on Multi Commodity Exchange of India.",
        fallback_spot_symbol="XAUUSD",
    ),
    InstrumentDefinition(
        instrument_id="GOLDM_MCX",
        symbol="GOLDM",
        name="Gold Mini Futures (MCX)",
        exchange=Exchange.MCX,
        asset_class=AssetClass.PRECIOUS_METALS,
        currency="INR",
        price_unit="INR/10g",
        contract_multiplier=10.0,
        lot_size=100,
        tick_size=1.0,
        is_tradable=True,
        is_benchmark=False,
        data_source="UPSTOX",
        trading_calendar="INDIAN_MCX",
        description="100g Gold Mini futures traded on Multi Commodity Exchange of India.",
        fallback_spot_symbol="XAUUSD",
    ),
    InstrumentDefinition(
        instrument_id="XAUUSD",
        symbol="XAU/USD",
        name="Spot Gold (International Benchmark)",
        exchange=Exchange.FOREX,
        asset_class=AssetClass.PRECIOUS_METALS,
        currency="USD",
        price_unit="USD/troy_oz",
        contract_multiplier=1.0,
        lot_size=1,
        tick_size=0.01,
        is_tradable=False,
        is_benchmark=True,
        data_source="YAHOO",
        trading_calendar="US_GLOBAL",
        description="Global spot gold reference price in US Dollars per troy ounce.",
    ),
    InstrumentDefinition(
        instrument_id="SILVER_MCX",
        symbol="SILVER",
        name="Silver 30kg Futures (MCX)",
        exchange=Exchange.MCX,
        asset_class=AssetClass.PRECIOUS_METALS,
        currency="INR",
        price_unit="INR/kg",
        contract_multiplier=30.0,
        lot_size=30,
        tick_size=1.0,
        is_tradable=True,
        is_benchmark=False,
        data_source="UPSTOX",
        trading_calendar="INDIAN_MCX",
        description="30kg silver contract on MCX India.",
        fallback_spot_symbol="XAGUSD",
    ),
    InstrumentDefinition(
        instrument_id="SILVERM_MCX",
        symbol="SILVERM",
        name="Silver Mini Futures (MCX)",
        exchange=Exchange.MCX,
        asset_class=AssetClass.PRECIOUS_METALS,
        currency="INR",
        price_unit="INR/kg",
        contract_multiplier=5.0,
        lot_size=5,
        tick_size=1.0,
        is_tradable=True,
        is_benchmark=False,
        data_source="UPSTOX",
        trading_calendar="INDIAN_MCX",
        description="5kg Silver Mini futures contract on MCX India.",
        fallback_spot_symbol="XAGUSD",
    ),
    InstrumentDefinition(
        instrument_id="XAGUSD",
        symbol="XAG/USD",
        name="Spot Silver (International Benchmark)",
        exchange=Exchange.FOREX,
        asset_class=AssetClass.PRECIOUS_METALS,
        currency="USD",
        price_unit="USD/troy_oz",
        contract_multiplier=1.0,
        lot_size=1,
        tick_size=0.005,
        is_tradable=False,
        is_benchmark=True,
        data_source="YAHOO",
        trading_calendar="US_GLOBAL",
        description="Global spot silver reference price in US Dollars per troy ounce.",
    ),
    InstrumentDefinition(
        instrument_id="PLATINUM_GLOBAL",
        symbol="XPT/USD",
        name="Spot Platinum",
        exchange=Exchange.FOREX,
        asset_class=AssetClass.PRECIOUS_METALS,
        currency="USD",
        price_unit="USD/troy_oz",
        contract_multiplier=1.0,
        lot_size=1,
        tick_size=0.1,
        is_tradable=False,
        is_benchmark=True,
        data_source="YAHOO",
        trading_calendar="US_GLOBAL",
        description="Global spot platinum reference price.",
    ),
    InstrumentDefinition(
        instrument_id="PALLADIUM_GLOBAL",
        symbol="XPD/USD",
        name="Spot Palladium",
        exchange=Exchange.FOREX,
        asset_class=AssetClass.PRECIOUS_METALS,
        currency="USD",
        price_unit="USD/troy_oz",
        contract_multiplier=1.0,
        lot_size=1,
        tick_size=0.1,
        is_tradable=False,
        is_benchmark=True,
        data_source="YAHOO",
        trading_calendar="US_GLOBAL",
        description="Global spot palladium reference price.",
    ),

    # --- ENERGY ---
    InstrumentDefinition(
        instrument_id="CRUDEOIL_MCX",
        symbol="CRUDEOIL",
        name="Crude Oil 100 bbl (MCX)",
        exchange=Exchange.MCX,
        asset_class=AssetClass.ENERGY,
        currency="INR",
        price_unit="INR/bbl",
        contract_multiplier=100.0,
        lot_size=100,
        tick_size=1.0,
        is_tradable=True,
        is_benchmark=False,
        data_source="UPSTOX",
        trading_calendar="INDIAN_MCX",
        description="Light sweet crude oil futures on MCX.",
        fallback_spot_symbol="WTI_NYMEX",
    ),
    InstrumentDefinition(
        instrument_id="CRUDEOILM_MCX",
        symbol="CRUDEOILM",
        name="Crude Oil Mini Futures (MCX)",
        exchange=Exchange.MCX,
        asset_class=AssetClass.ENERGY,
        currency="INR",
        price_unit="INR/bbl",
        contract_multiplier=10.0,
        lot_size=10,
        tick_size=1.0,
        is_tradable=True,
        is_benchmark=False,
        data_source="UPSTOX",
        trading_calendar="INDIAN_MCX",
        description="10 bbl Crude Oil Mini futures on MCX.",
        fallback_spot_symbol="WTI_NYMEX",
    ),
    InstrumentDefinition(
        instrument_id="BRENT_ICE",
        symbol="BZ=F",
        name="Brent Crude Oil Futures (ICE)",
        exchange=Exchange.ICE,
        asset_class=AssetClass.ENERGY,
        currency="USD",
        price_unit="USD/bbl",
        contract_multiplier=1000.0,
        lot_size=1000,
        tick_size=0.01,
        is_tradable=False,
        is_benchmark=True,
        data_source="YAHOO",
        trading_calendar="US_GLOBAL",
        description="International seaborne crude oil benchmark.",
    ),
    InstrumentDefinition(
        instrument_id="WTI_NYMEX",
        symbol="CL=F",
        name="WTI Light Sweet Crude Oil (NYMEX)",
        exchange=Exchange.NYMEX,
        asset_class=AssetClass.ENERGY,
        currency="USD",
        price_unit="USD/bbl",
        contract_multiplier=1000.0,
        lot_size=1000,
        tick_size=0.01,
        is_tradable=False,
        is_benchmark=True,
        data_source="YAHOO",
        trading_calendar="US_GLOBAL",
        description="North American sweet crude benchmark.",
    ),
    InstrumentDefinition(
        instrument_id="NATGAS_MCX",
        symbol="NATURALGAS",
        name="Natural Gas 1250 mmBtu (MCX)",
        exchange=Exchange.MCX,
        asset_class=AssetClass.ENERGY,
        currency="INR",
        price_unit="INR/mmBtu",
        contract_multiplier=1250.0,
        lot_size=1250,
        tick_size=0.1,
        is_tradable=True,
        is_benchmark=False,
        data_source="UPSTOX",
        trading_calendar="INDIAN_MCX",
        description="Natural Gas futures contract traded on MCX.",
        fallback_spot_symbol="NG_NYMEX",
    ),
    InstrumentDefinition(
        instrument_id="NATURALGAS_MCX",
        symbol="NATURALGAS",
        name="Natural Gas 1250 mmBtu (MCX)",
        exchange=Exchange.MCX,
        asset_class=AssetClass.ENERGY,
        currency="INR",
        price_unit="INR/mmBtu",
        contract_multiplier=1250.0,
        lot_size=1250,
        tick_size=0.1,
        is_tradable=True,
        is_benchmark=False,
        data_source="UPSTOX",
        trading_calendar="INDIAN_MCX",
        description="Natural Gas futures contract traded on MCX.",
        fallback_spot_symbol="NG_NYMEX",
    ),
    InstrumentDefinition(
        instrument_id="NATGASMINI_MCX",
        symbol="NATGASMINI",
        name="Natural Gas Mini Futures (MCX)",
        exchange=Exchange.MCX,
        asset_class=AssetClass.ENERGY,
        currency="INR",
        price_unit="INR/mmBtu",
        contract_multiplier=250.0,
        lot_size=250,
        tick_size=0.1,
        is_tradable=True,
        is_benchmark=False,
        data_source="UPSTOX",
        trading_calendar="INDIAN_MCX",
        description="250 mmBtu Natural Gas Mini futures on MCX.",
        fallback_spot_symbol="NG_NYMEX",
    ),
    InstrumentDefinition(
        instrument_id="NG_NYMEX",
        symbol="NG=F",
        name="Henry Hub Natural Gas (NYMEX)",
        exchange=Exchange.NYMEX,
        asset_class=AssetClass.ENERGY,
        currency="USD",
        price_unit="USD/mmBtu",
        contract_multiplier=10000.0,
        lot_size=10000,
        tick_size=0.001,
        is_tradable=False,
        is_benchmark=True,
        data_source="YAHOO",
        trading_calendar="US_GLOBAL",
        description="Henry Hub natural gas benchmark on NYMEX.",
    ),

    # --- INDUSTRIAL METALS ---
    InstrumentDefinition(
        instrument_id="COPPER_MCX",
        symbol="COPPER",
        name="Copper 2500 kg (MCX)",
        exchange=Exchange.MCX,
        asset_class=AssetClass.INDUSTRIAL_METALS,
        currency="INR",
        price_unit="INR/kg",
        contract_multiplier=2500.0,
        lot_size=2500,
        tick_size=0.05,
        is_tradable=True,
        is_benchmark=False,
        data_source="UPSTOX",
        trading_calendar="INDIAN_MCX",
        description="Grade A Copper futures contract on MCX.",
        fallback_spot_symbol="HG_COMEX",
    ),
    InstrumentDefinition(
        instrument_id="HG_COMEX",
        symbol="HG=F",
        name="Copper High Grade (COMEX)",
        exchange=Exchange.COMEX,
        asset_class=AssetClass.INDUSTRIAL_METALS,
        currency="USD",
        price_unit="USD/lb",
        contract_multiplier=25000.0,
        lot_size=25000,
        tick_size=0.0005,
        is_tradable=False,
        is_benchmark=True,
        data_source="YAHOO",
        trading_calendar="US_GLOBAL",
        description="COMEX High Grade Copper benchmark.",
    ),
    InstrumentDefinition(
        instrument_id="ALUMINIUM_MCX",
        symbol="ALUMINIUM",
        name="Aluminium (MCX)",
        exchange=Exchange.MCX,
        asset_class=AssetClass.INDUSTRIAL_METALS,
        currency="INR",
        price_unit="INR/kg",
        contract_multiplier=5000.0,
        lot_size=5000,
        tick_size=0.05,
        is_tradable=True,
        is_benchmark=False,
        data_source="UPSTOX",
        trading_calendar="INDIAN_MCX",
        description="Primary Aluminium contract on MCX.",
    ),
    InstrumentDefinition(
        instrument_id="ALUMINI_MCX",
        symbol="ALUMINI",
        name="Aluminium Mini Futures (MCX)",
        exchange=Exchange.MCX,
        asset_class=AssetClass.INDUSTRIAL_METALS,
        currency="INR",
        price_unit="INR/kg",
        contract_multiplier=1000.0,
        lot_size=1,
        tick_size=0.05,
        is_tradable=True,
        is_benchmark=False,
        data_source="UPSTOX",
        trading_calendar="INDIAN_MCX",
        description="1 MT Aluminium Mini contract on MCX.",
    ),
    InstrumentDefinition(
        instrument_id="ZINC_MCX",
        symbol="ZINC",
        name="Zinc (MCX)",
        exchange=Exchange.MCX,
        asset_class=AssetClass.INDUSTRIAL_METALS,
        currency="INR",
        price_unit="INR/kg",
        contract_multiplier=5000.0,
        lot_size=5000,
        tick_size=0.05,
        is_tradable=True,
        is_benchmark=False,
        data_source="UPSTOX",
        trading_calendar="INDIAN_MCX",
        description="Special High Grade Zinc on MCX.",
    ),
    InstrumentDefinition(
        instrument_id="ZINCMINI_MCX",
        symbol="ZINCMINI",
        name="Zinc Mini Futures (MCX)",
        exchange=Exchange.MCX,
        asset_class=AssetClass.INDUSTRIAL_METALS,
        currency="INR",
        price_unit="INR/kg",
        contract_multiplier=1000.0,
        lot_size=1,
        tick_size=0.05,
        is_tradable=True,
        is_benchmark=False,
        data_source="UPSTOX",
        trading_calendar="INDIAN_MCX",
        description="1 MT Zinc Mini contract on MCX.",
    ),
    InstrumentDefinition(
        instrument_id="LEAD_MCX",
        symbol="LEAD",
        name="Lead Futures (MCX)",
        exchange=Exchange.MCX,
        asset_class=AssetClass.INDUSTRIAL_METALS,
        currency="INR",
        price_unit="INR/kg",
        contract_multiplier=5000.0,
        lot_size=5,
        tick_size=0.05,
        is_tradable=True,
        is_benchmark=False,
        data_source="UPSTOX",
        trading_calendar="INDIAN_MCX",
        description="5 MT Lead futures contract on MCX.",
    ),
    InstrumentDefinition(
        instrument_id="LEADMINI_MCX",
        symbol="LEADMINI",
        name="Lead Mini Futures (MCX)",
        exchange=Exchange.MCX,
        asset_class=AssetClass.INDUSTRIAL_METALS,
        currency="INR",
        price_unit="INR/kg",
        contract_multiplier=1000.0,
        lot_size=1,
        tick_size=0.05,
        is_tradable=True,
        is_benchmark=False,
        data_source="UPSTOX",
        trading_calendar="INDIAN_MCX",
        description="1 MT Lead Mini contract on MCX.",
    ),
    InstrumentDefinition(
        instrument_id="NICKEL_MCX",
        symbol="NICKEL",
        name="Nickel Futures (MCX)",
        exchange=Exchange.MCX,
        asset_class=AssetClass.INDUSTRIAL_METALS,
        currency="INR",
        price_unit="INR/kg",
        contract_multiplier=250.0,
        lot_size=250,
        tick_size=0.10,
        is_tradable=True,
        is_benchmark=False,
        data_source="UPSTOX",
        trading_calendar="INDIAN_MCX",
        description="250 kg Nickel futures contract on MCX.",
    ),

    # --- AGRICULTURE ---
    InstrumentDefinition(
        instrument_id="WHEAT_CBOT",
        symbol="ZW=F",
        name="Chicago SRW Wheat Futures (CBOT)",
        exchange=Exchange.NYMEX,
        asset_class=AssetClass.AGRICULTURE,
        currency="USD",
        price_unit="USD/bushel",
        contract_multiplier=5000.0,
        lot_size=5000,
        tick_size=0.25,
        is_tradable=False,
        is_benchmark=True,
        data_source="YAHOO",
        trading_calendar="US_GLOBAL",
        description="Global wheat benchmark traded on Chicago Board of Trade.",
    ),
    InstrumentDefinition(
        instrument_id="COTTON_MCX",
        symbol="COTTON",
        name="Cotton 25 Bales (MCX)",
        exchange=Exchange.MCX,
        asset_class=AssetClass.AGRICULTURE,
        currency="INR",
        price_unit="INR/bale",
        contract_multiplier=25.0,
        lot_size=25,
        tick_size=10.0,
        is_tradable=True,
        is_benchmark=False,
        data_source="UPSTOX",
        trading_calendar="INDIAN_MCX",
        description="Cotton 29mm candy futures on MCX.",
    ),
    InstrumentDefinition(
        instrument_id="SOYBEAN_CBOT",
        symbol="ZS=F",
        name="Soybean Futures (CBOT)",
        exchange=Exchange.NYMEX,
        asset_class=AssetClass.AGRICULTURE,
        currency="USD",
        price_unit="USD/bushel",
        contract_multiplier=5000.0,
        lot_size=5000,
        tick_size=0.25,
        is_tradable=False,
        is_benchmark=True,
        data_source="YAHOO",
        trading_calendar="US_GLOBAL",
        description="Global soybean benchmark.",
    ),
    InstrumentDefinition(
        instrument_id="CORN_CBOT",
        symbol="ZC=F",
        name="Corn Futures (CBOT)",
        exchange=Exchange.NYMEX,
        asset_class=AssetClass.AGRICULTURE,
        currency="USD",
        price_unit="USD/bushel",
        contract_multiplier=5000.0,
        lot_size=5000,
        tick_size=0.25,
        is_tradable=False,
        is_benchmark=True,
        data_source="YAHOO",
        trading_calendar="US_GLOBAL",
        description="Global corn benchmark.",
    ),
    InstrumentDefinition(
        instrument_id="SUGAR_ICE",
        symbol="SB=F",
        name="Sugar No. 11 (ICE)",
        exchange=Exchange.ICE,
        asset_class=AssetClass.AGRICULTURE,
        currency="USD",
        price_unit="cents/lb",
        contract_multiplier=112000.0,
        lot_size=1,
        tick_size=0.01,
        is_tradable=False,
        is_benchmark=True,
        data_source="YAHOO",
        trading_calendar="US_GLOBAL",
        description="World raw sugar benchmark.",
    ),

    # --- EQUITIES & INDICES ---
    InstrumentDefinition(
        instrument_id="NIFTY50_NSE",
        symbol="NIFTY 50",
        name="NIFTY 50 Benchmark Index",
        exchange=Exchange.NSE,
        asset_class=AssetClass.INDEX,
        currency="INR",
        price_unit="index_points",
        contract_multiplier=25.0,
        lot_size=25,
        tick_size=0.05,
        is_tradable=True,
        is_benchmark=True,
        data_source="UPSTOX",
        trading_calendar="INDIAN_NSE",
        description="Flagship Indian benchmark index of 50 bluechip equities.",
    ),
    InstrumentDefinition(
        instrument_id="BANKNIFTY_NSE",
        symbol="BANKNIFTY",
        name="NIFTY Bank Index",
        exchange=Exchange.NSE,
        asset_class=AssetClass.INDEX,
        currency="INR",
        price_unit="index_points",
        contract_multiplier=15.0,
        lot_size=15,
        tick_size=0.05,
        is_tradable=True,
        is_benchmark=False,
        data_source="UPSTOX",
        trading_calendar="INDIAN_NSE",
        description="Top 12 banking institutions in India.",
    ),

    # --- CURRENCIES & MACRO ---
    InstrumentDefinition(
        instrument_id="USDINR_NSE",
        symbol="USDINR",
        name="USD/INR Currency Pair",
        exchange=Exchange.NSE,
        asset_class=AssetClass.CURRENCY,
        currency="INR",
        price_unit="INR/USD",
        contract_multiplier=1000.0,
        lot_size=1000,
        tick_size=0.0025,
        is_tradable=True,
        is_benchmark=False,
        data_source="UPSTOX",
        trading_calendar="INDIAN_NSE",
        description="US Dollar vs Indian Rupee currency futures.",
    ),
    InstrumentDefinition(
        instrument_id="DXY_INDEX",
        symbol="DX-Y.NYB",
        name="US Dollar Index (DXY)",
        exchange=Exchange.GLOBAL_INDEX,
        asset_class=AssetClass.CURRENCY,
        currency="USD",
        price_unit="points",
        contract_multiplier=1.0,
        lot_size=1,
        tick_size=0.01,
        is_tradable=False,
        is_benchmark=True,
        data_source="YAHOO",
        trading_calendar="US_GLOBAL",
        description="Measure of USD value relative to a basket of major currencies.",
    ),

    # --- CRYPTO ---
    InstrumentDefinition(
        instrument_id="BTCUSD",
        symbol="BTC-USD",
        name="Bitcoin / USD",
        exchange=Exchange.GLOBAL_INDEX,
        asset_class=AssetClass.CRYPTO,
        currency="USD",
        price_unit="USD/BTC",
        contract_multiplier=1.0,
        lot_size=1,
        tick_size=0.01,
        is_tradable=False,
        is_benchmark=True,
        data_source="YAHOO",
        trading_calendar="24_7",
        description="Bitcoin market reference benchmark.",
    ),
]


class UniversalInstrumentRegistry:
    """Singleton registry service providing fast lookup and asset categorization."""

    def __init__(self):
        self._by_id: Dict[str, InstrumentDefinition] = {inst.instrument_id: inst for inst in UNIVERSAL_INSTRUMENTS}
        self._by_symbol: Dict[str, List[InstrumentDefinition]] = {}
        for inst in UNIVERSAL_INSTRUMENTS:
            self._by_symbol.setdefault(inst.symbol.upper(), []).append(inst)

    def get_by_id(self, instrument_id: str) -> Optional[InstrumentDefinition]:
        return self._by_id.get(instrument_id)

    def get_by_symbol(self, symbol: str) -> List[InstrumentDefinition]:
        return self._by_symbol.get(symbol.upper(), [])

    def get_tradable_instruments(self) -> List[InstrumentDefinition]:
        return [inst for inst in self._by_id.values() if inst.is_tradable]

    def get_by_asset_class(self, asset_class: AssetClass) -> List[InstrumentDefinition]:
        return [inst for inst in self._by_id.values() if inst.asset_class == asset_class]

    def list_all(self) -> List[InstrumentDefinition]:
        return list(self._by_id.values())

    def register(self, definition: InstrumentDefinition) -> None:
        self._by_id[definition.instrument_id] = definition
        existing = self._by_symbol.setdefault(definition.symbol.upper(), [])
        for i, item in enumerate(existing):
            if item.instrument_id == definition.instrument_id:
                existing[i] = definition
                return
        existing.append(definition)


# Global singleton instance
instrument_registry = UniversalInstrumentRegistry()
