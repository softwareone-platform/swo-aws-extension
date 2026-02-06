from typing import Any
from unittest.mock import MagicMock

import pytest
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.constants import (
    CRM_TICKET_RESOLVED_STATE,
    PhasesEnum,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.processors.querying.aws_customer_roles import (
    AWSCustomerRolesProcessor,
)
from swo_aws_extension.swo.cloud_orchestrator.errors import CloudOrchestratorError


@pytest.fixture
def mock_client() -> MagicMock:
    return MagicMock(spec=MPTClient)


@pytest.fixture
def processor(mock_client: MagicMock, config: Any) -> AWSCustomerRolesProcessor:
    return AWSCustomerRolesProcessor(mock_client, config)


@pytest.fixture
def mock_context() -> MagicMock:
    context = MagicMock(spec=PurchaseContext)
    context.order = {}
    context.order_id = "ORD-123"
    context.aws_apn_client = MagicMock()
    return context


def test_can_process_true(processor: AWSCustomerRolesProcessor, mock_context: MagicMock) -> None:
    mock_context.phase = PhasesEnum.CHECK_CUSTOMER_ROLES

    result = processor.can_process(mock_context)

    assert result is True


def test_can_process_false(processor: AWSCustomerRolesProcessor, mock_context: MagicMock) -> None:
    mock_context.phase = PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT

    result = processor.can_process(mock_context)

    assert result is False


def test_process_customer_roles_deployed(
    mocker: Any,
    processor: AWSCustomerRolesProcessor,
    mock_context: MagicMock,
) -> None:
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_customer_roles.get_mpa_account_id",
        return_value="mpa-account-123",
    )
    mock_co_client = MagicMock()
    mock_co_client.get_bootstrap_role_status.return_value = {"deployed": True}
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_customer_roles.CloudOrchestratorClient",
        return_value=mock_co_client,
    )
    mock_switch = mocker.patch(
        "swo_aws_extension.processors.querying.aws_customer_roles.switch_order_status_to_process_and_notify"
    )
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_customer_roles.get_template_name",
        return_value="TEMPLATE_NAME",
    )

    processor.process(mock_context)  # act

    mock_switch.assert_called_once_with(processor.client, mock_context, "TEMPLATE_NAME")


def test_process_cr_not_deployed_no_timeout(
    mocker: Any,
    processor: AWSCustomerRolesProcessor,
    mock_context: MagicMock,
) -> None:
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_customer_roles.get_mpa_account_id",
        return_value="mpa-account-123",
    )
    mock_co_client = MagicMock()
    mock_co_client.get_bootstrap_role_status.return_value = {"deployed": False}
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_customer_roles.CloudOrchestratorClient",
        return_value=mock_co_client,
    )
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_customer_roles.is_querying_timeout",
        return_value=False,
    )
    mock_switch = mocker.patch(
        "swo_aws_extension.processors.querying.aws_customer_roles.switch_order_status_to_process_and_notify"
    )

    processor.process(mock_context)  # act

    mock_switch.assert_not_called()


def test_process_cr_not_deployed_timeout_reached(
    mocker: Any,
    processor: AWSCustomerRolesProcessor,
    mock_context: MagicMock,
    mock_crm_client: MagicMock,
    order_factory,
    fulfillment_parameters_factory,
) -> None:
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            crm_customer_role_ticket_id="TICKET-123"
        )
    )
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_customer_roles.get_mpa_account_id",
        return_value="mpa-account-123",
    )
    mock_co_client = MagicMock()
    mock_co_client.get_bootstrap_role_status.return_value = {"deployed": False}
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_customer_roles.CloudOrchestratorClient",
        return_value=mock_co_client,
    )
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_customer_roles.is_querying_timeout",
        return_value=True,
    )
    mock_switch = mocker.patch(
        "swo_aws_extension.processors.querying.aws_customer_roles.switch_order_status_to_process_and_notify"
    )
    mock_set_phase = mocker.patch(
        "swo_aws_extension.processors.querying.aws_customer_roles.set_phase"
    )
    mock_update_order = mocker.patch(
        "swo_aws_extension.processors.querying.aws_customer_roles.update_order"
    )
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_customer_roles.get_template_name",
        return_value="TEMPLATE_NAME",
    )
    mock_context.order = order
    mock_update_order.return_value = order
    mock_crm_client.return_value.get_service_request.return_value = {
        "state": "Active",
    }

    processor.process(mock_context)  # act

    mock_switch.assert_called_once_with(processor.client, mock_context, "TEMPLATE_NAME")
    mock_set_phase.assert_called_once_with(mock_context.order, PhasesEnum.CREATE_SUBSCRIPTION)
    mock_update_order.assert_called_once()


def test_process_cr_not_deployed_timeout_reached_to_create_new_ticket(
    mocker: Any,
    processor: AWSCustomerRolesProcessor,
    mock_context: MagicMock,
    mock_crm_client: MagicMock,
    order_factory,
    fulfillment_parameters_factory,
) -> None:
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            crm_customer_role_ticket_id="TICKET-123"
        )
    )
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_customer_roles.get_mpa_account_id",
        return_value="mpa-account-123",
    )
    mock_co_client = MagicMock()
    mock_co_client.get_bootstrap_role_status.return_value = {"deployed": False}
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_customer_roles.CloudOrchestratorClient",
        return_value=mock_co_client,
    )
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_customer_roles.is_querying_timeout",
        side_effect=[True, False],
    )
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_customer_roles.switch_order_status_to_process_and_notify"
    )
    mocker.patch("swo_aws_extension.processors.querying.aws_customer_roles.set_phase")
    mock_update_order = mocker.patch(
        "swo_aws_extension.processors.querying.aws_customer_roles.update_order"
    )
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_customer_roles.get_template_name",
        return_value="TEMPLATE_NAME",
    )
    mock_context.order = order
    mock_update_order.return_value = order
    mock_crm_client.return_value.get_service_request.return_value = {
        "state": CRM_TICKET_RESOLVED_STATE,
    }
    mock_crm_client.return_value.create_service_request.return_value = {"id": "TICKET-999"}

    processor.process(mock_context)  # act

    mock_update_order.assert_called_once()


def test_process_cloud_orchestrator_error(
    mocker: Any,
    processor: AWSCustomerRolesProcessor,
    mock_context: MagicMock,
) -> None:
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_customer_roles.get_mpa_account_id",
        return_value="mpa-account-123",
    )
    mock_co_client = MagicMock()
    mock_co_client.get_bootstrap_role_status.side_effect = CloudOrchestratorError("error")
    mocker.patch(
        "swo_aws_extension.processors.querying.aws_customer_roles.CloudOrchestratorClient",
        return_value=mock_co_client,
    )
    mock_switch = mocker.patch(
        "swo_aws_extension.processors.querying.aws_customer_roles.switch_order_status_to_process_and_notify"
    )

    processor.process(mock_context)  # act

    mock_switch.assert_not_called()
