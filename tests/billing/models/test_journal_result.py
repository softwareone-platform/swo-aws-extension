from decimal import Decimal

import pytest

from swo_aws_extension.billing.models.journal_result import (
    AgreementJournalResult,
    AuthorizationJournalResult,
    OrganizationSppSummaryRow,
    PlsMismatch,
)


def _build_spp_summary_row():
    return OrganizationSppSummaryRow(
        authorization_id="AUTH-1",
        pma="PMA-1",
        agreement_id="AGR-1",
        mpa="MPA-1",
        pp=Decimal("90.0"),
        sp=Decimal("100.0"),
        currency="USD",
        exchange_rate=Decimal("1.0"),
        spp_discount=Decimal("-10.0"),
        spp_discount_pct=Decimal("0.1111"),
        markup=Decimal("0.1111"),
    )


def test_organization_spp_summary_row_equality():
    result = _build_spp_summary_row()

    assert result == _build_spp_summary_row()


def test_agreement_journal_result_defaults_spp_summary_row_to_none():
    result = AgreementJournalResult()

    assert result.spp_summary_row is None


def test_agreement_journal_result_carries_spp_summary_row():
    row = _build_spp_summary_row()

    result = AgreementJournalResult(spp_summary_row=row)

    assert result.spp_summary_row == row


def test_authorization_journal_result_defaults_spp_summary_rows_to_empty_list():
    result = AuthorizationJournalResult()

    assert result.spp_summary_rows == []


@pytest.mark.parametrize(
    ("pls_in_order", "report_has_enterprise", "expected"),
    [
        (
            True,
            True,
            "Agreement AGR-1: parameter=PLS but report has 'AWS Support (Enterprise)'.",
        ),
        (
            True,
            False,
            "Agreement AGR-1: parameter=PLS but report does not have 'AWS Support (Enterprise)'.",
        ),
        (
            False,
            True,
            "Agreement AGR-1: parameter=Resold Support but report has 'AWS Support (Enterprise)'.",
        ),
        (
            False,
            False,
            (
                "Agreement AGR-1: parameter=Resold Support but report does not have 'AWS Support "
                "(Enterprise)'."
            ),
        ),
    ],
)
def test_pls_mismatch_description(pls_in_order, report_has_enterprise, expected):
    result = PlsMismatch(
        agreement_id="AGR-1",
        pls_in_order=pls_in_order,
        report_has_enterprise=report_has_enterprise,
    )

    assert result.description == expected
