"""
APEX Unit & Integration Test Suite: MCX Instrument Resolution
=============================================================
Tests for Milestone 2: Phase 3A
Covers:
- `backend/app/market_data/mcx/models.py`
- `backend/app/market_data/mcx/master_service.py`
- `backend/app/market_data/mcx/contract_resolver.py`
- `backend/app/market_data/mcx/registry_bridge.py`
- `backend/app/market/instruments.py` (MCX token support & dynamic resolution)
- `backend/app/market_data/instrument_registry.py` (All 16 commodities & dynamic fields)
"""

import os
import sys

# Ensure repository root is on sys.path for direct pytest invocation
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import gzip
import json
import time
import math
import tempfile
import datetime
import pytest
from unittest.mock import patch, MagicMock

from backend.app.market_data.mcx.models import (
    ContractTerm,
    MCXContract,
    CommodityResolution,
)
from backend.app.market_data.mcx.master_service import (
    MCXInstrumentMasterService,
    mcx_master_service,
)
from backend.app.market_data.mcx.contract_resolver import (
    ActiveContractResolver,
    active_contract_resolver,
    TARGET_COMMODITIES,
    IST,
)
from backend.app.market_data.mcx.registry_bridge import (
    MCXRegistryBridge,
    sync_mcx_contracts,
)
from backend.app.market_data.instrument_registry import (
    UniversalInstrumentRegistry,
    instrument_registry,
    InstrumentDefinition,
    Exchange,
    AssetClass,
)
from backend.app.market.instruments import (
    get_instrument_key,
    get_symbol_from_key,
    register_instrument,
    INSTRUMENT_MAP,
)


# ==============================================================================
# 1. Models & Data Contract Tests
# ==============================================================================

class TestMCXModels:
    """Verify MCXContract, ContractTerm, and CommodityResolution models."""

    def test_contract_term_enum_values(self):
        assert ContractTerm.NEAR_MONTH == "NEAR_MONTH"
        assert ContractTerm.NEXT_MONTH == "NEXT_MONTH"
        assert ContractTerm.FAR_MONTH == "FAR_MONTH"

    def test_mcx_contract_creation_and_attributes(self):
        contract = MCXContract(
            instrument_key="MCX_FO|495213",
            exchange_token="495213",
            trading_symbol="GOLD FUT 04 DEC 26",
            commodity_symbol="GOLD",
            term=ContractTerm.NEAR_MONTH,
            expiry_timestamp=1796322599000,
            expiry_date="2026-12-04",
            last_trading_date="2026-12-04 23:59:59",
            days_to_expiry=18,
            is_in_rollover_window=False,
            lot_size=1,
            qty_multiplier=100.0,
            price_quote_unit="GRMS",
            tick_size=100.0,
            tick_size_rupees=1.0,
        )
        assert contract.instrument_key == "MCX_FO|495213"
        assert contract.exchange_token == "495213"
        assert contract.term == ContractTerm.NEAR_MONTH
        assert contract.tick_size == 100.0
        assert contract.tick_size_rupees == 1.0
        assert contract.is_in_rollover_window is False

        # Test dictionary serialization
        d = contract.to_dict()
        assert d["instrument_key"] == "MCX_FO|495213"
        assert d["term"] == "NEAR_MONTH"

    def test_mcx_contract_rollover_window_flag(self):
        # Days <= 5 should be in rollover window
        c_rollover = MCXContract(
            instrument_key="MCX_FO|573422",
            exchange_token="573422",
            trading_symbol="CRUDEOIL FUT 19 NOV 26",
            commodity_symbol="CRUDEOIL",
            term=ContractTerm.NEAR_MONTH,
            expiry_timestamp=1794936923000,
            expiry_date="2026-11-19",
            last_trading_date="2026-11-19 23:59:59",
            days_to_expiry=3,
            is_in_rollover_window=True,
            lot_size=100,
            qty_multiplier=100.0,
            price_quote_unit="BBL",
            tick_size=100.0,
            tick_size_rupees=1.0,
        )
        assert c_rollover.is_in_rollover_window is True

    def test_commodity_resolution_model(self):
        near = MCXContract(
            instrument_key="MCX_FO|495213",
            exchange_token="495213",
            trading_symbol="GOLD FUT 04 DEC 26",
            commodity_symbol="GOLD",
            term=ContractTerm.NEAR_MONTH,
            expiry_timestamp=1796322599000,
            expiry_date="2026-12-04",
            last_trading_date="2026-12-04 23:59:59",
            days_to_expiry=18,
            is_in_rollover_window=False,
            lot_size=1,
            qty_multiplier=100.0,
            price_quote_unit="GRMS",
            tick_size=100.0,
            tick_size_rupees=1.0,
        )
        nxt = MCXContract(
            instrument_key="MCX_FO|495215",
            exchange_token="495215",
            trading_symbol="GOLD FUT 05 FEB 27",
            commodity_symbol="GOLD",
            term=ContractTerm.NEXT_MONTH,
            expiry_timestamp=1801765799000,
            expiry_date="2027-02-05",
            last_trading_date="2027-02-05 23:59:59",
            days_to_expiry=81,
            is_in_rollover_window=False,
            lot_size=1,
            qty_multiplier=100.0,
            price_quote_unit="GRMS",
            tick_size=100.0,
            tick_size_rupees=1.0,
        )

        res = CommodityResolution(
            commodity_code="GOLD",
            display_name="Gold 1kg Futures (MCX)",
            unit="₹/10g",
            near_contract=near,
            next_contract=nxt,
            far_contract=None,
            available_contracts_count=2,
            resolved_at=time.time(),
        )
        assert res.commodity_code == "GOLD"
        assert res.near_contract.instrument_key == "MCX_FO|495213"
        assert res.next_contract.instrument_key == "MCX_FO|495215"
        assert res.far_contract is None
        assert res.available_contracts_count == 2
        d = res.to_dict()
        assert d["near_contract"]["term"] == "NEAR_MONTH"


# ==============================================================================
# 2. Master Service (Download, Decompression, Caching) Tests
# ==============================================================================

class TestMCXMasterService:
    """Verify Master Service download, in-memory decompression, and caching."""

    def test_cache_validity_logic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "test_mcx.json")
            service = MCXInstrumentMasterService(cache_path=cache_file, ttl_hours=20.0)

            # Not created yet
            assert service.is_cache_valid() is False
            assert service.get_cache_age_hours() is None

            # Create fresh file
            with open(cache_file, "w") as f:
                json.dump([{"segment": "MCX_FO"}], f)

            assert service.is_cache_valid() is True
            assert service.get_cache_age_hours() < 0.1

            # Make file 25 hours old
            old_time = time.time() - (25 * 3600)
            os.utime(cache_file, (old_time, old_time))
            assert service.is_cache_valid() is False
            assert service.get_cache_age_hours() >= 25.0

    def test_decompression_and_caching(self):
        sample_data = [
            {
                "segment": "MCX_FO",
                "instrument_type": "FUT",
                "instrument_key": "MCX_FO|12345",
                "exchange_token": "12345",
                "trading_symbol": "GOLD FUT 04 DEC 26",
                "expiry": 1796322599000,
            },
            {
                "segment": "MCX_FO",
                "instrument_type": "CE",
                "instrument_key": "MCX_FO|99999",
                "exchange_token": "99999",
                "trading_symbol": "GOLD 04 DEC 26 CE 135000",
                "expiry": 1796322599000,
            },
        ]
        gzipped = gzip.compress(json.dumps(sample_data).encode("utf-8"))

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "cached_master.json")
            service = MCXInstrumentMasterService(cache_path=cache_file)

            # Test decompress_and_parse
            parsed = service._decompress_and_parse(gzipped)
            assert len(parsed) == 2

            # Test write to cache
            service._write_to_cache(parsed)
            assert os.path.exists(cache_file)

            # Test read from cache
            from_cache = service._read_from_cache()
            assert len(from_cache) == 2
            assert from_cache[0]["instrument_key"] == "MCX_FO|12345"

    def test_get_futures_contracts_filtering(self):
        sample_data = [
            {"segment": "MCX_FO", "instrument_type": "FUT", "instrument_key": "MCX_FO|1"},
            {"segment": "MCX_FO", "instrument_type": "CE", "instrument_key": "MCX_FO|2"},
            {"segment": "MCX_FO", "instrument_type": "PE", "instrument_key": "MCX_FO|3"},
            {"segment": "NSE_FO", "instrument_type": "FUT", "instrument_key": "NSE_FO|4"},
            {"segment": "MCX_FO", "instrument_type": "FUT", "instrument_key": "MCX_FO|5"},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "master.json")
            with open(cache_file, "w") as f:
                json.dump(sample_data, f)

            service = MCXInstrumentMasterService(cache_path=cache_file)
            futures = service.get_futures_contracts_sync()
            assert len(futures) == 2
            assert futures[0]["instrument_key"] == "MCX_FO|1"
            assert futures[1]["instrument_key"] == "MCX_FO|5"

    def test_fallback_to_stale_cache_on_download_failure(self):
        sample_data = [{"segment": "MCX_FO", "instrument_type": "FUT", "instrument_key": "MCX_FO|STALE_TEST"}]
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "stale_master.json")
            with open(cache_file, "w") as f:
                json.dump(sample_data, f)

            # Age file by 30 hours
            old_time = time.time() - (30 * 3600)
            os.utime(cache_file, (old_time, old_time))

            service = MCXInstrumentMasterService(cache_path=cache_file, master_url="https://invalid.upstox.fake.url/MCX.json.gz")

            # Should fall back to stale cache rather than failing
            records = service.get_master_records_sync(force=True)
            assert len(records) == 1
            assert records[0]["instrument_key"] == "MCX_FO|STALE_TEST"


# ==============================================================================
# 3. Contract Resolver Tests: All 16 Commodities & Rollover
# ==============================================================================

class TestActiveContractResolver:
    """Verify ActiveContractResolver resolves all 16 target commodities correctly."""

    def test_alias_normalization(self):
        assert ActiveContractResolver.normalize_commodity_code("GOLD") == "GOLD"
        assert ActiveContractResolver.normalize_commodity_code("GOLD_MCX") == "GOLD"
        assert ActiveContractResolver.normalize_commodity_code("gold mini") == "GOLDM"
        assert ActiveContractResolver.normalize_commodity_code("GOLD_MINI") == "GOLDM"
        assert ActiveContractResolver.normalize_commodity_code("CRUDE") == "CRUDEOIL"
        assert ActiveContractResolver.normalize_commodity_code("CRUDE OIL") == "CRUDEOIL"
        assert ActiveContractResolver.normalize_commodity_code("CRUDEOIL_MCX") == "CRUDEOIL"
        assert ActiveContractResolver.normalize_commodity_code("NATGAS") == "NATURALGAS"
        assert ActiveContractResolver.normalize_commodity_code("NATGAS_MCX") == "NATURALGAS"
        assert ActiveContractResolver.normalize_commodity_code("NATURALGAS_MCX") == "NATURALGAS"
        assert ActiveContractResolver.normalize_commodity_code("NATGASMINI_MCX") == "NATGASMINI"
        assert ActiveContractResolver.normalize_commodity_code("ALUMINUM") == "ALUMINIUM"
        assert ActiveContractResolver.normalize_commodity_code("ALUMINI_MCX") == "ALUMINI"
        assert ActiveContractResolver.normalize_commodity_code("ZINCMINI_MCX") == "ZINCMINI"
        assert ActiveContractResolver.normalize_commodity_code("LEADMINI_MCX") == "LEADMINI"
        assert ActiveContractResolver.normalize_commodity_code("NICKEL_MCX") == "NICKEL"
        assert ActiveContractResolver.normalize_commodity_code("UNKNOWN_XYZ") is None

    def test_resolve_all_16_target_commodities_from_live_master(self):
        """Verify that all 16 commodities resolve successfully from master dataset."""
        resolutions = active_contract_resolver.resolve_all_sync()
        assert len(resolutions) == 16

        expected_codes = [
            "GOLD", "GOLDM", "SILVER", "SILVERM", "CRUDEOIL", "CRUDEOILM",
            "NATURALGAS", "NATGASMINI", "COPPER", "ALUMINIUM", "ALUMINI",
            "ZINC", "ZINCMINI", "LEAD", "LEADMINI", "NICKEL"
        ]

        for code in expected_codes:
            assert code in resolutions, f"Missing resolution for {code}"
            res = resolutions[code]
            assert res.commodity_code == code
            assert res.near_contract is not None
            assert res.near_contract.term == ContractTerm.NEAR_MONTH
            assert res.near_contract.instrument_key.startswith("MCX_FO|")
            assert res.near_contract.lot_size > 0
            assert res.near_contract.qty_multiplier > 0
            assert res.near_contract.tick_size_rupees > 0
            assert res.available_contracts_count >= 1

    def test_commodity_specifications_table_accuracy(self):
        """Verify empirical specifications match Survey 1 §1.2."""
        resolutions = active_contract_resolver.resolve_all_sync()

        # Check Gold specs
        gold = resolutions["GOLD"].near_contract
        assert gold.lot_size == 1
        assert gold.qty_multiplier == 100.0
        assert gold.price_quote_unit == "GRMS"
        assert gold.tick_size == 100.0
        assert gold.tick_size_rupees == 1.0

        # Check Gold Mini specs
        goldm = resolutions["GOLDM"].near_contract
        assert goldm.lot_size == 100
        assert goldm.qty_multiplier == 10.0
        assert goldm.price_quote_unit == "GRMS"
        assert goldm.tick_size == 100.0
        assert goldm.tick_size_rupees == 1.0

        # Check Silver specs
        silver = resolutions["SILVER"].near_contract
        assert silver.lot_size == 30
        assert silver.qty_multiplier == 30.0
        assert silver.price_quote_unit == "KGS"
        assert silver.tick_size == 100.0
        assert silver.tick_size_rupees == 1.0

        # Check Silver Mini specs
        silverm = resolutions["SILVERM"].near_contract
        assert silverm.lot_size == 5
        assert silverm.qty_multiplier == 5.0
        assert silverm.price_quote_unit == "KGS"

        # Check Crude Oil specs
        crude = resolutions["CRUDEOIL"].near_contract
        assert crude.lot_size == 100
        assert crude.qty_multiplier == 100.0
        assert crude.price_quote_unit == "BBL"
        assert crude.tick_size == 100.0
        assert crude.tick_size_rupees == 1.0

        # Check Natural Gas specs
        natgas = resolutions["NATURALGAS"].near_contract
        assert natgas.lot_size == 1250
        assert natgas.qty_multiplier == 1250.0
        assert natgas.price_quote_unit == "mmBtu"
        assert natgas.tick_size == 10.0
        assert natgas.tick_size_rupees == 0.10

        # Check Copper specs
        copper = resolutions["COPPER"].near_contract
        assert copper.lot_size == 2500
        assert copper.qty_multiplier == 2500.0
        assert copper.price_quote_unit == "KGS"
        assert copper.tick_size == 5.0
        assert copper.tick_size_rupees == 0.05

        # Check Aluminium specs
        alum = resolutions["ALUMINIUM"].near_contract
        assert alum.lot_size == 5
        assert alum.qty_multiplier == 5000.0
        assert alum.tick_size == 5.0
        assert alum.tick_size_rupees == 0.05

    def test_automatic_contract_rollover_advancement(self):
        """
        Verify that when as_of_ms advances past the front contract's expiry,
        the resolver automatically advances Near to the next contract.
        """
        sample_futures = [
            {
                "segment": "MCX_FO",
                "instrument_type": "FUT",
                "instrument_key": "MCX_FO|C1",
                "exchange_token": "C1",
                "trading_symbol": "CRUDEOIL FUT 19 NOV 26",
                "expiry": 1000000,
                "lot_size": 100,
                "qty_multiplier": 100.0,
                "price_quote_unit": "BBL",
                "tick_size": 100.0,
            },
            {
                "segment": "MCX_FO",
                "instrument_type": "FUT",
                "instrument_key": "MCX_FO|C2",
                "exchange_token": "C2",
                "trading_symbol": "CRUDEOIL FUT 18 DEC 26",
                "expiry": 2000000,
                "lot_size": 100,
                "qty_multiplier": 100.0,
                "price_quote_unit": "BBL",
                "tick_size": 100.0,
            },
            {
                "segment": "MCX_FO",
                "instrument_type": "FUT",
                "instrument_key": "MCX_FO|C3",
                "exchange_token": "C3",
                "trading_symbol": "CRUDEOIL FUT 19 JAN 27",
                "expiry": 3000000,
                "lot_size": 100,
                "qty_multiplier": 100.0,
                "price_quote_unit": "BBL",
                "tick_size": 100.0,
            },
        ]

        resolver = ActiveContractResolver()

        # Case 1: as_of_ms before C1 expiry
        res_before = resolver.resolve_commodity_sync("CRUDEOIL", futures_records=sample_futures, as_of_ms=500000)
        assert res_before.near_contract.instrument_key == "MCX_FO|C1"
        assert res_before.next_contract.instrument_key == "MCX_FO|C2"
        assert res_before.far_contract.instrument_key == "MCX_FO|C3"
        assert res_before.available_contracts_count == 3

        # Case 2: as_of_ms AFTER C1 expiry (C1 has expired)
        res_after = resolver.resolve_commodity_sync("CRUDEOIL", futures_records=sample_futures, as_of_ms=1500000)
        assert res_after.near_contract.instrument_key == "MCX_FO|C2"  # Automatically advanced!
        assert res_after.next_contract.instrument_key == "MCX_FO|C3"
        assert res_after.far_contract is None
        assert res_after.available_contracts_count == 2

    def test_rollover_window_detection(self):
        """Verify days_to_expiry <= 5 triggers is_in_rollover_window = True."""
        sample_futures = [
            {
                "segment": "MCX_FO",
                "instrument_type": "FUT",
                "instrument_key": "MCX_FO|C_NEAR",
                "exchange_token": "C_NEAR",
                "trading_symbol": "CRUDEOIL FUT 19 NOV 26",
                "expiry": 1000 * 86400 * 1000,  # Day 1000
                "lot_size": 100,
                "qty_multiplier": 100.0,
                "price_quote_unit": "BBL",
                "tick_size": 100.0,
            }
        ]
        resolver = ActiveContractResolver()

        # Day 996 (4 days to expiry) -> in rollover window
        as_of_4d = (1000 - 4) * 86400 * 1000
        res_4d = resolver.resolve_commodity_sync("CRUDEOIL", futures_records=sample_futures, as_of_ms=as_of_4d)
        assert res_4d.near_contract.days_to_expiry == 4
        assert res_4d.near_contract.is_in_rollover_window is True

        # Day 990 (10 days to expiry) -> NOT in rollover window
        as_of_10d = (1000 - 10) * 86400 * 1000
        res_10d = resolver.resolve_commodity_sync("CRUDEOIL", futures_records=sample_futures, as_of_ms=as_of_10d)
        assert res_10d.near_contract.days_to_expiry == 10
        assert res_10d.near_contract.is_in_rollover_window is False

    @pytest.mark.asyncio
    async def test_async_resolution(self):
        """Verify async resolve_commodity and resolve_all work properly."""
        res = await active_contract_resolver.resolve_commodity("GOLD")
        assert res is not None
        assert res.commodity_code == "GOLD"
        assert res.near_contract.instrument_key == "MCX_FO|495213"

        all_res = await active_contract_resolver.resolve_all()
        assert len(all_res) == 16


# ==============================================================================
# 4. Registry Bridge & Universal Instrument Registry Tests
# ==============================================================================

class TestRegistryBridge:
    """Verify bridging into UniversalInstrumentRegistry and INSTRUMENT_MAP."""

    def test_sync_mcx_contracts_populates_registry(self):
        # Run sync
        resolutions = sync_mcx_contracts()
        assert len(resolutions) == 16

        # Check that GOLD_MCX in registry has live instrument_key
        gold_def = instrument_registry.get_by_id("GOLD_MCX")
        assert gold_def is not None
        assert gold_def.instrument_key == "MCX_FO|495213"
        assert gold_def.is_tradable is True
        assert gold_def.expiry_date == "2026-12-04"
        assert gold_def.near_trading_symbol == "GOLD FUT 04 DEC 26"
        assert gold_def.lot_size == 1
        assert gold_def.contract_multiplier == 100.0

        # Check CRUDEOIL_MCX
        crude_def = instrument_registry.get_by_id("CRUDEOIL_MCX")
        assert crude_def is not None
        assert crude_def.instrument_key == "MCX_FO|573422"
        assert crude_def.is_tradable is True

        # Check Minis exist in registry
        for mini_id in ["GOLDM_MCX", "SILVERM_MCX", "CRUDEOILM_MCX", "NATGASMINI_MCX", "ALUMINI_MCX", "ZINCMINI_MCX", "LEADMINI_MCX"]:
            m_def = instrument_registry.get_by_id(mini_id)
            assert m_def is not None, f"Mini definition missing: {mini_id}"
            assert m_def.instrument_key.startswith("MCX_FO|")

    def test_instruments_map_updated_with_mcx_tokens(self):
        # Verify get_instrument_key resolves commodity names directly
        assert get_instrument_key("GOLD") == "MCX_FO|495213"
        assert get_instrument_key("GOLD_MCX") == "MCX_FO|495213"
        assert get_instrument_key("CRUDEOIL") == "MCX_FO|573422"
        assert get_instrument_key("CRUDEOIL_MCX") == "MCX_FO|573422"
        assert get_instrument_key("SILVER") == "MCX_FO|495214"
        assert get_instrument_key("NATURALGAS") == "MCX_FO|574319"
        assert get_instrument_key("NATGAS") == "MCX_FO|574319"
        assert get_instrument_key("COPPER") == "MCX_FO|578634"


# ==============================================================================
# 5. instruments.py Token Validation & MCX Support Tests
# ==============================================================================

class TestInstrumentsModule:
    """Verify instruments.py allows MCX_FO| tokens and maps symbols."""

    def test_mcx_token_not_rejected(self):
        # Passing raw instrument key directly must NOT return None
        assert get_instrument_key("MCX_FO|495213") == "MCX_FO|495213"
        assert get_instrument_key("MCX_FO|573422") == "MCX_FO|573422"
        assert get_instrument_key("MCX_FO|CUSTOM99") == "MCX_FO|CUSTOM99"

    def test_nse_and_bse_tokens_still_supported(self):
        # Ensure no regression for NSE/BSE tokens
        assert get_instrument_key("NSE_EQ|INE002A01018") == "NSE_EQ|INE002A01018"
        assert get_instrument_key("BSE_EQ|500325") == "BSE_EQ|500325"

    def test_get_symbol_from_key_for_mcx(self):
        sym = get_symbol_from_key("MCX_FO|495213")
        assert sym in ["GOLD", "GOLD_MCX", "GOLD FUT 04 DEC 26"]

    def test_register_instrument_helper(self):
        custom_key = "MCX_FO|999888"
        register_instrument("TEST_COMMODITY", {
            "instrument_key": custom_key,
            "exchange": "MCX",
            "segment": "MCX_FO",
            "instrument_type": "FUT",
            "display_name": "Test Commodity",
        })
        assert get_instrument_key("TEST_COMMODITY") == custom_key


# ==============================================================================
# 6. Edge Cases & Robustness Tests
# ==============================================================================

class TestEdgeCases:
    """Verify edge case handling."""

    def test_empty_futures_list_returns_none(self):
        resolver = ActiveContractResolver()
        res = resolver.resolve_commodity_sync("GOLD", futures_records=[])
        assert res is None

    def test_all_contracts_expired_returns_none(self):
        sample_expired = [
            {
                "segment": "MCX_FO",
                "instrument_type": "FUT",
                "instrument_key": "MCX_FO|EXPIRED",
                "exchange_token": "EXPIRED",
                "trading_symbol": "GOLD FUT 04 DEC 20",
                "expiry": 1000,
            }
        ]
        resolver = ActiveContractResolver()
        res = resolver.resolve_commodity_sync("GOLD", futures_records=sample_expired, as_of_ms=2000)
        assert res is None

    def test_single_active_contract_handled(self):
        sample_single = [
            {
                "segment": "MCX_FO",
                "instrument_type": "FUT",
                "instrument_key": "MCX_FO|SINGLE1",
                "exchange_token": "SINGLE1",
                "trading_symbol": "NICKEL FUT 18 NOV 26",
                "expiry": 2000,
                "lot_size": 250,
                "qty_multiplier": 250.0,
                "price_quote_unit": "KGS",
                "tick_size": 10.0,
            }
        ]
        resolver = ActiveContractResolver()
        res = resolver.resolve_commodity_sync("NICKEL", futures_records=sample_single, as_of_ms=1000)
        assert res is not None
        assert res.near_contract.instrument_key == "MCX_FO|SINGLE1"
        assert res.next_contract is None
        assert res.far_contract is None
        assert res.available_contracts_count == 1

    def test_corrupt_cache_file_recovery(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "corrupt.json")
            with open(cache_file, "w") as f:
                f.write("NOT_VALID_JSON{{{")

            service = MCXInstrumentMasterService(cache_path=cache_file)
            assert service.is_cache_valid() is True  # File exists and recent
            # Reading corrupt cache raises ValueError/JSONDecodeError
            with pytest.raises(Exception):
                service._read_from_cache()
