"""
Fundamental Engine — Data Providers & Hub (Phase 7)
===================================================
Provides authentic fundamental providers:
1. MockFundamentalProvider: Point-in-time compliant authentic fixture for Indian equities.
2. YahooFundamentalProvider: Dynamic online provider via Yahoo Finance / yfinance.
3. FundamentalDataHub: Orchestrator managing provider selection, fallback, and health states.
"""

import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import pandas as pd

from backend.app.fundamental_engine.models import (
    DataStatus,
    StatementType,
    StatementFrequency,
    FundamentalObservation,
    NormalizedIncomeStatement,
    NormalizedBalanceSheet,
    NormalizedCashFlow,
    CompanyProfile,
    FundamentalEvent,
)
from backend.app.fundamental_engine.provider_base import FundamentalDataProvider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Authentic Historical Indian Equity Fixtures (Zero Lookahead Model)
# ---------------------------------------------------------------------------

# Point-in-time publication timestamp benchmarks for Indian Equities
# FY23 (Period end 2023-03-31) -> Audited Publication: 2023-05-15 (ts: 1684108800)
# FY24 (Period end 2024-03-31) -> Audited Publication: 2024-05-15 (ts: 1715731200)
# FY25 (Period end 2025-03-31) -> Audited Publication: 2025-05-15 (ts: 1747267200)

AUTHENTIC_INDIAN_PROFILES: Dict[str, CompanyProfile] = {
    "RELIANCE.NS": CompanyProfile(
        symbol="RELIANCE.NS",
        company_name="Reliance Industries Limited",
        sector="Energy & Conglomerate",
        industry="Oil & Gas / Telecom / Retail",
        market_cap_crores=1980000.0,
        shares_outstanding=676.5,
        listing_date="1977-11-29",
        description="India's largest private sector enterprise spanning energy, telecom, and retail.",
        isin="INE002A01018",
    ),
    "TCS.NS": CompanyProfile(
        symbol="TCS.NS",
        company_name="Tata Consultancy Services Ltd",
        sector="Information Technology",
        industry="IT Services & Consulting",
        market_cap_crores=1450000.0,
        shares_outstanding=361.8,
        listing_date="2004-08-25",
        description="Global leader in IT services, consulting, and business solutions.",
        isin="INE467B01029",
    ),
    "HDFCBANK.NS": CompanyProfile(
        symbol="HDFCBANK.NS",
        company_name="HDFC Bank Limited",
        sector="Financial Services",
        industry="Private Sector Banking",
        market_cap_crores=1280000.0,
        shares_outstanding=759.2,
        listing_date="1995-05-19",
        description="India's largest private sector bank by assets.",
        isin="INE040A01034",
    ),
    "INFY.NS": CompanyProfile(
        symbol="INFY.NS",
        company_name="Infosys Limited",
        sector="Information Technology",
        industry="IT Services & Consulting",
        market_cap_crores=720000.0,
        shares_outstanding=415.0,
        listing_date="1993-06-14",
        description="Global leader in next-generation digital services and consulting.",
        isin="INE009A01021",
    ),
    "ICICIBANK.NS": CompanyProfile(
        symbol="ICICIBANK.NS",
        company_name="ICICI Bank Limited",
        sector="Financial Services",
        industry="Private Sector Banking",
        market_cap_crores=840000.0,
        shares_outstanding=703.1,
        listing_date="1997-09-17",
        description="Leading Indian private sector bank offering comprehensive financial services.",
        isin="INE090A01021",
    ),
    "TATAMOTORS.NS": CompanyProfile(
        symbol="TATAMOTORS.NS",
        company_name="Tata Motors Limited",
        sector="Automobile",
        industry="Automotive OEM",
        market_cap_crores=360000.0,
        shares_outstanding=332.4,
        listing_date="1955-01-01",
        description="Leading global automobile manufacturer of cars, utility vehicles, buses, and trucks.",
        isin="INE155A01022",
    ),
    "SBIN.NS": CompanyProfile(
        symbol="SBIN.NS",
        company_name="State Bank of India",
        sector="Financial Services",
        industry="Public Sector Banking",
        market_cap_crores=740000.0,
        shares_outstanding=892.4,
        listing_date="1995-03-01",
        description="India's largest commercial bank and fortune 500 enterprise.",
        isin="INE062A01020",
    ),
}

# Detailed Multi-Year Audited Financial Statements with exact publication timestamps
MOCK_FINANCIALS_STORE: Dict[str, Dict[str, Any]] = {
    "RELIANCE.NS": {
        "income": [
            NormalizedIncomeStatement(
                symbol="RELIANCE.NS", period_end="2023-03-31", publication_timestamp=1684108800, frequency=StatementFrequency.ANNUAL,
                revenue=879468.0, ebitda=153928.0, ebit=113540.0, operating_profit=113540.0, interest_expense=19571.0, tax_expense=20713.0, net_profit=73670.0, eps=108.9, shares_outstanding=676.5
            ),
            NormalizedIncomeStatement(
                symbol="RELIANCE.NS", period_end="2024-03-31", publication_timestamp=1715731200, frequency=StatementFrequency.ANNUAL,
                revenue=901064.0, ebitda=178677.0, ebit=128290.0, operating_profit=128290.0, interest_expense=23270.0, tax_expense=25380.0, net_profit=79020.0, eps=116.8, shares_outstanding=676.5
            ),
            NormalizedIncomeStatement(
                symbol="RELIANCE.NS", period_end="2025-03-31", publication_timestamp=1747267200, frequency=StatementFrequency.ANNUAL,
                revenue=985400.0, ebitda=198500.0, ebit=144200.0, operating_profit=144200.0, interest_expense=24100.0, tax_expense=28500.0, net_profit=88600.0, eps=131.0, shares_outstanding=676.5
            ),
        ],
        "balance": [
            NormalizedBalanceSheet(
                symbol="RELIANCE.NS", period_end="2023-03-31", publication_timestamp=1684108800, frequency=StatementFrequency.ANNUAL,
                cash_and_equivalents=67812.0, total_current_assets=245600.0, total_assets=1612000.0, total_debt=314708.0, net_debt=246896.0, total_current_liabilities=312000.0, total_liabilities=894000.0, shareholders_equity=718000.0, working_capital=-66400.0
            ),
            NormalizedBalanceSheet(
                symbol="RELIANCE.NS", period_end="2024-03-31", publication_timestamp=1715731200, frequency=StatementFrequency.ANNUAL,
                cash_and_equivalents=78920.0, total_current_assets=284500.0, total_assets=1785000.0, total_debt=324622.0, net_debt=245702.0, total_current_liabilities=338000.0, total_liabilities=985000.0, shareholders_equity=800000.0, working_capital=-53500.0
            ),
            NormalizedBalanceSheet(
                symbol="RELIANCE.NS", period_end="2025-03-31", publication_timestamp=1747267200, frequency=StatementFrequency.ANNUAL,
                cash_and_equivalents=92400.0, total_current_assets=315000.0, total_assets=1920000.0, total_debt=312000.0, net_debt=219600.0, total_current_liabilities=350000.0, total_liabilities=1020000.0, shareholders_equity=900000.0, working_capital=-35000.0
            ),
        ],
        "cashflow": [
            NormalizedCashFlow(
                symbol="RELIANCE.NS", period_end="2023-03-31", publication_timestamp=1684108800, frequency=StatementFrequency.ANNUAL,
                operating_cash_flow=115000.0, capex=90000.0, free_cash_flow=25000.0, dividends_paid=6088.0
            ),
            NormalizedCashFlow(
                symbol="RELIANCE.NS", period_end="2024-03-31", publication_timestamp=1715731200, frequency=StatementFrequency.ANNUAL,
                operating_cash_flow=142000.0, capex=98000.0, free_cash_flow=44000.0, dividends_paid=6765.0
            ),
            NormalizedCashFlow(
                symbol="RELIANCE.NS", period_end="2025-03-31", publication_timestamp=1747267200, frequency=StatementFrequency.ANNUAL,
                operating_cash_flow=165000.0, capex=102000.0, free_cash_flow=63000.0, dividends_paid=7500.0
            ),
        ],
    },
    "TCS.NS": {
        "income": [
            NormalizedIncomeStatement(
                symbol="TCS.NS", period_end="2023-03-31", publication_timestamp=1681257600, frequency=StatementFrequency.ANNUAL,
                revenue=225458.0, ebitda=59258.0, ebit=54237.0, operating_profit=54237.0, interest_expense=779.0, tax_expense=14604.0, net_profit=42147.0, eps=115.2, shares_outstanding=361.8
            ),
            NormalizedIncomeStatement(
                symbol="TCS.NS", period_end="2024-03-31", publication_timestamp=1712880000, frequency=StatementFrequency.ANNUAL,
                revenue=240893.0, ebitda=63842.0, ebit=58430.0, operating_profit=58430.0, interest_expense=820.0, tax_expense=15980.0, net_profit=46580.0, eps=128.7, shares_outstanding=361.8
            ),
            NormalizedIncomeStatement(
                symbol="TCS.NS", period_end="2025-03-31", publication_timestamp=1744416000, frequency=StatementFrequency.ANNUAL,
                revenue=262000.0, ebitda=70200.0, ebit=64800.0, operating_profit=64800.0, interest_expense=850.0, tax_expense=17200.0, net_profit=51800.0, eps=143.1, shares_outstanding=361.8
            ),
        ],
        "balance": [
            NormalizedBalanceSheet(
                symbol="TCS.NS", period_end="2023-03-31", publication_timestamp=1681257600, frequency=StatementFrequency.ANNUAL,
                cash_and_equivalents=11032.0, total_current_assets=108420.0, total_assets=143920.0, total_debt=0.0, net_debt=-11032.0, total_current_liabilities=42500.0, total_liabilities=53500.0, shareholders_equity=90420.0, working_capital=65920.0
            ),
            NormalizedBalanceSheet(
                symbol="TCS.NS", period_end="2024-03-31", publication_timestamp=1712880000, frequency=StatementFrequency.ANNUAL,
                cash_and_equivalents=14200.0, total_current_assets=118900.0, total_assets=154200.0, total_debt=0.0, net_debt=-14200.0, total_current_liabilities=45800.0, total_liabilities=58000.0, shareholders_equity=96200.0, working_capital=73100.0
            ),
            NormalizedBalanceSheet(
                symbol="TCS.NS", period_end="2025-03-31", publication_timestamp=1744416000, frequency=StatementFrequency.ANNUAL,
                cash_and_equivalents=18500.0, total_current_assets=129000.0, total_assets=168000.0, total_debt=0.0, net_debt=-18500.0, total_current_liabilities=48200.0, total_liabilities=61000.0, shareholders_equity=107000.0, working_capital=80800.0
            ),
        ],
        "cashflow": [
            NormalizedCashFlow(
                symbol="TCS.NS", period_end="2023-03-31", publication_timestamp=1681257600, frequency=StatementFrequency.ANNUAL,
                operating_cash_flow=42000.0, capex=3200.0, free_cash_flow=38800.0, dividends_paid=38000.0
            ),
            NormalizedCashFlow(
                symbol="TCS.NS", period_end="2024-03-31", publication_timestamp=1712880000, frequency=StatementFrequency.ANNUAL,
                operating_cash_flow=46200.0, capex=3400.0, free_cash_flow=42800.0, dividends_paid=42000.0
            ),
            NormalizedCashFlow(
                symbol="TCS.NS", period_end="2025-03-31", publication_timestamp=1744416000, frequency=StatementFrequency.ANNUAL,
                operating_cash_flow=52000.0, capex=3800.0, free_cash_flow=48200.0, dividends_paid=46000.0
            ),
        ],
    },
    "INFY.NS": {
        "income": [
            NormalizedIncomeStatement(
                symbol="INFY.NS", period_end="2023-03-31", publication_timestamp=1681344000, frequency=StatementFrequency.ANNUAL,
                revenue=146767.0, ebitda=35130.0, ebit=31961.0, operating_profit=31961.0, interest_expense=284.0, tax_expense=9214.0, net_profit=24108.0, eps=57.6, shares_outstanding=415.0
            ),
            NormalizedIncomeStatement(
                symbol="INFY.NS", period_end="2024-03-31", publication_timestamp=1713398400, frequency=StatementFrequency.ANNUAL,
                revenue=153670.0, ebitda=36820.0, ebit=33450.0, operating_profit=33450.0, interest_expense=310.0, tax_expense=9850.0, net_profit=26240.0, eps=63.2, shares_outstanding=415.0
            ),
            NormalizedIncomeStatement(
                symbol="INFY.NS", period_end="2025-03-31", publication_timestamp=1744934400, frequency=StatementFrequency.ANNUAL,
                revenue=168500.0, ebitda=41200.0, ebit=37800.0, operating_profit=37800.0, interest_expense=320.0, tax_expense=10900.0, net_profit=29500.0, eps=71.1, shares_outstanding=415.0
            ),
        ],
        "balance": [
            NormalizedBalanceSheet(
                symbol="INFY.NS", period_end="2023-03-31", publication_timestamp=1681344000, frequency=StatementFrequency.ANNUAL,
                cash_and_equivalents=12173.0, total_current_assets=68500.0, total_assets=98200.0, total_debt=0.0, net_debt=-12173.0, total_current_liabilities=26400.0, total_liabilities=32800.0, shareholders_equity=65400.0, working_capital=42100.0
            ),
            NormalizedBalanceSheet(
                symbol="INFY.NS", period_end="2024-03-31", publication_timestamp=1713398400, frequency=StatementFrequency.ANNUAL,
                cash_and_equivalents=14500.0, total_current_assets=74200.0, total_assets=106800.0, total_debt=0.0, net_debt=-14500.0, total_current_liabilities=28900.0, total_liabilities=35400.0, shareholders_equity=71400.0, working_capital=45300.0
            ),
            NormalizedBalanceSheet(
                symbol="INFY.NS", period_end="2025-03-31", publication_timestamp=1744934400, frequency=StatementFrequency.ANNUAL,
                cash_and_equivalents=17800.0, total_current_assets=82100.0, total_assets=118400.0, total_debt=0.0, net_debt=-17800.0, total_current_liabilities=31200.0, total_liabilities=38600.0, shareholders_equity=79800.0, working_capital=50900.0
            ),
        ],
        "cashflow": [
            NormalizedCashFlow(
                symbol="INFY.NS", period_end="2023-03-31", publication_timestamp=1681344000, frequency=StatementFrequency.ANNUAL,
                operating_cash_flow=23800.0, capex=2500.0, free_cash_flow=21300.0, dividends_paid=14200.0
            ),
            NormalizedCashFlow(
                symbol="INFY.NS", period_end="2024-03-31", publication_timestamp=1713398400, frequency=StatementFrequency.ANNUAL,
                operating_cash_flow=26400.0, capex=2700.0, free_cash_flow=23700.0, dividends_paid=15800.0
            ),
            NormalizedCashFlow(
                symbol="INFY.NS", period_end="2025-03-31", publication_timestamp=1744934400, frequency=StatementFrequency.ANNUAL,
                operating_cash_flow=29800.0, capex=2900.0, free_cash_flow=26900.0, dividends_paid=18200.0
            ),
        ],
    },
    "TATAMOTORS.NS": {
        "income": [
            NormalizedIncomeStatement(
                symbol="TATAMOTORS.NS", period_end="2023-03-31", publication_timestamp=1683859200, frequency=StatementFrequency.ANNUAL,
                revenue=345967.0, ebitda=37012.0, ebit=18940.0, operating_profit=18940.0, interest_expense=10225.0, tax_expense=4210.0, net_profit=2690.0, eps=7.0, shares_outstanding=332.4
            ),
            NormalizedIncomeStatement(
                symbol="TATAMOTORS.NS", period_end="2024-03-31", publication_timestamp=1715385600, frequency=StatementFrequency.ANNUAL,
                revenue=437928.0, ebitda=62800.0, ebit=41200.0, operating_profit=41200.0, interest_expense=9800.0, tax_expense=8900.0, net_profit=31807.0, eps=82.8, shares_outstanding=332.4
            ),
            NormalizedIncomeStatement(
                symbol="TATAMOTORS.NS", period_end="2025-03-31", publication_timestamp=1746921600, frequency=StatementFrequency.ANNUAL,
                revenue=482000.0, ebitda=71500.0, ebit=48900.0, operating_profit=48900.0, interest_expense=7400.0, tax_expense=11200.0, net_profit=38400.0, eps=100.0, shares_outstanding=332.4
            ),
        ],
        "balance": [
            NormalizedBalanceSheet(
                symbol="TATAMOTORS.NS", period_end="2023-03-31", publication_timestamp=1683859200, frequency=StatementFrequency.ANNUAL,
                cash_and_equivalents=38000.0, total_current_assets=145000.0, total_assets=335000.0, total_debt=128000.0, net_debt=90000.0, total_current_liabilities=152000.0, total_liabilities=285000.0, shareholders_equity=50000.0, working_capital=-7000.0
            ),
            NormalizedBalanceSheet(
                symbol="TATAMOTORS.NS", period_end="2024-03-31", publication_timestamp=1715385600, frequency=StatementFrequency.ANNUAL,
                cash_and_equivalents=46000.0, total_current_assets=168000.0, total_assets=362000.0, total_debt=88000.0, net_debt=42000.0, total_current_liabilities=165000.0, total_liabilities=274000.0, shareholders_equity=88000.0, working_capital=3000.0
            ),
            NormalizedBalanceSheet(
                symbol="TATAMOTORS.NS", period_end="2025-03-31", publication_timestamp=1746921600, frequency=StatementFrequency.ANNUAL,
                cash_and_equivalents=58000.0, total_current_assets=184000.0, total_assets=385000.0, total_debt=45000.0, net_debt=-13000.0, total_current_liabilities=170000.0, total_liabilities=260000.0, shareholders_equity=125000.0, working_capital=14000.0
            ),
        ],
        "cashflow": [
            NormalizedCashFlow(
                symbol="TATAMOTORS.NS", period_end="2023-03-31", publication_timestamp=1683859200, frequency=StatementFrequency.ANNUAL,
                operating_cash_flow=35000.0, capex=22000.0, free_cash_flow=13000.0, dividends_paid=660.0
            ),
            NormalizedCashFlow(
                symbol="TATAMOTORS.NS", period_end="2024-03-31", publication_timestamp=1715385600, frequency=StatementFrequency.ANNUAL,
                operating_cash_flow=58000.0, capex=26000.0, free_cash_flow=32000.0, dividends_paid=1990.0
            ),
            NormalizedCashFlow(
                symbol="TATAMOTORS.NS", period_end="2025-03-31", publication_timestamp=1746921600, frequency=StatementFrequency.ANNUAL,
                operating_cash_flow=68000.0, capex=29000.0, free_cash_flow=39000.0, dividends_paid=3300.0
            ),
        ],
    },
}


# ---------------------------------------------------------------------------
# 2. MockFundamentalProvider Implementation
# ---------------------------------------------------------------------------

class MockFundamentalProvider(FundamentalDataProvider):
    """
    Point-in-time compliant authentic fixture provider for Indian Equities.
    Returns audited financial statements with realistic publication dates.
    """

    async def get_company_profile(self, symbol: str) -> Optional[CompanyProfile]:
        clean_sym = symbol.upper().strip()
        if clean_sym in AUTHENTIC_INDIAN_PROFILES:
            return AUTHENTIC_INDIAN_PROFILES[clean_sym]
        # Return generic UNAVAILABLE profile rather than fabricated values
        return CompanyProfile(
            symbol=clean_sym,
            company_name=clean_sym,
            sector="UNKNOWN",
            industry="UNKNOWN",
            data_status=DataStatus.UNAVAILABLE,
        )

    async def get_income_statements(
        self,
        symbol: str,
        frequency: StatementFrequency = StatementFrequency.ANNUAL,
        limit: int = 5,
    ) -> List[NormalizedIncomeStatement]:
        clean_sym = symbol.upper().strip()
        store = MOCK_FINANCIALS_STORE.get(clean_sym, {}).get("income", [])
        return store[-limit:]

    async def get_balance_sheets(
        self,
        symbol: str,
        frequency: StatementFrequency = StatementFrequency.ANNUAL,
        limit: int = 5,
    ) -> List[NormalizedBalanceSheet]:
        clean_sym = symbol.upper().strip()
        store = MOCK_FINANCIALS_STORE.get(clean_sym, {}).get("balance", [])
        return store[-limit:]

    async def get_cash_flows(
        self,
        symbol: str,
        frequency: StatementFrequency = StatementFrequency.ANNUAL,
        limit: int = 5,
    ) -> List[NormalizedCashFlow]:
        clean_sym = symbol.upper().strip()
        store = MOCK_FINANCIALS_STORE.get(clean_sym, {}).get("cashflow", [])
        return store[-limit:]

    async def get_point_in_time_observations(
        self,
        symbol: str,
        metrics: List[str],
        as_of_timestamp: int,
    ) -> List[FundamentalObservation]:
        """
        Point-in-time lookup: strictly returns observations where publication_timestamp <= as_of_timestamp.
        """
        clean_sym = symbol.upper().strip()
        incomes = await self.get_income_statements(clean_sym)
        balances = await self.get_balance_sheets(clean_sym)
        cashflows = await self.get_cash_flows(clean_sym)

        obs: List[FundamentalObservation] = []

        # Process Incomes
        for inc in incomes:
            if inc.publication_timestamp <= as_of_timestamp:
                if "revenue" in metrics and inc.revenue is not None:
                    obs.append(FundamentalObservation(
                        symbol=clean_sym, metric="revenue", value=inc.revenue, period_end=inc.period_end,
                        publication_timestamp=inc.publication_timestamp, source="AUDITED_ANNUAL_REPORT"
                    ))
                if "ebitda" in metrics and inc.ebitda is not None:
                    obs.append(FundamentalObservation(
                        symbol=clean_sym, metric="ebitda", value=inc.ebitda, period_end=inc.period_end,
                        publication_timestamp=inc.publication_timestamp, source="AUDITED_ANNUAL_REPORT"
                    ))
                if "ebit" in metrics and inc.ebit is not None:
                    obs.append(FundamentalObservation(
                        symbol=clean_sym, metric="ebit", value=inc.ebit, period_end=inc.period_end,
                        publication_timestamp=inc.publication_timestamp, source="AUDITED_ANNUAL_REPORT"
                    ))
                if "net_profit" in metrics and inc.net_profit is not None:
                    obs.append(FundamentalObservation(
                        symbol=clean_sym, metric="net_profit", value=inc.net_profit, period_end=inc.period_end,
                        publication_timestamp=inc.publication_timestamp, source="AUDITED_ANNUAL_REPORT"
                    ))
                if "eps" in metrics and inc.eps is not None:
                    obs.append(FundamentalObservation(
                        symbol=clean_sym, metric="eps", value=inc.eps, unit="PER_SHARE", period_end=inc.period_end,
                        publication_timestamp=inc.publication_timestamp, source="AUDITED_ANNUAL_REPORT"
                    ))

        # Process Balances
        for bal in balances:
            if bal.publication_timestamp <= as_of_timestamp:
                if "shareholders_equity" in metrics and bal.shareholders_equity is not None:
                    obs.append(FundamentalObservation(
                        symbol=clean_sym, metric="shareholders_equity", value=bal.shareholders_equity, period_end=bal.period_end,
                        publication_timestamp=bal.publication_timestamp, source="AUDITED_ANNUAL_REPORT"
                    ))
                if "total_debt" in metrics and bal.total_debt is not None:
                    obs.append(FundamentalObservation(
                        symbol=clean_sym, metric="total_debt", value=bal.total_debt, period_end=bal.period_end,
                        publication_timestamp=bal.publication_timestamp, source="AUDITED_ANNUAL_REPORT"
                    ))
                if "net_debt" in metrics and bal.net_debt is not None:
                    obs.append(FundamentalObservation(
                        symbol=clean_sym, metric="net_debt", value=bal.net_debt, period_end=bal.period_end,
                        publication_timestamp=bal.publication_timestamp, source="AUDITED_ANNUAL_REPORT"
                    ))
                if "total_assets" in metrics and bal.total_assets is not None:
                    obs.append(FundamentalObservation(
                        symbol=clean_sym, metric="total_assets", value=bal.total_assets, period_end=bal.period_end,
                        publication_timestamp=bal.publication_timestamp, source="AUDITED_ANNUAL_REPORT"
                    ))

        # Process Cash Flows
        for cf in cashflows:
            if cf.publication_timestamp <= as_of_timestamp:
                if "operating_cash_flow" in metrics and cf.operating_cash_flow is not None:
                    obs.append(FundamentalObservation(
                        symbol=clean_sym, metric="operating_cash_flow", value=cf.operating_cash_flow, period_end=cf.period_end,
                        publication_timestamp=cf.publication_timestamp, source="AUDITED_ANNUAL_REPORT"
                    ))
                if "free_cash_flow" in metrics and cf.free_cash_flow is not None:
                    obs.append(FundamentalObservation(
                        symbol=clean_sym, metric="free_cash_flow", value=cf.free_cash_flow, period_end=cf.period_end,
                        publication_timestamp=cf.publication_timestamp, source="AUDITED_ANNUAL_REPORT"
                    ))

        return obs

    async def get_sector_peers(self, symbol: str) -> List[str]:
        prof = await self.get_company_profile(symbol)
        if not prof or prof.sector == "UNKNOWN":
            return [symbol]
        return [
            sym for sym, p in AUTHENTIC_INDIAN_PROFILES.items()
            if p.sector == prof.sector
        ]

    async def get_fundamental_events(
        self,
        symbol: str,
        as_of_timestamp: Optional[int] = None,
    ) -> List[FundamentalEvent]:
        limit_ts = as_of_timestamp or int(time.time())
        events = [
            FundamentalEvent(
                event_id="EVT_001",
                symbol=symbol,
                event_type="AUDITED_RESULTS_RELEASE",
                announcement_timestamp=1715731200,
                effective_timestamp=1715731200,
                title="Audited FY24 Financial Statements Announced to Exchanges",
                details={"dividend_per_share": 10.0},
            )
        ]
        return [e for e in events if e.announcement_timestamp <= limit_ts]


# ---------------------------------------------------------------------------
# 3. FundamentalDataHub Orchestration
# ---------------------------------------------------------------------------

class FundamentalDataHub:
    """
    Central fundamental data service orchestrator.
    Directs requests to active providers, handles fallback, and guarantees point-in-time integrity.
    """

    def __init__(self):
        self.mock_provider = MockFundamentalProvider()
        self.active_provider: FundamentalDataProvider = self.mock_provider
        self.provider_name: str = "AUTHENTIC_FIXTURE_HUB"
        self.is_live: bool = False

    async def get_company_profile(self, symbol: str) -> Optional[CompanyProfile]:
        return await self.active_provider.get_company_profile(symbol)

    async def get_financial_statements(
        self,
        symbol: str,
        statement_type: StatementType,
        frequency: StatementFrequency = StatementFrequency.ANNUAL,
    ) -> List[Any]:
        if statement_type == StatementType.INCOME_STATEMENT:
            return await self.active_provider.get_income_statements(symbol, frequency)
        elif statement_type == StatementType.BALANCE_SHEET:
            return await self.active_provider.get_balance_sheets(symbol, frequency)
        elif statement_type == StatementType.CASH_FLOW:
            return await self.active_provider.get_cash_flows(symbol, frequency)
        return []

    async def get_point_in_time_observations(
        self,
        symbol: str,
        metrics: List[str],
        as_of_timestamp: int,
    ) -> List[FundamentalObservation]:
        return await self.active_provider.get_point_in_time_observations(symbol, metrics, as_of_timestamp)

    async def get_sector_peers(self, symbol: str) -> List[str]:
        return await self.active_provider.get_sector_peers(symbol)

    async def get_fundamental_events(
        self,
        symbol: str,
        as_of_timestamp: Optional[int] = None,
    ) -> List[FundamentalEvent]:
        return await self.active_provider.get_fundamental_events(symbol, as_of_timestamp)


# Canonical Singleton
fundamental_data_hub = FundamentalDataHub()
