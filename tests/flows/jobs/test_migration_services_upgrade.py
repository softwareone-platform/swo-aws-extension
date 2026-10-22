import pytest

from swo_aws_extension.constants import (
    FulfillmentParametersEnum,
    ParamPhasesEnum,
)
from swo_aws_extension.flows.jobs.migration_services_upgrade import (
    build_order_context,
    get_stored_execution_arns,
    get_upgrade_request,
    get_upgrade_status,
    start_upgrade,
    store_execution_arns,
)
from swo_aws_extension.swo.cloud_orchestrator.errors import (
    CloudOrchestratorError,
    CloudOrchestratorMissingScuError,
)

ORDER_ID = "ORD-0792-5000-2253-4210"
AGREEMENT_ID = "AGR-2119-4550-8674-5962"
PMA_ACCOUNT_ID = "123456789012"
MASTER_PAYER_ID = "651706759263"
EXECUTION_PREFIX = "arn:aws:states:eu-west-1:822835360798:execution"
FIRST_EXECUTION_ARN = f"{EXECUTION_PREFIX}:deployment-1155d5f6:execution-54b05eea"
SECOND_EXECUTION_ARN = f"{EXECUTION_PREFIX}:deployment-bf570ae0:execution-789355e7"
EXECUTION_ARNS = (FIRST_EXECUTION_ARN, SECOND_EXECUTION_ARN)
STORED_EXECUTION_ARNS = ",".join(EXECUTION_ARNS)


@pytest.fixture
def upgrade_response():
    # Real Cloud Orchestrator upgrade response: one execution per deployment of the account.
    return {
        "executions": [
            {
                "execution_arn": FIRST_EXECUTION_ARN,
                "deployment_id": "f54e1c4b-3d90-4489-8ec6-f2b1157daf3b",
            },
            {
                "execution_arn": SECOND_EXECUTION_ARN,
                "deployment_id": "5fb1a5e9-2678-4cd1-92f0-830559483b4d",
            },
        ]
    }


@pytest.fixture
def order(buyer, seller, fulfillment_parameters_factory, order_parameters_factory):
    return {
        "id": ORDER_ID,
        "parameters": {
            "ordering": order_parameters_factory(mpa_id=MASTER_PAYER_ID),
            "fulfillment": fulfillment_parameters_factory(),
        },
        "authorization": {"externalIds": {"operations": PMA_ACCOUNT_ID}},
        "agreement": {
            "id": AGREEMENT_ID,
            "parameters": {
                "ordering": [],
                "fulfillment": fulfillment_parameters_factory(execution_arn=STORED_EXECUTION_ARNS),
            },
        },
        "buyer": buyer,
        "seller": seller,
    }


@pytest.fixture
def mock_cloud_orchestrator(mocker, upgrade_response):
    mock_client = mocker.patch(
        "swo_aws_extension.flows.cloud_orchestrator_utils.CloudOrchestratorClient"
    ).return_value
    mock_client.upgrade_customer.return_value = upgrade_response
    mock_client.get_deployment_status.return_value = {"status": "RUNNING"}
    return mock_client


def test_get_stored_execution_arns(order):
    result = get_stored_execution_arns(order)

    assert result == list(EXECUTION_ARNS)


@pytest.mark.parametrize(
    ("stored_value", "expected"),
    [
        (FIRST_EXECUTION_ARN, [FIRST_EXECUTION_ARN]),
        (f" {FIRST_EXECUTION_ARN} , {SECOND_EXECUTION_ARN},", list(EXECUTION_ARNS)),
        ("", []),
        (" , ", []),
    ],
)
def test_get_stored_execution_arns_splits_the_stored_value(
    order, fulfillment_parameters_factory, stored_value, expected
):
    order["agreement"]["parameters"]["fulfillment"] = fulfillment_parameters_factory(
        execution_arn=stored_value
    )

    result = get_stored_execution_arns(order)

    assert result == expected


def test_get_stored_execution_arns_without_agreement_parameters():
    result = get_stored_execution_arns({"id": ORDER_ID, "agreement": {"id": AGREEMENT_ID}})

    assert result == []


def test_build_order_context_keeps_the_order_intact(order, buyer):
    context = build_order_context(order)  # act

    assert context.order_id == ORDER_ID
    assert context.pm_account_id == PMA_ACCOUNT_ID
    assert context.buyer == buyer
    assert order["agreement"]["id"] == AGREEMENT_ID
    assert order["buyer"] == buyer


def test_get_upgrade_request(order):
    order["buyer"] = {
        "id": "BUY-1111-1111",
        "name": "A buyer",
        "externalIds": {"erpCustomer": "US-SCU-999999"},
    }
    context = build_order_context(order)

    result = get_upgrade_request(context)

    assert result == {"scu": "US-SCU-999999", "master_payer_id": MASTER_PAYER_ID}


@pytest.mark.parametrize("external_ids", [{}, {"erpCustomer": ""}, None])
def test_get_upgrade_request_without_scu_raises(order, external_ids):
    order["buyer"] = {"id": "BUY-1111-1111", "name": "A buyer", "externalIds": external_ids}
    context = build_order_context(order)

    with pytest.raises(CloudOrchestratorMissingScuError, match="Buyer SCU is not set"):
        get_upgrade_request(context)


def test_start_upgrade_sends_the_order_data(config, order, buyer, mock_cloud_orchestrator):
    result = start_upgrade(config, order)

    assert result == list(EXECUTION_ARNS)
    mock_cloud_orchestrator.upgrade_customer.assert_called_once_with({
        "scu": buyer["externalIds"]["erpCustomer"],
        "master_payer_id": MASTER_PAYER_ID,
    })


def test_start_upgrade_without_scu_skips_cloud_orchestrator(config, order, mock_cloud_orchestrator):
    order["buyer"] = {"id": "BUY-1111-1111", "name": "Customer"}

    with pytest.raises(CloudOrchestratorMissingScuError):
        start_upgrade(config, order)

    mock_cloud_orchestrator.upgrade_customer.assert_not_called()


def test_start_upgrade_without_executions(mocker, config, order, mock_cloud_orchestrator):
    mock_notify = mocker.patch(
        "swo_aws_extension.flows.cloud_orchestrator_utils.notify_one_time_error"
    )
    mock_cloud_orchestrator.upgrade_customer.return_value = {"executions": []}

    result = start_upgrade(config, order)

    assert result == []
    mock_notify.assert_called_once()


def test_start_upgrade_raises_cloud_orchestrator_error(config, order, mock_cloud_orchestrator):
    mock_cloud_orchestrator.upgrade_customer.side_effect = CloudOrchestratorError("co down")

    with pytest.raises(CloudOrchestratorError):
        start_upgrade(config, order)


def test_store_execution_arns_joins_them_with_commas(mocker, mpt_client, order):
    mock_update_agreement = mocker.patch(
        "swo_aws_extension.flows.jobs.migration_agreement_parameters.update_agreement"
    )

    result = store_execution_arns(mpt_client, order, list(EXECUTION_ARNS))

    assert result is True
    mock_update_agreement.assert_called_once_with(
        mpt_client,
        AGREEMENT_ID,
        parameters={
            ParamPhasesEnum.FULFILLMENT.value: [
                {
                    "externalId": FulfillmentParametersEnum.EXECUTION_ARN.value,
                    "value": STORED_EXECUTION_ARNS,
                }
            ]
        },
    )


def test_get_upgrade_status(config, order, mock_cloud_orchestrator):
    result = get_upgrade_status(config, order, FIRST_EXECUTION_ARN)

    assert result == "running"
    mock_cloud_orchestrator.get_deployment_status.assert_called_once_with(FIRST_EXECUTION_ARN)
