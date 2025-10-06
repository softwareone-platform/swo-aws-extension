from decimal import Decimal

from swo_aws_extension.constants import ItemSkusEnum
from swo_aws_extension.flows.jobs.billing_journal.line_processors.other_services import (
    GenerateOtherServicesJournalLines,
)


def test_generate_other_services_journal_lines(mock_journal_args, mock_journal_line_factory):
    proc = GenerateOtherServicesJournalLines(billing_discount_tolerance_rate=1, discount=0)
    item_external_id = ItemSkusEnum.AWS_OTHER_SERVICES.value
    args = mock_journal_args()

    journal_lines = proc.process(**args)

    expected = mock_journal_line_factory(
        service_name="Other AWS services",
        item_external_id=item_external_id,
        price=Decimal(100),
    )
    assert journal_lines == [expected]
