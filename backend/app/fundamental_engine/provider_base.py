"""
Fundamental Engine — Provider Base Abstraction (Phase 7)
========================================================
Defines the provider-agnostic interface for fundamental financial statements,
company metadata, observations, and corporate events.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from backend.app.fundamental_engine.models import (
    FundamentalObservation,
    NormalizedIncomeStatement,
    NormalizedBalanceSheet,
    NormalizedCashFlow,
    CompanyProfile,
    FundamentalEvent,
    StatementFrequency,
)


class FundamentalDataProvider(ABC):
    """
    Abstract interface for fundamental data providers.
    All implementations must strictly preserve publication timestamps.
    """

    @abstractmethod
    async def get_company_profile(self, symbol: str) -> Optional[CompanyProfile]:
        """Fetch descriptive company metadata and sector classification."""
        pass

    @abstractmethod
    async def get_income_statements(
        self,
        symbol: str,
        frequency: StatementFrequency = StatementFrequency.ANNUAL,
        limit: int = 5,
    ) -> List[NormalizedIncomeStatement]:
        """Fetch historical normalized income statements sorted chronologically by period_end."""
        pass

    @abstractmethod
    async def get_balance_sheets(
        self,
        symbol: str,
        frequency: StatementFrequency = StatementFrequency.ANNUAL,
        limit: int = 5,
    ) -> List[NormalizedBalanceSheet]:
        """Fetch historical normalized balance sheets sorted chronologically by period_end."""
        pass

    @abstractmethod
    async def get_cash_flows(
        self,
        symbol: str,
        frequency: StatementFrequency = StatementFrequency.ANNUAL,
        limit: int = 5,
    ) -> List[NormalizedCashFlow]:
        """Fetch historical normalized cash flows sorted chronologically by period_end."""
        pass

    @abstractmethod
    async def get_point_in_time_observations(
        self,
        symbol: str,
        metrics: List[str],
        as_of_timestamp: int,
    ) -> List[FundamentalObservation]:
        """Fetch all point-in-time fundamental observations published on or before as_of_timestamp."""
        pass

    @abstractmethod
    async def get_sector_peers(self, symbol: str) -> List[str]:
        """Fetch list of peer symbols in the same sector/industry."""
        pass

    @abstractmethod
    async def get_fundamental_events(
        self,
        symbol: str,
        as_of_timestamp: Optional[int] = None,
    ) -> List[FundamentalEvent]:
        """Fetch historical corporate events published on or before as_of_timestamp."""
        pass
