"""
APEX MCX Instrument Master Ingestion Service
===========================================
Downloads, decompresses, and disk-caches the official Upstox MCX Instrument Master
file (`MCX.json.gz`). Provides filtered access to active commodity futures contracts.

Invariants:
- Cached to `backend/data/cache/mcx_master.json`.
- Refreshed only if cache is missing, older than 20 hours, or `force=True`.
- In-memory gzip decompression.
- Graceful fallback to cached data if network download fails.
- Never introduces mock instruments.
"""

import os
import gzip
import json
import time
import logging
import urllib.request
from typing import List, Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

# Constants
DEFAULT_MCX_MASTER_URL = "https://assets.upstox.com/market-quote/instruments/exchange/MCX.json.gz"
DEFAULT_CACHE_TTL_HOURS = 20.0
HTTP_TIMEOUT_SECONDS = 30.0

# Path resolution: backend/data/cache/mcx_master.json
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DEFAULT_CACHE_DIR = os.path.join(_BACKEND_DIR, "data", "cache")
DEFAULT_CACHE_PATH = os.path.join(DEFAULT_CACHE_DIR, "mcx_master.json")


class MCXInstrumentMasterService:
    """
    Manages fetching, decompressing, disk caching, and querying of the
    Upstox MCX Instrument Master dataset.
    """

    def __init__(
        self,
        cache_path: Optional[str] = None,
        ttl_hours: float = DEFAULT_CACHE_TTL_HOURS,
        master_url: str = DEFAULT_MCX_MASTER_URL,
    ):
        self.cache_path = cache_path or DEFAULT_CACHE_PATH
        self.ttl_seconds = ttl_hours * 3600.0
        self.master_url = master_url
        self._memory_cache: Optional[List[Dict[str, Any]]] = None

    def is_cache_valid(self) -> bool:
        """Check if cached master file exists and is younger than TTL."""
        if not os.path.exists(self.cache_path):
            return False
        try:
            mtime = os.path.getmtime(self.cache_path)
            age = time.time() - mtime
            return age < self.ttl_seconds
        except OSError:
            return False

    def get_cache_age_hours(self) -> Optional[float]:
        """Return the age of the cache file in hours, or None if not cached."""
        if not os.path.exists(self.cache_path):
            return None
        try:
            mtime = os.path.getmtime(self.cache_path)
            return (time.time() - mtime) / 3600.0
        except OSError:
            return None

    def _read_from_cache(self) -> List[Dict[str, Any]]:
        """Read and parse cached JSON from disk."""
        logger.info(f"[MCX MASTER] Loading instruments from disk cache: {self.cache_path}")
        with open(self.cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError(f"Invalid cache format in {self.cache_path}: expected JSON list")
        self._memory_cache = data
        return data

    def _write_to_cache(self, data: List[Dict[str, Any]]) -> None:
        """Write JSON array to disk cache, creating parent directories if needed."""
        cache_dir = os.path.dirname(self.cache_path)
        os.makedirs(cache_dir, exist_ok=True)
        temp_path = f"{self.cache_path}.tmp_{os.getpid()}_{int(time.time())}"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(temp_path, self.cache_path)
        self._memory_cache = data
        logger.info(f"[MCX MASTER] Cached {len(data)} instruments to {self.cache_path}")

    def _decompress_and_parse(self, gzipped_bytes: bytes) -> List[Dict[str, Any]]:
        """Decompress gzipped bytes in-memory and parse JSON."""
        decompressed = gzip.decompress(gzipped_bytes)
        text = decompressed.decode("utf-8")
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("Parsed MCX master is not a list")
        return data

    def get_master_records_sync(self, force: bool = False) -> List[Dict[str, Any]]:
        """
        Synchronously get all master records.
        Uses cached file if valid and force=False.
        Downloads from Upstox CDN if cache is stale or missing.
        Falls back to stale cache if download fails.
        """
        if not force and self.is_cache_valid():
            if self._memory_cache is not None:
                return self._memory_cache
            return self._read_from_cache()

        logger.info(f"[MCX MASTER] Downloading MCX master from {self.master_url} (force={force})...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)",
            "Accept-Encoding": "gzip",
        }

        try:
            req = urllib.request.Request(self.master_url, headers=headers)
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
                raw_bytes = resp.read()
            data = self._decompress_and_parse(raw_bytes)
            self._write_to_cache(data)
            return data
        except Exception as e:
            logger.warning(f"[MCX MASTER] Failed to download master from CDN: {e}")
            if os.path.exists(self.cache_path):
                logger.warning(f"[MCX MASTER] Falling back to existing disk cache at {self.cache_path}")
                return self._read_from_cache()
            raise RuntimeError(
                f"Failed to obtain MCX master dataset: download failed ({e}) and no cache exists at {self.cache_path}"
            ) from e

    async def get_master_records(self, force: bool = False) -> List[Dict[str, Any]]:
        """
        Asynchronously get all master records.
        Uses cached file if valid and force=False.
        Downloads from Upstox CDN if cache is stale or missing.
        Falls back to stale cache if download fails.
        """
        if not force and self.is_cache_valid():
            if self._memory_cache is not None:
                return self._memory_cache
            return self._read_from_cache()

        logger.info(f"[MCX MASTER] Async downloading MCX master from {self.master_url} (force={force})...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)",
            "Accept-Encoding": "gzip",
        }

        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
                resp = await client.get(self.master_url, headers=headers)
                resp.raise_for_status()
                raw_bytes = resp.content
            data = self._decompress_and_parse(raw_bytes)
            self._write_to_cache(data)
            return data
        except Exception as e:
            logger.warning(f"[MCX MASTER] Async download failed: {e}")
            if os.path.exists(self.cache_path):
                logger.warning(f"[MCX MASTER] Falling back to existing disk cache at {self.cache_path}")
                return self._read_from_cache()
            raise RuntimeError(
                f"Failed to obtain MCX master dataset: download failed ({e}) and no cache exists at {self.cache_path}"
            ) from e

    def get_futures_contracts_sync(self, force: bool = False) -> List[Dict[str, Any]]:
        """
        Synchronously return only active MCX futures contracts (`segment == 'MCX_FO'` and `instrument_type == 'FUT'`).
        """
        records = self.get_master_records_sync(force=force)
        return [
            rec for rec in records
            if rec.get("segment") == "MCX_FO" and rec.get("instrument_type") == "FUT"
        ]

    async def get_futures_contracts(self, force: bool = False) -> List[Dict[str, Any]]:
        """
        Asynchronously return only active MCX futures contracts (`segment == 'MCX_FO'` and `instrument_type == 'FUT'`).
        """
        records = await self.get_master_records(force=force)
        return [
            rec for rec in records
            if rec.get("segment") == "MCX_FO" and rec.get("instrument_type") == "FUT"
        ]


# Default singleton instance
mcx_master_service = MCXInstrumentMasterService()
