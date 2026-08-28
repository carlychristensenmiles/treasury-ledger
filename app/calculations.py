"""
The core calculation this whole product exists for:

    state_tax_exempt_amount = ordinary_dividends (1099-DIV Box 1a) x (fund's
    published % of income derived from direct U.S. government obligations)

Kept in its own module, deliberately tiny and dependency-light, so it can be
unit tested precisely and so the logic is never duplicated between routes.
"""
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Fund


@dataclass
class CalcResult:
    matched: bool
    pct_used: Optional[float]
    exempt_amount: float
    cactny_restricted: bool


def calculate_exempt_amount(
    ordinary_dividends: float,
    fund: Optional[Fund],
    state_mode: str = "ALL",
) -> CalcResult:
    """
    state_mode:
      "ALL"    - most states: apply the fund's published percentage directly.
      "CACTNY" - California / Connecticut / New York: the pass-through of
                 exempt income is only permitted for funds that meet each
                 family's 50%-of-assets-at-every-quarter-end test. If the
                 fund does not meet that threshold, the exempt amount is $0
                 for CA/CT/NY purposes even though the fund does report some
                 government-obligation income.
    """
    if fund is None:
        return CalcResult(matched=False, pct_used=None, exempt_amount=0.0, cactny_restricted=False)

    if state_mode == "CACTNY" and not fund.meets_ca_ct_ny:
        return CalcResult(matched=True, pct_used=fund.pct_govt_obligations, exempt_amount=0.0, cactny_restricted=True)

    exempt = round(ordinary_dividends * (fund.pct_govt_obligations / 100.0), 2)
    return CalcResult(matched=True, pct_used=fund.pct_govt_obligations, exempt_amount=exempt, cactny_restricted=False)


def find_fund(
    db: Session,
    ticker: Optional[str] = None,
    name: Optional[str] = None,
    cusip: Optional[str] = None,
    tax_year: int = 2025,
    fuzzy_threshold: float = 0.82,
) -> Optional[Fund]:
    """
    Look up a Fund by, in order of confidence: exact ticker, exact CUSIP,
    then a fuzzy name match (used mainly for PIMCO and some Fidelity funds,
    whose source tax documents don't publish a ticker symbol at all).
    """
    query = db.query(Fund).filter(Fund.tax_year == tax_year)

    if ticker:
        ticker_norm = ticker.strip().upper()
        fund = query.filter(Fund.ticker == ticker_norm).first()
        if fund:
            return fund

    if cusip:
        cusip_norm = cusip.strip().upper()
        fund = query.filter(Fund.cusip == cusip_norm).first()
        if fund:
            return fund

    if name:
        name_norm = name.strip().lower()
        best_fund, best_score = None, 0.0
        for candidate in query.all():
            score = SequenceMatcher(None, name_norm, candidate.name.lower()).ratio()
            if score > best_score:
                best_fund, best_score = candidate, score
        if best_fund and best_score >= fuzzy_threshold:
            return best_fund

    return None
