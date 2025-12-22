import pytest
from freezegun import freeze_time

from swo_aws_extension.airtable.models import OpScaleRecord
from swo_aws_extension.constants import OpScaleStatusEnum
from swo_aws_extension.flows.jobs.op_scale_entitlements_processor import (
    OpScaleEntitlementsProcessor,
)

MPT_BASE_URL = "https://localhost"
AGREEMENTS_URL = (
    f"{MPT_BASE_URL}/v1/commerce/agreements?"
    "and(eq(status,Active),in(product.id,(PRD-1111-1111)))"
    "&select=parameters,subscriptions,authorization.externalIds.operations"
    "&limit=10&offset=0"
)
AGREEMENTS_WITH_IDS_URL = (
    f"{MPT_BASE_URL}/v1/commerce/agreements?"
    "and(in(id,(AGR-0001)),eq(status,Active),in(product.id,(PRD-1111-1111)))"
    "&select=parameters,subscriptions,authorization.externalIds.operations"
    "&limit=10&offset=0"
)
PRODUCT_IDS = ("PRD-1111-1111",)
FROZEN_DATE = "2025-12-22 00:00:00"
CURRENT_DATE = "2025-12-22T00:00:00+00:00"
OLD_DATE = "2025-09-22T00:00:00+00:00"  # 90 days before frozen date


@pytest.fixture
def mock_entitlements_table(mocker):
    mock_table = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.flows.jobs.op_scale_entitlements_processor.OpScaleEntitlementsTable",
        return_value=mock_table,
    )
    return mock_table


@freeze_time(FROZEN_DATE)
def test_sync_creates_new_entitlement(
    mocker,
    mpt_client,
    config,
    agreement_factory,
    requests_mocker,
    mock_entitlements_table,
    aws_client_factory,
):
    agreement_data = agreement_factory()
    requests_mocker.add(
        requests_mocker.GET,
        AGREEMENTS_URL,
        json={
            "data": [agreement_data],
            "$meta": {"pagination": {"total": 1, "limit": 10, "offset": 0}},
        },
    )
    mock_entitlements_table.get_by_agreement_id.return_value = []
    _, mock_aws_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_aws_client.get_current_billing_view_by_account_id.return_value = [
        {"arn": "arn:aws:billing::123:billingview/test"}
    ]
    mock_aws_client.get_cost_and_usage.return_value = [{"Groups": [{"Keys": ["123456789"]}]}]
    mocker.patch(
        "swo_aws_extension.flows.jobs.op_scale_entitlements_processor.AWSClient",
        return_value=mock_aws_client,
    )
    processor = OpScaleEntitlementsProcessor(mpt_client, config, [], PRODUCT_IDS)

    processor.sync()  # act

    mock_entitlements_table.save.assert_called_once()


@freeze_time(FROZEN_DATE)
def test_sync_updates_existing(
    mocker,
    mpt_client,
    config,
    agreement_factory,
    requests_mocker,
    mock_entitlements_table,
    aws_client_factory,
):
    agreement_data = agreement_factory()
    requests_mocker.add(
        requests_mocker.GET,
        AGREEMENTS_URL,
        json={
            "data": [agreement_data],
            "$meta": {"pagination": {"total": 1, "limit": 10, "offset": 0}},
        },
    )
    existing_record = OpScaleRecord(
        record_id="rec123",
        account_id="123456789",
        agreement_id="AGR-2119-4550-8674-5962",
        status=OpScaleStatusEnum.ACTIVE,
        last_usage_date=CURRENT_DATE,
    )
    mock_entitlements_table.get_by_agreement_id.return_value = [existing_record]
    _, mock_aws_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_aws_client.get_current_billing_view_by_account_id.return_value = [
        {"arn": "arn:aws:billing::123:billingview/test"}
    ]
    mock_aws_client.get_cost_and_usage.return_value = [{"Groups": [{"Keys": ["123456789"]}]}]
    mocker.patch(
        "swo_aws_extension.flows.jobs.op_scale_entitlements_processor.AWSClient",
        return_value=mock_aws_client,
    )
    processor = OpScaleEntitlementsProcessor(mpt_client, config, [], PRODUCT_IDS)

    processor.sync()  # act

    mock_entitlements_table.update_status_and_usage_date.assert_called()


@freeze_time(FROZEN_DATE)
def test_sync_terminates_inactive(
    mocker,
    mpt_client,
    config,
    agreement_factory,
    requests_mocker,
    mock_entitlements_table,
    aws_client_factory,
):
    agreement_data = agreement_factory()
    requests_mocker.add(
        requests_mocker.GET,
        AGREEMENTS_URL,
        json={
            "data": [agreement_data],
            "$meta": {"pagination": {"total": 1, "limit": 10, "offset": 0}},
        },
    )
    inactive_record = OpScaleRecord(
        record_id="rec123",
        account_id="999999999",
        agreement_id="AGR-2119-4550-8674-5962",
        status=OpScaleStatusEnum.ACTIVE,
        last_usage_date=OLD_DATE,
    )
    mock_entitlements_table.get_by_agreement_id.return_value = [inactive_record]
    _, mock_aws_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_aws_client.get_current_billing_view_by_account_id.return_value = []
    mock_aws_client.get_cost_and_usage.return_value = []
    mocker.patch(
        "swo_aws_extension.flows.jobs.op_scale_entitlements_processor.AWSClient",
        return_value=mock_aws_client,
    )
    processor = OpScaleEntitlementsProcessor(mpt_client, config, [], PRODUCT_IDS)

    processor.sync()  # act

    mock_entitlements_table.update_status_and_usage_date.assert_called_with(
        inactive_record,
        OpScaleStatusEnum.TERMINATED,
        mocker.ANY,
    )


@freeze_time(FROZEN_DATE)
def test_sync_skips_missing_mpa(
    mocker, mpt_client, config, agreement_factory, requests_mocker, mock_entitlements_table
):
    agreement_data = agreement_factory(vendor_id="")
    requests_mocker.add(
        requests_mocker.GET,
        AGREEMENTS_URL,
        json={
            "data": [agreement_data],
            "$meta": {"pagination": {"total": 1, "limit": 10, "offset": 0}},
        },
    )
    notification_mock = mocker.patch(
        "swo_aws_extension.flows.jobs.op_scale_entitlements_processor.TeamsNotificationManager"
    )
    processor = OpScaleEntitlementsProcessor(mpt_client, config, [], PRODUCT_IDS)

    processor.sync()  # act

    notification_mock.return_value.send_error.assert_called_once()


@freeze_time(FROZEN_DATE)
def test_sync_skips_missing_pma(
    mocker, mpt_client, config, agreement_factory, requests_mocker, mock_entitlements_table
):
    agreement_data = agreement_factory(pma_account_id="")
    requests_mocker.add(
        requests_mocker.GET,
        AGREEMENTS_URL,
        json={
            "data": [agreement_data],
            "$meta": {"pagination": {"total": 1, "limit": 10, "offset": 0}},
        },
    )
    notification_mock = mocker.patch(
        "swo_aws_extension.flows.jobs.op_scale_entitlements_processor.TeamsNotificationManager"
    )
    processor = OpScaleEntitlementsProcessor(mpt_client, config, [], PRODUCT_IDS)

    processor.sync()  # act

    notification_mock.return_value.send_error.assert_called_once()


@freeze_time(FROZEN_DATE)
def test_sync_no_agreements(mpt_client, config, requests_mocker, mock_entitlements_table):
    requests_mocker.add(
        requests_mocker.GET,
        AGREEMENTS_URL,
        json={
            "data": [],
            "$meta": {"pagination": {"total": 0, "limit": 10, "offset": 0}},
        },
    )
    processor = OpScaleEntitlementsProcessor(mpt_client, config, [], PRODUCT_IDS)

    processor.sync()  # act

    mock_entitlements_table.get_by_agreement_id.assert_not_called()


@freeze_time(FROZEN_DATE)
def test_sync_with_agreement_ids(
    mocker,
    mpt_client,
    config,
    agreement_factory,
    requests_mocker,
    mock_entitlements_table,
    aws_client_factory,
):
    agreement_data = agreement_factory()
    requests_mocker.add(
        requests_mocker.GET,
        AGREEMENTS_WITH_IDS_URL,
        json={
            "data": [agreement_data],
            "$meta": {"pagination": {"total": 1, "limit": 10, "offset": 0}},
        },
    )
    mock_entitlements_table.get_by_agreement_id.return_value = []
    _, mock_aws_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_aws_client.get_current_billing_view_by_account_id.return_value = []
    mocker.patch(
        "swo_aws_extension.flows.jobs.op_scale_entitlements_processor.AWSClient",
        return_value=mock_aws_client,
    )
    processor = OpScaleEntitlementsProcessor(mpt_client, config, ["AGR-0001"], PRODUCT_IDS)

    processor.sync()  # act

    mock_entitlements_table.get_by_agreement_id.assert_called_once()


@freeze_time(FROZEN_DATE)
def test_skips_terminated_entitlements(
    mocker,
    mpt_client,
    config,
    agreement_factory,
    requests_mocker,
    mock_entitlements_table,
    aws_client_factory,
):
    agreement_data = agreement_factory()
    requests_mocker.add(
        requests_mocker.GET,
        AGREEMENTS_URL,
        json={
            "data": [agreement_data],
            "$meta": {"pagination": {"total": 1, "limit": 10, "offset": 0}},
        },
    )
    terminated_record = OpScaleRecord(
        record_id="rec123",
        account_id="999999999",
        agreement_id="AGR-2119-4550-8674-5962",
        status=OpScaleStatusEnum.TERMINATED,
        last_usage_date=OLD_DATE,
    )
    mock_entitlements_table.get_by_agreement_id.return_value = [terminated_record]
    _, mock_aws_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mock_aws_client.get_current_billing_view_by_account_id.return_value = []
    mocker.patch(
        "swo_aws_extension.flows.jobs.op_scale_entitlements_processor.AWSClient",
        return_value=mock_aws_client,
    )
    processor = OpScaleEntitlementsProcessor(mpt_client, config, [], PRODUCT_IDS)

    processor.sync()  # act

    mock_entitlements_table.update_status_and_usage_date.assert_not_called()
