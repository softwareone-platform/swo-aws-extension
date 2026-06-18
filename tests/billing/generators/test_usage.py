from decimal import Decimal

import pytest

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.billing.generators.usage import (
    CostExplorerUsageGenerator,
)
from swo_aws_extension.billing.models.invoice import (
    InvoiceEntity,
    OrganizationInvoice,
)
from swo_aws_extension.billing.models.usage import (
    OrganizationUsageResult,
)
from swo_aws_extension.constants import AWSRecordTypeEnum
from swo_aws_extension.models import BillingPeriod


@pytest.fixture
def mock_aws_client(mocker):
    return mocker.MagicMock(spec=AWSClient)


@pytest.fixture
def billing_period():
    return BillingPeriod(start_date="2025-10-01", end_date="2025-11-01")


@pytest.fixture
def organization_invoice():
    return OrganizationInvoice()


@pytest.fixture
def generator(mock_aws_client):
    return CostExplorerUsageGenerator(mock_aws_client)


@pytest.fixture
def single_billing_view():
    return [{"arn": "arn:...:view/1", "name": "View 1"}]


@pytest.fixture
def single_account_usage():
    return [
        [
            {
                "TimePeriod": {"Start": "2025-10-01", "End": "2025-10-02"},
                "Groups": [{"Keys": ["ACT-1"]}],
            }
        ],
        [
            {
                "TimePeriod": {"Start": "2025-10-01", "End": "2025-10-02"},
                "Groups": [
                    {
                        "Keys": ["ACT-1", "AmazonEC2"],
                        "Metrics": {"UnblendedCost": {"Amount": "10,25"}},
                    }
                ],
            }
        ],
        [
            {
                "TimePeriod": {"Start": "2025-10-01", "End": "2025-10-02"},
                "Groups": [{"Keys": ["AmazonEC2", "Amazon Web Services, Inc."]}],
            }
        ],
        [
            {
                "TimePeriod": {"Start": "2025-10-01", "End": "2025-10-02"},
                "Groups": [
                    {
                        "Keys": [AWSRecordTypeEnum.USAGE, "AmazonEC2"],
                        "Metrics": {"UnblendedCost": {"Amount": "50,75"}},
                    }
                ],
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
        [
            {
                "TimePeriod": {"Start": "2025-10-01", "End": "2025-10-02"},
                "Groups": [{"Keys": ["ACT-1"]}],
            }
        ],
        [
            {
                "TimePeriod": {"Start": "2025-10-01", "End": "2025-10-02"},
                "Groups": [
                    {
                        "Keys": ["ACT-1", "AmazonRDS"],
                        "Metrics": {"UnblendedCost": {"Amount": "100.0"}},
                    }
                ],
            }
        ],
        [
            {
                "TimePeriod": {"Start": "2025-10-01", "End": "2025-10-02"},
                "Groups": [{"Keys": ["AmazonRDS", "Amazon Web Services, Inc."]}],
            }
        ],
        [
            {
                "TimePeriod": {"Start": "2025-10-01", "End": "2025-10-02"},
                "Groups": [
                    {
                        "Keys": [AWSRecordTypeEnum.USAGE, "AmazonRDS"],
                        "Metrics": {"UnblendedCost": {"Amount": "50.0"}},
                    }
                ],
            }
        ],
    ]
    return view_data + view_data


def test_generate_processes_single_account(
    generator,
    mock_aws_client,
    billing_period,
    organization_invoice,
    single_billing_view,
    single_account_usage,
):
    mock_aws_client.get_billing_views_by_account_id.return_value = single_billing_view
    mock_aws_client.get_cost_and_usage.side_effect = single_account_usage

    result = generator.run("USD", "MPA-1", billing_period, organization_invoice)

    assert isinstance(result, OrganizationUsageResult)
    assert "ACT-1" in result.usage_by_account
    account_usage = result.usage_by_account["ACT-1"]
    metrics = [metric for metric in account_usage.metrics if metric.service_name == "AmazonEC2"]
    assert len(metrics) > 0
    marketplace_metrics = [metric for metric in metrics if metric.record_type == "MARKETPLACE"]
    assert len(marketplace_metrics) == 1
    metric = marketplace_metrics[0]
    assert (metric.amount, metric.start_date, metric.end_date) == (
        Decimal("10.25"),
        "2025-10-01",
        "2025-10-01",
    )


def test_generate_returns_correct_invoice_entity(
    generator,
    mock_aws_client,
    billing_period,
    organization_invoice,
    single_billing_view,
):
    mock_aws_client.get_billing_views_by_account_id.return_value = single_billing_view
    mock_aws_client.get_cost_and_usage.side_effect = [
        [
            {
                "TimePeriod": {"Start": "2025-10-01", "End": "2025-10-02"},
                "Groups": [{"Keys": ["ACT-1"]}],
            }
        ],
        [{"TimePeriod": {"Start": "2025-10-01", "End": "2025-10-02"}, "Groups": []}],
        [
            {
                "TimePeriod": {"Start": "2025-10-01", "End": "2025-10-02"},
                "Groups": [{"Keys": ["AmazonEC2", "Amazon Web Services, Inc."]}],
            }
        ],
        [
            {
                "TimePeriod": {"Start": "2025-10-01", "End": "2025-10-02"},
                "Groups": [
                    {
                        "Keys": [AWSRecordTypeEnum.USAGE, "AmazonEC2"],
                        "Metrics": {"UnblendedCost": {"Amount": "10.0"}},
                    }
                ],
            }
        ],
    ]

    result = generator.run("USD", "MPA-1", billing_period, organization_invoice)

    account_usage = result.usage_by_account["ACT-1"]
    metrics = [metric for metric in account_usage.metrics if metric.service_name == "AmazonEC2"]
    assert metrics[0].invoice_entity == "Amazon Web Services, Inc.:AWS"


def test_generate_handles_multiple_billing_views(
    generator,
    mock_aws_client,
    billing_period,
    organization_invoice,
    duplicate_billing_views,
    duplicate_account_usage,
):
    mock_aws_client.get_billing_views_by_account_id.return_value = duplicate_billing_views
    mock_aws_client.get_cost_and_usage.side_effect = duplicate_account_usage

    result = generator.run("USD", "MPA-1", billing_period, organization_invoice)

    account_usage = result.usage_by_account["ACT-1"]
    metrics = [metric for metric in account_usage.metrics if metric.service_name == "AmazonRDS"]
    assert len(metrics) > 0
    marketplace_metrics = [metric for metric in metrics if metric.record_type == "MARKETPLACE"]
    assert len(marketplace_metrics) == 1
    assert marketplace_metrics[0].amount == Decimal("100.0")


def test_generate_error_retrieving_accounts(
    generator,
    mock_aws_client,
    billing_period,
    organization_invoice,
    single_billing_view,
):
    mock_aws_client.get_billing_views_by_account_id.return_value = single_billing_view
    mock_aws_client.get_cost_and_usage.side_effect = AWSError("AWS API Error")

    result = generator.run("USD", "MPA-1", billing_period, organization_invoice)

    assert not result.usage_by_account


def test_generate_skips_zero_amount_metrics(
    generator,
    mock_aws_client,
    billing_period,
    organization_invoice,
    single_billing_view,
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

    result = generator.run("USD", "MPA-1", billing_period, organization_invoice)

    account_usage = result.usage_by_account["ACT-1"]
    metrics = [metric for metric in account_usage.metrics if metric.service_name == "S3"]
    assert len(metrics) == 0


def test_generate_sets_invoice_id_from_organization_invoice(
    generator,
    mock_aws_client,
    billing_period,
    single_billing_view,
    single_account_usage,
):
    mock_aws_client.get_billing_views_by_account_id.return_value = single_billing_view
    mock_aws_client.get_cost_and_usage.side_effect = single_account_usage
    organization_invoice = OrganizationInvoice(
        entities={
            "Amazon Web Services, Inc.:AWS": InvoiceEntity(invoice_id="INV-001,INV-002"),
        },
    )

    result = generator.run(
        "USD",
        "MPA-1",
        billing_period,
        organization_invoice=organization_invoice,
    )

    account_usage = result.usage_by_account["ACT-1"]
    metrics = [
        metric
        for metric in account_usage.metrics
        if metric.service_name == "AmazonEC2" and metric.record_type != "MARKETPLACE"
    ]
    assert metrics[0].invoice_id == "INV-001,INV-002"


def test_run_for_pma_fetches_correct_usage(
    generator,
    mock_aws_client,
    billing_period,
    organization_invoice,
    single_account_usage,
):
    mock_aws_client.get_cost_and_usage.side_effect = single_account_usage[1:]

    result = generator.run_for_pma("ACT-1", billing_period, organization_invoice)

    assert isinstance(result, OrganizationUsageResult)
    assert "ACT-1" in result.usage_by_account
    account_usage = result.usage_by_account["ACT-1"]
    metrics = [metric for metric in account_usage.metrics if metric.service_name == "AmazonEC2"]
    assert len(metrics) > 0
    assert mock_aws_client.get_cost_and_usage.call_count == 3
    first_call_kwargs = mock_aws_client.get_cost_and_usage.call_args_list[0].kwargs
    assert "view_arn" not in first_call_kwargs or first_call_kwargs["view_arn"] in {None, ""}


def test_create_metric_without_invoicing_entity(
    generator,
    mock_aws_client,
    billing_period,
    single_billing_view,
):
    account_usage_data = [
        [{"Groups": [{"Keys": ["ACT-1"]}]}],
        [
            {
                "TimePeriod": {"Start": "2025-10-01", "End": "2025-10-02"},
                "Groups": [
                    {
                        "Keys": ["ACT-1", "AmazonEC2"],
                        "Metrics": {"UnblendedCost": {"Amount": "10.00"}},
                    },
                ],
            },
        ],
        [{"Groups": [{"Keys": ["UnknownService", "SomeEntity"]}]}],
        [
            {
                "TimePeriod": {"Start": "2025-10-01", "End": "2025-10-02"},
                "Groups": [
                    {
                        "Keys": [AWSRecordTypeEnum.USAGE, "AmazonEC2"],
                        "Metrics": {"UnblendedCost": {"Amount": "50.00"}},
                    },
                ],
            },
        ],
    ]
    mock_aws_client.get_billing_views_by_account_id.return_value = single_billing_view
    mock_aws_client.get_cost_and_usage.side_effect = account_usage_data

    result = generator.run("USD", "MPA-1", billing_period, OrganizationInvoice())

    account_usage = result.usage_by_account["ACT-1"]
    usage_metrics = [
        metric
        for metric in account_usage.metrics
        if metric.service_name == "AmazonEC2" and metric.record_type != "MARKETPLACE"
    ]
    assert usage_metrics[0].invoice_entity is None
    assert not usage_metrics[0].invoice_id
