import re

import pytest

from swo_aws_extension.constants import (
    CLOUD_ORCHESTRATOR_ONBOARDING_TYPE,
    DeploymentStatusEnum,
    SupportTypesEnum,
)
from swo_aws_extension.flows.cloud_orchestrator_utils import (
    check_onboard_status,
    get_buyer_scu,
    get_feature_version_onboard_request,
    onboard,
    upgrade,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.swo.cloud_orchestrator.client import CloudOrchestratorClient
from swo_aws_extension.swo.cloud_orchestrator.errors import CloudOrchestratorMissingScuError

MODULE = "swo_aws_extension.flows.cloud_orchestrator_utils"
EXECUTION_PREFIX = "arn:aws:states:eu-west-1:822835360798:execution"
FIRST_EXECUTION_ARN = f"{EXECUTION_PREFIX}:deployment-1155d5f6:execution-54b05eea"
SECOND_EXECUTION_ARN = f"{EXECUTION_PREFIX}:deployment-bf570ae0:execution-789355e7"
EXECUTION_ARNS = (FIRST_EXECUTION_ARN, SECOND_EXECUTION_ARN)
BUYER_SCU = "US-SCU-111111"
MISSING_SCU_MESSAGE = (
    "Buyer SCU is not set for order ORD-0792-5000-2253-4210 (MPA 123456789012, buyer BUY-1111-1111)"
)


@pytest.fixture
def scu_buyer(buyer_factory):
    return {**buyer_factory(), "externalIds": {"erpCustomer": BUYER_SCU}}


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


def test_onboard(mocker, config):
    co_client_mock = mocker.MagicMock(spec=CloudOrchestratorClient)
    co_client_mock.onboard_customer.return_value = {
        "execution_arn": "arn:aws:states:us-east-1:123456789012:execution:test"
    }
    mocker.patch(f"{MODULE}.CloudOrchestratorClient", return_value=co_client_mock)

    result = onboard(config, {"payload": "data"}, "ORD-001")  # act

    assert result == "arn:aws:states:us-east-1:123456789012:execution:test"
    co_client_mock.onboard_customer.assert_called_once_with({"payload": "data"})


def test_onboard_missing_execution_arn(mocker, config, caplog):
    co_client_mock = mocker.MagicMock(spec=CloudOrchestratorClient)
    co_client_mock.onboard_customer.return_value = {}
    mocker.patch(f"{MODULE}.CloudOrchestratorClient", return_value=co_client_mock)

    result = onboard(config, {"payload": "data"}, "ORD-001")  # act

    assert not result
    assert "ORD-001 - Onboard response missing execution_arn" in caplog.text


def test_onboard_request_pls(order_factory, order_parameters_factory, scu_buyer):
    order = order_factory(
        order_parameters=order_parameters_factory(
            mpa_id="123456789012",
            support_type=SupportTypesEnum.PARTNER_LED_SUPPORT.value,
        ),
        buyer=scu_buyer,
    )
    context = PurchaseContext.from_order_data(order)

    result = get_feature_version_onboard_request(context)

    assert result["customer"] == "A buyer"
    assert result["scu"] == BUYER_SCU
    assert result["pma"] == "123456789012"
    assert result["master_payer_id"] == "123456789012"
    assert result["support_type"] == SupportTypesEnum.PARTNER_LED_SUPPORT.value
    assert result["onboarding_type"] == CLOUD_ORCHESTRATOR_ONBOARDING_TYPE


def test_onboard_request_resold_support(order_factory, order_parameters_factory, scu_buyer):
    order = order_factory(
        order_parameters=order_parameters_factory(
            mpa_id="123456789012",
            support_type=SupportTypesEnum.AWS_RESOLD_SUPPORT.value,
        ),
        buyer=scu_buyer,
    )
    context = PurchaseContext.from_order_data(order)

    result = get_feature_version_onboard_request(context)

    assert result["customer"] == "A buyer"
    assert result["scu"] == BUYER_SCU
    assert result["pma"] == "123456789012"
    assert result["master_payer_id"] == "123456789012"
    assert result["support_type"] == SupportTypesEnum.AWS_RESOLD_SUPPORT.value
    assert result["onboarding_type"] == CLOUD_ORCHESTRATOR_ONBOARDING_TYPE


def test_onboard_request_master_payer_id(order_factory, order_parameters_factory, scu_buyer):
    order = order_factory(
        order_parameters=order_parameters_factory(mpa_id="123456789012"),
        buyer=scu_buyer,
    )
    context = PurchaseContext.from_order_data(order)

    result = get_feature_version_onboard_request(context)

    assert result["customer"] == "A buyer"
    assert result["scu"] == BUYER_SCU
    assert result["pma"] == "123456789012"
    assert result["master_payer_id"] == "123456789012"
    assert result["support_type"] == SupportTypesEnum.PARTNER_LED_SUPPORT.value
    assert result["onboarding_type"] == CLOUD_ORCHESTRATOR_ONBOARDING_TYPE


def test_onboard_request_customer_name(order_factory, order_parameters_factory, buyer_factory):
    buyer = {**buyer_factory(name="Acme Corp"), "externalIds": {"erpCustomer": BUYER_SCU}}
    order = order_factory(
        order_parameters=order_parameters_factory(mpa_id="123456789012"),
        buyer=buyer,
    )
    context = PurchaseContext.from_order_data(order)

    result = get_feature_version_onboard_request(context)

    assert result["customer"] == "Acme Corp"
    assert result["scu"] == BUYER_SCU
    assert result["pma"] == "123456789012"
    assert result["master_payer_id"] == "123456789012"
    assert result["support_type"] == SupportTypesEnum.PARTNER_LED_SUPPORT.value
    assert result["onboarding_type"] == CLOUD_ORCHESTRATOR_ONBOARDING_TYPE


def test_onboard_request_customer_scu(order_factory, order_parameters_factory):
    buyer = {
        "id": "BUY-1111-1111",
        "name": "A buyer",
        "externalIds": {"erpCustomer": "US-SCU-999999"},
    }
    order = order_factory(
        order_parameters=order_parameters_factory(mpa_id="123456789012"),
        buyer=buyer,
    )
    context = PurchaseContext.from_order_data(order)

    result = get_feature_version_onboard_request(context)

    assert result["customer"] == "A buyer"
    assert result["scu"] == "US-SCU-999999"
    assert result["pma"] == "123456789012"
    assert result["master_payer_id"] == "123456789012"
    assert result["support_type"] == SupportTypesEnum.PARTNER_LED_SUPPORT.value
    assert result["onboarding_type"] == CLOUD_ORCHESTRATOR_ONBOARDING_TYPE


def test_onboard_request_without_scu_raises(order_factory, order_parameters_factory):
    order = order_factory(order_parameters=order_parameters_factory(mpa_id="123456789012"))
    context = PurchaseContext.from_order_data(order)

    with pytest.raises(CloudOrchestratorMissingScuError, match=re.escape(MISSING_SCU_MESSAGE)):
        get_feature_version_onboard_request(context)


def test_get_buyer_scu(order_factory, scu_buyer):
    context = PurchaseContext.from_order_data(order_factory(buyer=scu_buyer))

    result = get_buyer_scu(context)

    assert result == BUYER_SCU


@pytest.mark.parametrize(
    "buyer_without_scu",
    [
        {"id": "BUY-1111-1111", "name": "A buyer"},
        {"id": "BUY-1111-1111", "name": "A buyer", "externalIds": None},
        {"id": "BUY-1111-1111", "name": "A buyer", "externalIds": {}},
        {"id": "BUY-1111-1111", "name": "A buyer", "externalIds": {"erpCustomer": ""}},
    ],
)
def test_get_buyer_scu_without_scu_raises(
    order_factory, order_parameters_factory, buyer_without_scu
):
    order = order_factory(
        order_parameters=order_parameters_factory(mpa_id="123456789012"),
        buyer=buyer_without_scu,
    )
    context = PurchaseContext.from_order_data(order)

    with pytest.raises(CloudOrchestratorMissingScuError, match=re.escape(MISSING_SCU_MESSAGE)):
        get_buyer_scu(context)


def test_upgrade_returns_every_execution_arn(mocker, config, upgrade_response):
    notify_mock = mocker.patch(f"{MODULE}.notify_one_time_error")
    co_client_mock = mocker.MagicMock(spec=CloudOrchestratorClient)
    co_client_mock.upgrade_customer.return_value = upgrade_response
    mocker.patch(f"{MODULE}.CloudOrchestratorClient", return_value=co_client_mock)

    result = upgrade(config, {"payload": "data"}, "ORD-001")  # act

    assert result == list(EXECUTION_ARNS)
    co_client_mock.upgrade_customer.assert_called_once_with({"payload": "data"})
    notify_mock.assert_not_called()


def test_upgrade_skips_executions_without_arn(mocker, config, caplog):
    co_client_mock = mocker.MagicMock(spec=CloudOrchestratorClient)
    co_client_mock.upgrade_customer.return_value = {
        "executions": [
            {"deployment_id": "f54e1c4b-3d90-4489-8ec6-f2b1157daf3b"},
            {"execution_arn": "", "deployment_id": "0c1d7a6e-5b2f-4c3d-9e8f-7a6b5c4d3e2f"},
            {
                "execution_arn": SECOND_EXECUTION_ARN,
                "deployment_id": "5fb1a5e9-2678-4cd1-92f0-830559483b4d",
            },
        ]
    }
    mocker.patch(f"{MODULE}.CloudOrchestratorClient", return_value=co_client_mock)

    result = upgrade(config, {"payload": "data"}, "ORD-001")  # act

    assert result == [SECOND_EXECUTION_ARN]
    assert "returned no execution ARNs" not in caplog.text


@pytest.mark.parametrize(
    "upgrade_response",
    [
        {},
        {"executions": []},
        {"executions": None},
        {"executions": [{"deployment_id": "f54e1c4b-3d90-4489-8ec6-f2b1157daf3b"}]},
    ],
)
def test_upgrade_missing_execution_arns(mocker, config, caplog, upgrade_response):
    co_client_mock = mocker.MagicMock(spec=CloudOrchestratorClient)
    co_client_mock.upgrade_customer.return_value = upgrade_response
    mocker.patch(f"{MODULE}.CloudOrchestratorClient", return_value=co_client_mock)
    notify_mock = mocker.patch(f"{MODULE}.notify_one_time_error")

    result = upgrade(config, {"payload": "data"}, "ORD-001")  # act

    assert result == []
    assert (
        "ORD-001 - Cloud Orchestrator upgrade returned no execution ARNs: expected "
        "executions[].execution_arn in the response, nothing to poll. "
        f"Response: {upgrade_response}"
    ) in caplog.text
    notify_mock.assert_called_once_with(
        "Cloud Orchestrator upgrade error for order ORD-001",
        "Cloud Orchestrator upgrade for order `ORD-001` returned no execution ARNs. "
        "Expected `executions[].execution_arn` in the response. There is nothing to poll.\n\n"
        f"```{upgrade_response}```",
    )


def test_onboard_status_succeeds_immediately(mocker, config, order_factory):
    order = order_factory()
    context = PurchaseContext.from_order_data(order)
    co_client_mock = mocker.MagicMock(spec=CloudOrchestratorClient)
    co_client_mock.get_deployment_status.return_value = {
        "status": DeploymentStatusEnum.SUCCEEDED.value
    }
    mocker.patch(f"{MODULE}.CloudOrchestratorClient", return_value=co_client_mock)

    result = check_onboard_status(config, context, "arn:test")

    assert result == DeploymentStatusEnum.SUCCEEDED.value
    co_client_mock.get_deployment_status.assert_called_once_with("arn:test")


def test_check_onboard_status_failed_immediately(mocker, config, order_factory):
    order = order_factory()
    context = PurchaseContext.from_order_data(order)
    co_client_mock = mocker.MagicMock(spec=CloudOrchestratorClient)
    co_client_mock.get_deployment_status.return_value = {
        "status": DeploymentStatusEnum.FAILED.value
    }
    mocker.patch(f"{MODULE}.CloudOrchestratorClient", return_value=co_client_mock)

    result = check_onboard_status(config, context, "arn:test")

    assert result == DeploymentStatusEnum.FAILED.value
    co_client_mock.get_deployment_status.assert_called_once_with("arn:test")


def test_check_onboard_status_running(mocker, config, order_factory):
    order = order_factory()
    context = PurchaseContext.from_order_data(order)
    co_client_mock = mocker.MagicMock(spec=CloudOrchestratorClient)
    co_client_mock.get_deployment_status.return_value = {
        "status": DeploymentStatusEnum.RUNNING.value
    }
    mocker.patch(f"{MODULE}.CloudOrchestratorClient", return_value=co_client_mock)

    result = check_onboard_status(config, context, "arn:test")

    assert result == DeploymentStatusEnum.RUNNING.value
    co_client_mock.get_deployment_status.assert_called_once_with("arn:test")


def test_check_onboard_status_empty_status(mocker, config, order_factory):
    order = order_factory()
    context = PurchaseContext.from_order_data(order)
    co_client_mock = mocker.MagicMock(spec=CloudOrchestratorClient)
    co_client_mock.get_deployment_status.return_value = {"status": ""}
    mocker.patch(f"{MODULE}.CloudOrchestratorClient", return_value=co_client_mock)

    result = check_onboard_status(config, context, "arn:test")

    assert not result
    co_client_mock.get_deployment_status.assert_called_once_with("arn:test")
