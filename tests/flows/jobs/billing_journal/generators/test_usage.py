from decimal import Decimal

import pytest

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import AWSRecordTypeEnum
from swo_aws_extension.flows.jobs.billing_journal.generators.usage import (
    CostExplorerUsageGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.models.billing_period import BillingPeriod
from swo_aws_extension.flows.jobs.billing_journal.models.usage import (
    OrganizationUsageResult,
)


@pytest.fixture
def mock_aws_client(mocker):
    return mocker.MagicMock(spec=AWSClient)


@pytest.fixture
def billing_period():
    return BillingPeriod(start_date="2025-10-01", end_date="2025-11-01")


@pytest.fixture
def generator(mock_aws_client):
    return CostExplorerUsageGenerator(mock_aws_client)


@pytest.fixture
def single_billing_view():
    return [{"arn": "arn:...:view/1", "name": "View 1"}]


@pytest.fixture
def single_account_usage():
    return [
        [{"Groups": [{"Keys": ["ACT-1"]}]}],
        [
            {
                "Groups": [
                    {
                        "Keys": ["ACT-1", "AmazonEC2"],
                        "Metrics": {"UnblendedCost": {"Amount": "10,25"}},
                    }
                ]
            }
        ],
        [{"Groups": [{"Keys": ["AmazonEC2", "Amazon Web Services, Inc."]}]}],
        [
            {
                "Groups": [
                    {
                        "Keys": [AWSRecordTypeEnum.USAGE, "AmazonEC2"],
                        "Metrics": {"UnblendedCost": {"Amount": "50,75"}},
                    }
                ]
            }
        ],
    ]


@pytest.fixture
def duplicate_billing_views():
    return [
        {"arn": "arn:...:view/1", "name": "View 1"},
        {"arn": "arn:...:view/2", "name": "View 2"},
    ]


@pytest.fixture
def duplicate_account_usage():
    view_data = [
        [{"Groups": [{"Keys": ["ACT-1"]}]}],
        [
            {
                "Groups": [
                    {
                        "Keys": ["ACT-1", "AmazonRDS"],
                        "Metrics": {"UnblendedCost": {"Amount": "100.0"}},
                    }
                ]
            }
        ],
        [{"Groups": [{"Keys": ["AmazonRDS", "Amazon Web Services, Inc."]}]}],
        [
            {
                "Groups": [
                    {
                        "Keys": [AWSRecordTypeEnum.USAGE, "AmazonRDS"],
                        "Metrics": {"UnblendedCost": {"Amount": "50.0"}},
                    }
                ]
            }
        ],
    ]
    return view_data + view_data


def test_generate_processes_single_account(
    generator, mock_aws_client, billing_period, single_billing_view, single_account_usage
):
    mock_aws_client.get_billing_views_by_account_id.return_value = single_billing_view
    mock_aws_client.get_cost_and_usage.side_effect = single_account_usage

    result = generator.run("AGR-1", "MPA-1", billing_period)

    assert isinstance(result, OrganizationUsageResult)
    assert "ACT-1" in result.usage_by_account
    service_metrics = result.usage_by_account["ACT-1"].services["AmazonEC2"]
    assert service_metrics.marketplace == Decimal("10.25")
    assert service_metrics.usage == Decimal("50.75")


def test_generate_returns_correct_invoice_entity(
    generator, mock_aws_client, billing_period, single_billing_view
):
    mock_aws_client.get_billing_views_by_account_id.return_value = single_billing_view
    mock_aws_client.get_cost_and_usage.side_effect = [
        [{"Groups": [{"Keys": ["ACT-1"]}]}],
        [{"Groups": []}],
        [{"Groups": [{"Keys": ["AmazonEC2", "Amazon Web Services, Inc."]}]}],
        [
            {
                "Groups": [
                    {
                        "Keys": [AWSRecordTypeEnum.USAGE, "AmazonEC2"],
                        "Metrics": {"UnblendedCost": {"Amount": "10.0"}},
                    }
                ]
            }
        ],
    ]

    result = generator.run("AGR-1", "MPA-1", billing_period)

    service = result.usage_by_account["ACT-1"].services["AmazonEC2"]
    assert service.service_invoice_entity == "Amazon Web Services, Inc."


def test_generate_handles_multiple_billing_views(
    generator, mock_aws_client, billing_period, duplicate_billing_views, duplicate_account_usage
):
    mock_aws_client.get_billing_views_by_account_id.return_value = duplicate_billing_views
    mock_aws_client.get_cost_and_usage.side_effect = duplicate_account_usage

    result = generator.run("AGR-1", "MPA-1", billing_period)

    service_metrics = result.usage_by_account["ACT-1"].services["AmazonRDS"]
    assert service_metrics.marketplace == Decimal("100.0")
    assert service_metrics.usage == Decimal("50.0")


def test_generate_error_retrieving_accounts(
    generator, mock_aws_client, billing_period, single_billing_view
):
    mock_aws_client.get_billing_views_by_account_id.return_value = single_billing_view
    mock_aws_client.get_cost_and_usage.side_effect = AWSError("AWS API Error")

    result = generator.run("AGR-1", "MPA-1", billing_period)

    assert result.usage_by_account == {}


def test_generate_skips_zero_amount_metrics(
    generator, mock_aws_client, billing_period, single_billing_view
):
    mock_aws_client.get_billing_views_by_account_id.return_value = single_billing_view
    mock_aws_client.get_cost_and_usage.side_effect = [
        [{"Groups": [{"Keys": ["ACT-1"]}]}],
        [{"Groups": []}],
        [{"Groups": [{"Keys": ["S3", "EntityValue"]}]}],
        [
            {
                "Groups": [
                    {
                        "Keys": [AWSRecordTypeEnum.USAGE, "S3"],
                        "Metrics": {"UnblendedCost": {"Amount": "0.0"}},
                    },
                ]
            }
        ],
    ]

    result = generator.run("AGR-1", "MPA-1", billing_period)

    service = result.usage_by_account["ACT-1"].services["S3"]
    assert service.usage == Decimal(0)
