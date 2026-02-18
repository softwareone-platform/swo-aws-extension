import pytest
from freezegun import freeze_time

from swo_aws_extension.airtable.models import FinOpsRecord
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import FinOpsStatusEnum
from swo_aws_extension.flows.jobs.finops_entitlements_processor import (
    FinOpsEntitlementsProcessor,
)
from swo_aws_extension.swo.finops.errors import FinOpsError

MPT_BASE_URL = "https://localhost/public"
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
OLD_DATE = "2025-09-22T00:00:00+00:00"


@pytest.fixture
def mock_entitlements_table(mocker):
    mock_table = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.flows.jobs.finops_entitlements_processor.FinOpsEntitlementsTable",
        return_value=mock_table,
    )
    return mock_table


@pytest.fixture
def mock_finops_client(mocker):
    mock_client = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.flows.jobs.finops_entitlements_processor.get_ffc_client",
        return_value=mock_client,
    )
    return mock_client


@pytest.fixture
def mock_agreements_response(requests_mocker, agreement_factory):
    def factory(url=AGREEMENTS_URL, agreements=None, total=None):
        if agreements is None:
            agreements = [agreement_factory()]
        if total is None:
            total = len(agreements)
        requests_mocker.add(
            requests_mocker.GET,
            url,
            json={
                "data": agreements,
                "$meta": {"pagination": {"total": total, "limit": 10, "offset": 0}},
            },
        )

    return factory


@pytest.fixture
def finops_processor(mpt_client, config):
    def factory(agreement_ids=None):
        if agreement_ids is None:
            agreement_ids = []
        return FinOpsEntitlementsProcessor(mpt_client, config, agreement_ids, PRODUCT_IDS)

    return factory


@pytest.fixture
def mock_aws_client(mocker, aws_client_factory, config):
    _, mock_client = aws_client_factory(config, "test_account_id", "test_role_name")
    mocker.patch(
        "swo_aws_extension.flows.jobs.finops_entitlements_processor.AWSClient",
        return_value=mock_client,
    )
    return mock_client


@freeze_time(FROZEN_DATE)
def test_sync_creates_new_entitlement(
    mocker,
    mock_agreements_response,
    mock_entitlements_table,
    mock_finops_client,
    mock_aws_client,
    finops_processor,
):
    mock_agreements_response()
    mock_entitlements_table.get_by_agreement_id.return_value = []
    mock_finops_client.get_entitlement_by_datasource.return_value = None
    mock_finops_client.create_entitlement.return_value = {"id": "ENT-001"}
    mock_aws_client.get_current_billing_view_by_account_id.return_value = [
        {"arn": "arn:aws:billing::123:billingview/test"}
    ]
    mock_aws_client.get_cost_and_usage.return_value = [{"Groups": [{"Keys": ["123456789"]}]}]
    processor = finops_processor()

    processor.sync()  # act

    mock_finops_client.create_entitlement.assert_called_once()
    mock_entitlements_table.save.assert_called_once()


@freeze_time(FROZEN_DATE)
def test_sync_updates_existing(
    mocker,
    mock_agreements_response,
    mock_entitlements_table,
    mock_finops_client,
    mock_aws_client,
    finops_processor,
):
    mock_agreements_response()
    existing_record = FinOpsRecord(
        record_id="rec123",
        account_id="123456789",
        buyer_id="BUY-3731-7971",
        agreement_id="AGR-2119-4550-8674-5962",
        entitlement_id="ENT-001",
        status=FinOpsStatusEnum.ACTIVE,
        last_usage_date=CURRENT_DATE,
    )
    mock_entitlements_table.get_by_agreement_id.return_value = [existing_record]
    mock_finops_client.get_entitlement_by_datasource.return_value = {
        "id": "ENT-001",
        "status": "active",
    }
    mock_aws_client.get_current_billing_view_by_account_id.return_value = [
        {"arn": "arn:aws:billing::123:billingview/test"}
    ]
    mock_aws_client.get_cost_and_usage.return_value = [{"Groups": [{"Keys": ["123456789"]}]}]
    processor = finops_processor()

    processor.sync()  # act

    mock_entitlements_table.update_status_and_usage_date.assert_called()


@freeze_time(FROZEN_DATE)
def test_sync_terminates_inactive(
    mocker,
    mock_agreements_response,
    mock_entitlements_table,
    mock_finops_client,
    mock_aws_client,
    finops_processor,
):
    mock_agreements_response()
    inactive_record = FinOpsRecord(
        record_id="rec123",
        account_id="999999999",
        buyer_id="BUY-3731-7971",
        agreement_id="AGR-2119-4550-8674-5962",
        entitlement_id="ENT-001",
        status=FinOpsStatusEnum.ACTIVE,
        last_usage_date=OLD_DATE,
    )
    mock_entitlements_table.get_by_agreement_id.return_value = [inactive_record]
    mock_finops_client.get_entitlement_by_datasource.return_value = {
        "id": "ENT-001",
        "status": "active",
    }
    mock_aws_client.get_current_billing_view_by_account_id.return_value = []
    processor = finops_processor()

    processor.sync()  # act

    mock_finops_client.terminate_entitlement.assert_called_once()
    mock_entitlements_table.update_status_and_usage_date.assert_called_with(
        inactive_record,
        FinOpsStatusEnum.TERMINATED,
        mocker.ANY,
    )


@freeze_time(FROZEN_DATE)
def test_sync_deletes_new_entitlement(
    mock_agreements_response,
    mock_entitlements_table,
    mock_finops_client,
    mock_aws_client,
    finops_processor,
):
    mock_agreements_response()
    inactive_record = FinOpsRecord(
        record_id="rec123",
        account_id="999999999",
        buyer_id="BUY-3731-7971",
        agreement_id="AGR-2119-4550-8674-5962",
        entitlement_id="ENT-001",
        status=FinOpsStatusEnum.ACTIVE,
        last_usage_date=OLD_DATE,
    )
    mock_entitlements_table.get_by_agreement_id.return_value = [inactive_record]
    mock_finops_client.get_entitlement_by_datasource.return_value = {
        "id": "ENT-001",
        "status": "new",
    }
    mock_aws_client.get_current_billing_view_by_account_id.return_value = []
    processor = finops_processor()

    processor.sync()  # act

    mock_finops_client.delete_entitlement.assert_called_once()


@freeze_time(FROZEN_DATE)
def test_sync_skips_missing_mpa(
    mocker,
    agreement_factory,
    mock_agreements_response,
    mock_entitlements_table,
    mock_finops_client,
    finops_processor,
):
    mock_agreements_response(agreements=[agreement_factory(vendor_id="")])
    notification_mock = mocker.patch(
        "swo_aws_extension.flows.jobs.finops_entitlements_processor.TeamsNotificationManager"
    )
    processor = finops_processor()

    processor.sync()  # act

    notification_mock.return_value.send_error.assert_called_once()


@freeze_time(FROZEN_DATE)
def test_sync_skips_missing_pma(
    mocker,
    agreement_factory,
    mock_agreements_response,
    mock_entitlements_table,
    mock_finops_client,
    finops_processor,
):
    mock_agreements_response(agreements=[agreement_factory(pma_account_id="")])
    notification_mock = mocker.patch(
        "swo_aws_extension.flows.jobs.finops_entitlements_processor.TeamsNotificationManager"
    )
    processor = finops_processor()

    processor.sync()  # act

    notification_mock.return_value.send_error.assert_called_once()


@freeze_time(FROZEN_DATE)
def test_sync_no_agreements(
    mock_agreements_response, mock_entitlements_table, mock_finops_client, finops_processor
):
    mock_agreements_response(agreements=[], total=0)
    processor = finops_processor()

    processor.sync()  # act

    mock_entitlements_table.get_by_agreement_id.assert_not_called()


@freeze_time(FROZEN_DATE)
def test_sync_with_agreement_ids(
    mock_agreements_response,
    mock_entitlements_table,
    mock_finops_client,
    mock_aws_client,
    finops_processor,
):
    mock_agreements_response(url=AGREEMENTS_WITH_IDS_URL)
    mock_entitlements_table.get_by_agreement_id.return_value = []
    mock_aws_client.get_current_billing_view_by_account_id.return_value = []
    processor = finops_processor(agreement_ids=["AGR-0001"])

    processor.sync()  # act

    mock_entitlements_table.get_by_agreement_id.assert_called_once()


@freeze_time(FROZEN_DATE)
def test_sync_skips_terminated(
    mock_agreements_response,
    mock_entitlements_table,
    mock_finops_client,
    mock_aws_client,
    finops_processor,
):
    mock_agreements_response()
    terminated_record = FinOpsRecord(
        record_id="rec123",
        account_id="999999999",
        buyer_id="BUY-3731-7971",
        agreement_id="AGR-2119-4550-8674-5962",
        entitlement_id="ENT-001",
        status=FinOpsStatusEnum.TERMINATED,
        last_usage_date=OLD_DATE,
    )
    mock_entitlements_table.get_by_agreement_id.return_value = [terminated_record]
    mock_aws_client.get_current_billing_view_by_account_id.return_value = []
    processor = finops_processor()

    processor.sync()  # act

    mock_finops_client.terminate_entitlement.assert_not_called()
    mock_entitlements_table.update_status_and_usage_date.assert_not_called()


@freeze_time(FROZEN_DATE)
def test_sync_uses_existing_finops_entitlement(
    mock_agreements_response,
    mock_entitlements_table,
    mock_finops_client,
    mock_aws_client,
    finops_processor,
):
    mock_agreements_response()
    mock_entitlements_table.get_by_agreement_id.return_value = []
    mock_finops_client.get_entitlement_by_datasource.return_value = {
        "id": "ENT-EXISTING",
        "status": "active",
    }
    mock_aws_client.get_current_billing_view_by_account_id.return_value = [
        {"arn": "arn:aws:billing::123:billingview/test"}
    ]
    mock_aws_client.get_cost_and_usage.return_value = [{"Groups": [{"Keys": ["123456789"]}]}]
    processor = finops_processor()

    processor.sync()  # act

    mock_finops_client.create_entitlement.assert_not_called()
    mock_entitlements_table.save.assert_called_once()


@freeze_time(FROZEN_DATE)
def test_sync_handles_finops_error_on_create(
    mocker,
    mock_agreements_response,
    mock_entitlements_table,
    mock_finops_client,
    mock_aws_client,
    finops_processor,
):
    mock_agreements_response()
    mock_entitlements_table.get_by_agreement_id.return_value = []
    mock_finops_client.get_entitlement_by_datasource.return_value = None
    mock_finops_client.create_entitlement.side_effect = FinOpsError("FinOps API error")
    mock_aws_client.get_current_billing_view_by_account_id.return_value = [
        {"arn": "arn:aws:billing::123:billingview/test"}
    ]
    mock_aws_client.get_cost_and_usage.return_value = [{"Groups": [{"Keys": ["123456789"]}]}]
    processor = finops_processor()

    processor.sync()  # act

    mock_entitlements_table.save.assert_called_once()
    saved_record = mock_entitlements_table.save.call_args[0][0]
    assert saved_record.entitlement_id is None


@freeze_time(FROZEN_DATE)
def test_sync_finops_error_on_get_entitlement(
    mocker,
    mock_agreements_response,
    mock_entitlements_table,
    mock_finops_client,
    mock_aws_client,
    finops_processor,
):
    mock_agreements_response()
    mock_entitlements_table.get_by_agreement_id.return_value = []
    mock_finops_client.get_entitlement_by_datasource.side_effect = FinOpsError("FinOps API error")
    mock_aws_client.get_current_billing_view_by_account_id.return_value = [
        {"arn": "arn:aws:billing::123:billingview/test"}
    ]
    mock_aws_client.get_cost_and_usage.return_value = [{"Groups": [{"Keys": ["123456789"]}]}]
    processor = finops_processor()

    processor.sync()  # act

    mock_finops_client.create_entitlement.assert_not_called()
    mock_entitlements_table.save.assert_called_once()
    saved_record = mock_entitlements_table.save.call_args[0][0]
    assert saved_record.entitlement_id is None


@freeze_time(FROZEN_DATE)
def test_sync_updates_existing_with_finops_error(
    mocker,
    mock_agreements_response,
    mock_entitlements_table,
    mock_finops_client,
    mock_aws_client,
    finops_processor,
):
    mock_agreements_response()
    existing_record = FinOpsRecord(
        record_id="rec123",
        account_id="123456789",
        buyer_id="BUY-3731-7971",
        agreement_id="AGR-2119-4550-8674-5962",
        entitlement_id="ENT-001",
        status=FinOpsStatusEnum.ACTIVE,
        last_usage_date=CURRENT_DATE,
    )
    mock_entitlements_table.get_by_agreement_id.return_value = [existing_record]
    mock_finops_client.get_entitlement_by_datasource.side_effect = FinOpsError("FinOps API error")
    mock_aws_client.get_current_billing_view_by_account_id.return_value = [
        {"arn": "arn:aws:billing::123:billingview/test"}
    ]
    mock_aws_client.get_cost_and_usage.return_value = [{"Groups": [{"Keys": ["123456789"]}]}]
    processor = finops_processor()

    processor.sync()  # act

    assert existing_record.entitlement_id == "ENT-001"
    mock_entitlements_table.update_status_and_usage_date.assert_called()


@freeze_time(FROZEN_DATE)
def test_sync_handles_aws_error_on_cost_and_usage(
    mock_agreements_response,
    mock_entitlements_table,
    mock_finops_client,
    mock_aws_client,
    finops_processor,
):
    mock_agreements_response()
    mock_entitlements_table.get_by_agreement_id.return_value = []
    mock_aws_client.get_current_billing_view_by_account_id.return_value = [
        {"arn": "arn:aws:billing::123:billingview/test"}
    ]
    mock_aws_client.get_cost_and_usage.side_effect = AWSError("AWS API error")
    processor = finops_processor()

    processor.sync()  # act

    mock_finops_client.create_entitlement.assert_not_called()
    mock_entitlements_table.save.assert_not_called()


@freeze_time(FROZEN_DATE)
def test_sync_terminate_not_found_in_finops(
    mocker,
    mock_agreements_response,
    mock_entitlements_table,
    mock_finops_client,
    mock_aws_client,
    finops_processor,
):
    mock_agreements_response()
    inactive_record = FinOpsRecord(
        record_id="rec123",
        account_id="999999999",
        buyer_id="BUY-3731-7971",
        agreement_id="AGR-2119-4550-8674-5962",
        entitlement_id="ENT-001",
        status=FinOpsStatusEnum.ACTIVE,
        last_usage_date=OLD_DATE,
    )
    mock_entitlements_table.get_by_agreement_id.return_value = [inactive_record]
    mock_finops_client.get_entitlement_by_datasource.return_value = None
    mock_aws_client.get_current_billing_view_by_account_id.return_value = []
    processor = finops_processor()

    processor.sync()  # act

    mock_finops_client.terminate_entitlement.assert_not_called()
    mock_finops_client.delete_entitlement.assert_not_called()
    mock_entitlements_table.update_status_and_usage_date.assert_called_with(
        inactive_record,
        FinOpsStatusEnum.TERMINATED,
        mocker.ANY,
    )


@freeze_time(FROZEN_DATE)
def test_sync_deletes_new_entitlement_and_update(
    mocker,
    mock_agreements_response,
    mock_entitlements_table,
    mock_finops_client,
    mock_aws_client,
    finops_processor,
):
    mock_agreements_response()
    inactive_record = FinOpsRecord(
        record_id="rec123",
        account_id="999999999",
        buyer_id="BUY-3731-7971",
        agreement_id="AGR-2119-4550-8674-5962",
        entitlement_id="ENT-001",
        status=FinOpsStatusEnum.ACTIVE,
        last_usage_date=OLD_DATE,
    )
    mock_entitlements_table.get_by_agreement_id.return_value = [inactive_record]
    mock_finops_client.get_entitlement_by_datasource.return_value = {
        "id": "ENT-001",
        "status": "new",
    }
    mock_aws_client.get_current_billing_view_by_account_id.return_value = []
    processor = finops_processor()

    processor.sync()  # act

    mock_finops_client.delete_entitlement.assert_called_once_with("ENT-001")
    mock_finops_client.terminate_entitlement.assert_not_called()
    mock_entitlements_table.update_status_and_usage_date.assert_called_with(
        inactive_record,
        FinOpsStatusEnum.TERMINATED,
        mocker.ANY,
    )
