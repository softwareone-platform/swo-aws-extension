import pytest
from mpt_extension_sdk.flows.pipeline import Step
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.airtable.models import AccountMigrationRecord
from swo_aws_extension.constants import FulfillmentParametersEnum, PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.set_migration_fulfillment_parameters import (
    SetMigrationFulfillmentParameters,
    get_missing_record_values,
    get_required_parameters,
    get_unset_migration_parameters,
)
from swo_aws_extension.parameters import (
    get_cco_contract_number,
    get_service_discount,
    get_support_discount,
)

MODULE = "swo_aws_extension.flows.steps.set_migration_fulfillment_parameters"
SAMPLE_CCO = "CH-CCO-331705"
SAMPLE_SUPPORT_DISCOUNT = 10
SAMPLE_USAGE_DISCOUNT = 2.5
ALL_MIGRATION_PARAMETERS = (
    FulfillmentParametersEnum.CCO_CONTRACT_NUMBER,
    FulfillmentParametersEnum.SUPPORT_DISCOUNT,
    FulfillmentParametersEnum.SERVICE_DISCOUNT,
)


@pytest.fixture
def migration_record():
    def factory(
        mpt_cco=SAMPLE_CCO,
        mpt_order_id="ORD-0792-5000-2253-4210",
        swo_support_discount=SAMPLE_SUPPORT_DISCOUNT,
        swo_usage_discount=SAMPLE_USAGE_DISCOUNT,
    ):
        return AccountMigrationRecord(
            swo_seller="SWO Spain",
            swo_buyer="Buyer",
            masterpayer="651706759263",
            mpt_cco=mpt_cco,
            swo_support_discount=swo_support_discount,
            swo_usage_discount=swo_usage_discount,
            aws_account_email="customer@example.com",
            aws_support_type="Business",
            technical_contact_name="Tech Contact",
            technical_contact_email="tech@example.com",
            mpt_order_id=mpt_order_id,
            record_id="rec123",
        )

    return factory


@pytest.fixture
def migration_context(order_factory, fulfillment_parameters_factory):
    def factory(
        phase=PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION.value,
        cco="",
        support_discount="",
        service_discount="",
    ):
        order = order_factory(
            fulfillment_parameters=fulfillment_parameters_factory(
                phase=phase,
                cco_contract_number=cco,
                support_discount=support_discount,
                service_discount=service_discount,
            ),
        )
        return PurchaseContext.from_order_data(order)

    return factory


@pytest.fixture
def mock_migration_table(mocker):
    return mocker.patch(f"{MODULE}.AwsAccountMigrationTable")


def fake_update_order(_client, order_id, **kwargs):
    return {"id": order_id, "parameters": kwargs["parameters"]}


@pytest.fixture
def mock_update_order(mocker):
    return mocker.patch(f"{MODULE}.update_order", side_effect=fake_update_order)


@pytest.fixture
def mock_notify(mocker):
    return mocker.patch("swo_aws_extension.flows.steps.base.notify_one_time_error")


@pytest.mark.parametrize(
    ("cco", "support_discount", "service_discount", "expected"),
    [
        ("", "", "", list(ALL_MIGRATION_PARAMETERS)),
        (
            SAMPLE_CCO,
            "",
            "",
            [
                FulfillmentParametersEnum.SUPPORT_DISCOUNT,
                FulfillmentParametersEnum.SERVICE_DISCOUNT,
            ],
        ),
        (SAMPLE_CCO, "10", "", [FulfillmentParametersEnum.SERVICE_DISCOUNT]),
        (SAMPLE_CCO, "10", "2.5", []),
    ],
)
def test_get_unset_migration_parameters(
    migration_context, cco, support_discount, service_discount, expected
):
    context = migration_context(
        cco=cco, support_discount=support_discount, service_discount=service_discount
    )

    result = get_unset_migration_parameters(context.order)

    assert result == expected


@pytest.mark.parametrize(
    ("mpt_cco", "expected"),
    [
        ("", ["ccoContractNumber"]),
        (None, ["ccoContractNumber"]),
        (SAMPLE_CCO, []),
    ],
)
def test_get_missing_record_values(migration_record, mpt_cco, expected):
    record = migration_record(mpt_cco=mpt_cco)

    result = get_missing_record_values(record, ALL_MIGRATION_PARAMETERS)

    assert result == expected


def test_get_required_parameters():
    result = get_required_parameters(list(ALL_MIGRATION_PARAMETERS))

    assert result == [FulfillmentParametersEnum.CCO_CONTRACT_NUMBER]


def test_get_missing_record_values_ignores_optional_discounts(migration_record):
    record = migration_record(swo_support_discount=None, swo_usage_discount=None)

    result = get_missing_record_values(record, ALL_MIGRATION_PARAMETERS)

    assert result == []


def test_sets_parameters_from_migration_record(
    mocker, migration_context, migration_record, mock_migration_table, mock_update_order
):
    mock_client = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    context = migration_context()
    mock_migration_table.return_value.get_by_order_id.return_value = migration_record()
    step = SetMigrationFulfillmentParameters()

    step(mock_client, context, next_step_mock)  # act

    mock_migration_table.return_value.get_by_order_id.assert_called_once_with(context.order_id)
    assert get_cco_contract_number(context.order) == SAMPLE_CCO
    assert get_support_discount(context.order) == "10"
    assert get_service_discount(context.order) == "2.5"
    mock_update_order.assert_called_once_with(
        mock_client, context.order_id, parameters=context.order["parameters"]
    )
    next_step_mock.assert_called_once_with(mock_client, context)


def test_overrides_default_discounts_with_record_values(
    mocker, migration_context, migration_record, mock_migration_table, mock_update_order
):
    mock_client = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    context = migration_context(support_discount="5", service_discount="5")
    mock_migration_table.return_value.get_by_order_id.return_value = migration_record()
    step = SetMigrationFulfillmentParameters()

    step(mock_client, context, next_step_mock)  # act

    assert get_cco_contract_number(context.order) == SAMPLE_CCO
    assert get_support_discount(context.order) == "10"
    assert get_service_discount(context.order) == "2.5"
    next_step_mock.assert_called_once_with(mock_client, context)


def test_keeps_cco_already_set_in_the_order(
    mocker, migration_context, migration_record, mock_migration_table, mock_update_order
):
    mock_client = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    context = migration_context(cco="CH-CCO-000001")
    mock_migration_table.return_value.get_by_order_id.return_value = migration_record()
    step = SetMigrationFulfillmentParameters()

    step(mock_client, context, next_step_mock)  # act

    assert get_cco_contract_number(context.order) == "CH-CCO-000001"
    assert get_support_discount(context.order) == "10"
    assert get_service_discount(context.order) == "2.5"
    next_step_mock.assert_called_once_with(mock_client, context)


def test_stores_zero_discounts(
    mocker, migration_context, migration_record, mock_migration_table, mock_update_order
):
    mock_client = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    context = migration_context()
    mock_migration_table.return_value.get_by_order_id.return_value = migration_record(
        swo_support_discount=0, swo_usage_discount=0
    )
    step = SetMigrationFulfillmentParameters()

    step(mock_client, context, next_step_mock)  # act

    assert get_support_discount(context.order) == "0"
    assert get_service_discount(context.order) == "0"
    next_step_mock.assert_called_once_with(mock_client, context)


def test_leaves_discounts_unset_when_record_has_none(
    mocker,
    migration_context,
    migration_record,
    mock_migration_table,
    mock_update_order,
    mock_notify,
):
    mock_client = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    context = migration_context()
    mock_migration_table.return_value.get_by_order_id.return_value = migration_record(
        swo_support_discount=None, swo_usage_discount=None
    )
    step = SetMigrationFulfillmentParameters()

    step(mock_client, context, next_step_mock)  # act

    assert get_cco_contract_number(context.order) == SAMPLE_CCO
    assert not get_support_discount(context.order)
    assert not get_service_discount(context.order)
    mock_notify.assert_not_called()
    mock_update_order.assert_called_once()
    next_step_mock.assert_called_once_with(mock_client, context)


def test_skips_when_parameters_already_set(
    mocker, migration_context, mock_migration_table, mock_update_order
):
    mock_client = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    context = migration_context(cco=SAMPLE_CCO, support_discount="10", service_discount="2.5")
    step = SetMigrationFulfillmentParameters()

    step(mock_client, context, next_step_mock)  # act

    mock_migration_table.assert_not_called()
    mock_update_order.assert_not_called()
    next_step_mock.assert_called_once_with(mock_client, context)


def test_skips_when_phase_does_not_match(
    mocker, migration_context, mock_migration_table, mock_update_order
):
    mock_client = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    context = migration_context(phase=PhasesEnum.CREATE_SUBSCRIPTION.value)
    step = SetMigrationFulfillmentParameters()

    step(mock_client, context, next_step_mock)  # act

    mock_migration_table.assert_not_called()
    mock_update_order.assert_not_called()
    next_step_mock.assert_called_once_with(mock_client, context)


def test_stops_and_notifies_when_record_is_missing(
    mocker, migration_context, mock_migration_table, mock_update_order, mock_notify
):
    mock_client = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    context = migration_context()
    mock_migration_table.return_value.get_by_order_id.return_value = None
    step = SetMigrationFulfillmentParameters()

    step(mock_client, context, next_step_mock)  # act

    mock_notify.assert_called_once_with(
        f"Migration order {context.order_id} has no migration record",
        f"The migration order {context.order_id} cannot be processed because no row of the "
        "AWS Account Migration Airtable table is linked to it. Please link the row to the "
        "order so the fulfillment can continue.",
    )
    assert not get_cco_contract_number(context.order)
    mock_update_order.assert_not_called()
    next_step_mock.assert_not_called()


def test_continues_without_record_when_only_optional_parameters_are_unset(
    mocker, migration_context, mock_migration_table, mock_update_order, mock_notify
):
    mock_client = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    context = migration_context(cco=SAMPLE_CCO)
    mock_migration_table.return_value.get_by_order_id.return_value = None
    step = SetMigrationFulfillmentParameters()

    step(mock_client, context, next_step_mock)  # act

    mock_notify.assert_not_called()
    assert get_cco_contract_number(context.order) == SAMPLE_CCO
    assert not get_support_discount(context.order)
    assert not get_service_discount(context.order)
    next_step_mock.assert_called_once_with(mock_client, context)


def test_stops_and_notifies_when_record_value_is_missing(
    mocker,
    migration_context,
    migration_record,
    mock_migration_table,
    mock_update_order,
    mock_notify,
):
    mock_client = mocker.MagicMock(spec=MPTClient)
    next_step_mock = mocker.MagicMock(spec=Step)
    context = migration_context()
    mock_migration_table.return_value.get_by_order_id.return_value = migration_record(mpt_cco="")
    step = SetMigrationFulfillmentParameters()

    step(mock_client, context, next_step_mock)  # act

    mock_notify.assert_called_once_with(
        f"Migration order {context.order_id} is missing required data",
        f"The migration order {context.order_id} cannot be processed because the following "
        "parameters have no value in its AWS Account Migration row: ccoContractNumber. "
        "Please complete the row so the fulfillment can continue.",
    )
    assert not get_cco_contract_number(context.order)
    mock_update_order.assert_not_called()
    next_step_mock.assert_not_called()
