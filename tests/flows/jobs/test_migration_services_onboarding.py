import pytest

from swo_aws_extension.constants import (
    CLOUD_ORCHESTRATOR_ONBOARDING_TYPE,
    DEFAULT_SCU,
    FulfillmentParametersEnum,
    ParamPhasesEnum,
)
from swo_aws_extension.flows.jobs.migration_services_onboarding import (
    build_order_context,
    get_onboarding_status,
    get_stored_execution_arn,
    start_onboarding,
    store_execution_arn,
)
from swo_aws_extension.swo.cloud_orchestrator.errors import CloudOrchestratorError

ORDER_ID = "ORD-0792-5000-2253-4210"
AGREEMENT_ID = "AGR-2119-4550-8674-5962"
PMA_ACCOUNT_ID = "123456789012"
EXECUTION_ARN = "arn:aws:states:us-east-1:123456789012:execution:onboard:abc123"


@pytest.fixture
def order(buyer, seller, fulfillment_parameters_factory, order_parameters_factory):
    return {
        "id": ORDER_ID,
        "parameters": {
            "ordering": order_parameters_factory(),
            "fulfillment": fulfillment_parameters_factory(),
        },
        "authorization": {"externalIds": {"operations": PMA_ACCOUNT_ID}},
        "agreement": {
            "id": AGREEMENT_ID,
            "parameters": {
                "ordering": [],
                "fulfillment": fulfillment_parameters_factory(execution_arn=EXECUTION_ARN),
            },
        },
        "buyer": buyer,
        "seller": seller,
    }


@pytest.fixture
def mock_cloud_orchestrator(mocker):
    mock_client = mocker.patch(
        "swo_aws_extension.flows.cloud_orchestrator_utils.CloudOrchestratorClient"
    ).return_value
    mock_client.onboard_customer.return_value = {"execution_arn": EXECUTION_ARN}
    mock_client.get_deployment_status.return_value = {"status": "RUNNING"}
    return mock_client


def test_get_stored_execution_arn(order):
    result = get_stored_execution_arn(order)

    assert result == EXECUTION_ARN


def test_get_stored_execution_arn_without_agreement_parameters():
    result = get_stored_execution_arn({"id": ORDER_ID, "agreement": {"id": AGREEMENT_ID}})

    assert result is None


def test_build_order_context_keeps_the_order_intact(order, buyer):
    context = build_order_context(order)  # act

    assert context.order_id == ORDER_ID
    assert context.pm_account_id == PMA_ACCOUNT_ID
    assert context.buyer == buyer
    assert order["agreement"]["id"] == AGREEMENT_ID
    assert order["buyer"] == buyer


def test_start_onboarding_sends_the_order_data(config, order, buyer, mock_cloud_orchestrator):
    result = start_onboarding(config, order)

    assert result == EXECUTION_ARN
    mock_cloud_orchestrator.onboard_customer.assert_called_once_with({
        "customer": buyer["name"],
        "scu": buyer["externalIds"]["erpCustomer"],
        "pma": PMA_ACCOUNT_ID,
        "master_payer_id": "651706759263",
        "support_type": "PartnerLedSupport",
        "onboarding_type": CLOUD_ORCHESTRATOR_ONBOARDING_TYPE,
    })


def test_start_onboarding_without_scu_uses_the_default(config, order, mock_cloud_orchestrator):
    order["buyer"] = {"name": "Customer"}

    start_onboarding(config, order)  # act

    onboard_payload = mock_cloud_orchestrator.onboard_customer.call_args.args[0]
    assert onboard_payload["scu"] == DEFAULT_SCU


def test_start_onboarding_without_execution_arn(config, order, mock_cloud_orchestrator):
    mock_cloud_orchestrator.onboard_customer.return_value = {}

    result = start_onboarding(config, order)

    assert not result


def test_start_onboarding_raises_cloud_orchestrator_error(config, order, mock_cloud_orchestrator):
    mock_cloud_orchestrator.onboard_customer.side_effect = CloudOrchestratorError("co down")

    with pytest.raises(CloudOrchestratorError):
        start_onboarding(config, order)


def test_store_execution_arn(mocker, mpt_client, order):
    mock_update_agreement = mocker.patch(
        "swo_aws_extension.flows.jobs.migration_agreement_parameters.update_agreement"
    )

    result = store_execution_arn(mpt_client, order, EXECUTION_ARN)

    assert result is True
    mock_update_agreement.assert_called_once_with(
        mpt_client,
        AGREEMENT_ID,
        parameters={
            ParamPhasesEnum.FULFILLMENT.value: [
                {
                    "externalId": FulfillmentParametersEnum.EXECUTION_ARN.value,
                    "value": EXECUTION_ARN,
                }
            ]
        },
    )


def test_get_onboarding_status(config, order, mock_cloud_orchestrator):
    result = get_onboarding_status(config, order, EXECUTION_ARN)

    assert result == "running"
    mock_cloud_orchestrator.get_deployment_status.assert_called_once_with(EXECUTION_ARN)
