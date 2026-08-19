"""
Fundamental Engine — Canonical Models & Data Contracts (Phase 7)
================================================================
Defines point-in-time fundamental observations, financial statements,
company metadata, and quality status invariants.

CRITICAL INVARIANTS:
1. REPORT PERIOD != PUBLICATION DATE != MARKET AVAILABILITY DATE.
2. An observation is NEVER visible to calculations or backtests before publication_timestamp.
3. Missing values remain None (UNAVAILABLE). 0 is preserved as a valid numeric quantity (e.g. Debt = 0).
4. No fabricated financial data.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional


class DataStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"
    RESTATED = "RESTATED"


class StatementType(str, Enum):
    INCOME_STATEMENT = "INCOME_STATEMENT"
    BALANCE_SHEET = "BALANCE_SHEET"
    CASH_FLOW = "CASH_FLOW"


class StatementFrequency(str, Enum):
    ANNUAL = "ANNUAL"
    QUARTERLY = "QUARTERLY"
    TRAILING_TWELVE_MONTHS = "TTM"


@dataclass
class FundamentalObservation:
    """
    Atomic point-in-time financial observation.
    Strictly records period bounds and publication timestamp to prevent lookahead bias.
    """
    symbol: str
    metric: str
    value: Optional[float]
    unit: str = "INR_CRORES"  # INR_CRORES, PERCENT, RATIO, PER_SHARE
    currency: str = "INR"
    period_start: Optional[str] = None       # e.g. "2024-04-01"
    period_end: Optional[str] = None         # e.g. "2025-03-31"
    publication_timestamp: int = 0           # Unix timestamp (seconds) when officially public
    source: str = "AUTHENTIC_PROVIDER"       # YAHOO, NSE_FILING, AUDITED_ANNUAL_REPORT, FIXTURE
    source_timestamp: int = 0                # Unix timestamp when ingested into APEX
    data_status: DataStatus = DataStatus.AVAILABLE
    restated_flag: bool = False
    revision_timestamp: Optional[int] = None
    notes: Optional[str] = None

    def is_visible_at(self, as_of_timestamp: int) -> bool:
        """Point-in-time lookahead safeguard: only visible if published on or before as_of_timestamp."""
        if self.publication_timestamp <= 0:
            return False
        return self.publication_timestamp <= as_of_timestamp


@dataclass
class NormalizedIncomeStatement:
    """Standardized GAAP / IndAS Income Statement."""
    symbol: str
    period_end: str
    publication_timestamp: int
    frequency: StatementFrequency
    revenue: Optional[float] = None
    ebitda: Optional[float] = None
    ebit: Optional[float] = None
    operating_profit: Optional[float] = None
    interest_expense: Optional[float] = None
    tax_expense: Optional[float] = None
    net_profit: Optional[float] = None
    eps: Optional[float] = None
    shares_outstanding: Optional[float] = None
    data_status: DataStatus = DataStatus.AVAILABLE
    is_restated: bool = False


@dataclass
class NormalizedBalanceSheet:
    """Standardized GAAP / IndAS Balance Sheet."""
    symbol: str
    period_end: str
    publication_timestamp: int
    frequency: StatementFrequency
    cash_and_equivalents: Optional[float] = None
    short_term_investments: Optional[float] = None
    total_current_assets: Optional[float] = None
    total_assets: Optional[float] = None
    short_term_debt: Optional[float] = None
    long_term_debt: Optional[float] = None
    total_debt: Optional[float] = None
    net_debt: Optional[float] = None
    total_current_liabilities: Optional[float] = None
    total_liabilities: Optional[float] = None
    shareholders_equity: Optional[float] = None
    working_capital: Optional[float] = None
    data_status: DataStatus = DataStatus.AVAILABLE
    is_restated: bool = False


@dataclass
class NormalizedCashFlow:
    """Standardized GAAP / IndAS Cash Flow Statement."""
    symbol: str
    period_end: str
    publication_timestamp: int
    frequency: StatementFrequency
    operating_cash_flow: Optional[float] = None
    capex: Optional[float] = None
    free_cash_flow: Optional[float] = None
    investing_cash_flow: Optional[float] = None
    financing_cash_flow: Optional[float] = None
    dividends_paid: Optional[float] = None
    net_change_in_cash: Optional[float] = None
    data_status: DataStatus = DataStatus.AVAILABLE
    is_restated: bool = False


@dataclass
class CompanyProfile:
    """Company descriptive and classification metadata."""
    symbol: str
    company_name: str
    sector: str
    industry: str
    market_cap_crores: Optional[float] = None
    shares_outstanding: Optional[float] = None
    listing_date: Optional[str] = None
    description: Optional[str] = None
    isin: Optional[str] = None
    data_status: DataStatus = DataStatus.AVAILABLE


@dataclass
class FundamentalEvent:
    """Point-in-time corporate and filing event."""
    event_id: str
    symbol: str
    event_type: str  # EARNINGS_RELEASE, DIVIDEND_DECLARATION, BONUS_ISSUE, AUDIT_QUALIFICATION
    announcement_timestamp: int
    effective_timestamp: int
    title: str
    details: Dict[str, Any] = field(default_factory=dict)
    source: str = "NSE_FILING"
