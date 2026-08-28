from app.calculations import calculate_exempt_amount, find_fund


def test_basic_exempt_calculation(sample_funds):
    fund = sample_funds[1]  # BND, 44.06%
    result = calculate_exempt_amount(500.00, fund, state_mode="ALL")
    assert result.matched is True
    assert result.pct_used == 44.06
    assert result.exempt_amount == 220.30
    assert result.cactny_restricted is False


def test_100pct_fund(sample_funds):
    fund = sample_funds[0]  # VUSXX, 100%
    result = calculate_exempt_amount(1000.00, fund, state_mode="ALL")
    assert result.exempt_amount == 1000.00


def test_unmatched_fund_is_zero():
    result = calculate_exempt_amount(300.00, None, state_mode="ALL")
    assert result.matched is False
    assert result.exempt_amount == 0.0


def test_cactny_mode_zeroes_out_non_qualifying_fund(sample_funds):
    fund = sample_funds[1]  # BND does NOT meet CA/CT/NY threshold
    result = calculate_exempt_amount(500.00, fund, state_mode="CACTNY")
    assert result.matched is True
    assert result.cactny_restricted is True
    assert result.exempt_amount == 0.0


def test_cactny_mode_still_applies_for_qualifying_fund(sample_funds):
    fund = sample_funds[0]  # VUSXX meets the threshold
    result = calculate_exempt_amount(1000.00, fund, state_mode="CACTNY")
    assert result.cactny_restricted is False
    assert result.exempt_amount == 1000.00


def test_fidelity_asterisk_inversion_is_already_normalized(sample_funds):
    """
    The Fidelity fund in sample_funds had an asterisk in its source PDF,
    which per Fidelity's own footnote means it did NOT meet the CA/CT/NY
    threshold. This must already be reflected as meets_ca_ct_ny=False on the
    stored Fund -- calculations.py must never re-interpret family-specific
    asterisk conventions itself.
    """
    fund = sample_funds[2]
    assert fund.meets_ca_ct_ny is False
    result = calculate_exempt_amount(1000.00, fund, state_mode="CACTNY")
    assert result.cactny_restricted is True
    assert result.exempt_amount == 0.0

    # Under the normal (non-CA/CT/NY) rule, the fund's percentage still applies in full.
    result_all = calculate_exempt_amount(1000.00, fund, state_mode="ALL")
    assert round(result_all.exempt_amount, 2) == 385.63


def test_find_fund_by_ticker_real(db_session, sample_funds):
    fund = find_fund(db_session, ticker="bnd")  # lowercase input should still match
    assert fund is not None
    assert fund.ticker == "BND"


def test_find_fund_by_cusip(db_session, sample_funds):
    fund = find_fund(db_session, cusip="316069244")
    assert fund is not None
    assert fund.family == "Fidelity"


def test_find_fund_by_fuzzy_name(db_session, sample_funds):
    fund = find_fund(db_session, name="PIMCO Long Term US Government Fund")
    assert fund is not None
    assert fund.family == "PIMCO"


def test_find_fund_no_match_returns_none(db_session, sample_funds):
    fund = find_fund(db_session, ticker="ZZZZ", name="Not A Real Fund At All")
    assert fund is None
