from unittest.mock import Mock

import pytest

from swo_aws_extension.constants import SWO_EXTENSION_MANAGEMENT_ROLE
from swo_aws_extension.flows.order import InitialAWSContext, TerminateContext
from swo_aws_extension.flows.steps.finops import (
    CreateFinOpsEntitlementStep,
    CreateFinOpsMPAEntitlementStep,
    DeleteFinOpsEntitlementsStep,
    create_finops_entitlement,
    have_active_accounts,
)


@pytest.fixture
def next_step():
    return Mock()


def test_create_finops_entitlement_existing(ffc_client):
    account_id = "test_account_id"
    buyer_id = "test_buyer_id"
    logger_header = "test_header"
    existing_entitlement = {"id": "existing_entitlement_id"}

    ffc_client.get_entitlement_by_datasource_id.return_value = existing_entitlement

    create_finops_entitlement(ffc_client, account_id, buyer_id, logger_header)

    ffc_client.get_entitlement_by_datasource_id.assert_called_once_with(account_id)
    ffc_client.create_entitlement.assert_not_called()


def test_create_finops_entitlement_new(ffc_client):
    account_id = "test_account_id"
    buyer_id = "test_buyer_id"
    logger_header = "test_header"
    new_entitlement = {"id": "new_entitlement_id"}

    ffc_client.get_entitlement_by_datasource_id.return_value = None
    ffc_client.create_entitlement.return_value = new_entitlement

    create_finops_entitlement(ffc_client, account_id, buyer_id, logger_header)

    ffc_client.get_entitlement_by_datasource_id.assert_called_once_with(account_id)
    ffc_client.create_entitlement.assert_called_once_with(buyer_id, account_id)


def test_create_finops_entitlement_step(
    mocker,
    ffc_client,
    order_factory,
    subscription_factory,
    fulfillment_parameters_factory,
):
    mocker.patch("swo_aws_extension.flows.steps.finops.get_ffc_client", return_value=ffc_client)
    order = order_factory(
        subscriptions=[
            subscription_factory(vendor_id="account_id_1", status="Terminating"),
            subscription_factory(vendor_id="account_id_2", status="Terminating"),
        ],
        fulfillment_parameters=fulfillment_parameters_factory(phase=""),
    )
    context = InitialAWSContext.from_order_data(order)
    context.buyer = {"id": "buyer_id"}
    next_step = Mock()
    ffc_client.get_entitlement_by_datasource_id.return_value = None
    ffc_client.create_entitlement.return_value = {
        "id": "entitlement_id",
        "status": "new",
    }
    step = CreateFinOpsEntitlementStep()
    step(Mock(), context, next_step)

    assert ffc_client.get_entitlement_by_datasource_id.call_count == 2
    assert ffc_client.create_entitlement.call_count == 2
    next_step.assert_called_once()


def test_create_finops_mpa_entitlement_step(
    mocker,
    ffc_client,
    order_factory,
    fulfillment_parameters_factory,
    agreement_factory,
    subscription_factory,
):
    mocker.patch("swo_aws_extension.flows.steps.finops.get_ffc_client", return_value=ffc_client)
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(phase=""),
        agreement=agreement_factory(vendor_id="mpa_account_id"),
        subscriptions=subscription_factory(status="Terminating"),
    )
    context = InitialAWSContext.from_order_data(order)
    context.buyer = {"id": "buyer_id"}
    next_step = Mock()
    ffc_client.get_entitlement_by_datasource_id.return_value = None
    ffc_client.create_entitlement.return_value = {
        "id": "entitlement_id",
        "status": "new",
    }
    step = CreateFinOpsMPAEntitlementStep()
    step(Mock(), context, next_step)

    ffc_client.get_entitlement_by_datasource_id.assert_called_once_with("mpa_account_id")
    ffc_client.create_entitlement.assert_called_once_with("buyer_id", "mpa_account_id")
    next_step.assert_called_once()


def test_have_active_accounts(
    mocker, aws_client_factory, config, aws_accounts_factory, data_aws_account_factory
):
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mpa_account_id = "mpa_account_id"
    mock_client.list_accounts.return_value = aws_accounts_factory(
        accounts=[
            data_aws_account_factory(aws_id=mpa_account_id),
            data_aws_account_factory(aws_id="account_1"),
            data_aws_account_factory(aws_id="account_2", status="SUSPENDED"),
        ]
    )

    result = have_active_accounts(aws_client, mpa_account_id)

    assert result is True
    mock_client.list_accounts.assert_called_once()


def test_have_active_accounts_no_active(mocker, aws_client_factory, config, aws_accounts_factory):
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mpa_account_id = "mpa_account_id"
    mock_client.list_accounts.return_value = aws_accounts_factory(status="SUSPENDED")

    result = have_active_accounts(aws_client, mpa_account_id)

    assert result is False
    mock_client.list_accounts.assert_called_once()


def test_delete_finops_entitlements_step_new_status(
    mocker,
    ffc_client,
    next_step,
    aws_accounts_factory,
    config,
    aws_client_factory,
    order_factory,
    subscription_factory,
):
    mocker.patch("swo_aws_extension.flows.steps.finops.get_ffc_client", return_value=ffc_client)
    ffc_client.get_entitlement_by_datasource_id.return_value = {
        "id": "entitlement_id",
        "status": "new",
    }
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mock_client.list_accounts.return_value = aws_accounts_factory(status="ACTIVE")
    step = DeleteFinOpsEntitlementsStep()
    order = order_factory(subscriptions=[subscription_factory(status="Terminating")])
    terminate_context = TerminateContext.from_order_data(order)
    terminate_context.aws_client = aws_client
    step(Mock(), terminate_context, next_step)

    assert ffc_client.get_entitlement_by_datasource_id.call_count == 1
    assert ffc_client.delete_entitlement.call_count == 1
    ffc_client.terminate_entitlement.assert_not_called()
    next_step.assert_called_once()


def test_delete_finops_entitlements_step_active_status(
    mocker,
    ffc_client,
    next_step,
    aws_accounts_factory,
    config,
    aws_client_factory,
    order_factory,
    subscription_factory,
):
    mocker.patch("swo_aws_extension.flows.steps.finops.get_ffc_client", return_value=ffc_client)
    ffc_client.get_entitlement_by_datasource_id.return_value = {
        "id": "entitlement_id",
        "status": "active",
    }
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mock_client.list_accounts.return_value = aws_accounts_factory(status="SUSPENDED")
    step = DeleteFinOpsEntitlementsStep()
    order = order_factory(subscriptions=[subscription_factory(status="Terminating")])
    terminate_context = TerminateContext.from_order_data(order)
    terminate_context.aws_client = aws_client
    step(Mock(), terminate_context, next_step)

    assert ffc_client.get_entitlement_by_datasource_id.call_count == 1
    assert ffc_client.terminate_entitlement.call_count == 2
    ffc_client.delete_entitlement.assert_not_called()
    next_step.assert_called_once()


def test_delete_finops_entitlements_step_no_entitlement(
    mocker,
    ffc_client,
    next_step,
    aws_accounts_factory,
    config,
    aws_client_factory,
    order_factory,
    subscription_factory,
):
    mocker.patch("swo_aws_extension.flows.steps.finops.get_ffc_client", return_value=ffc_client)
    ffc_client.get_entitlement_by_datasource_id.return_value = None
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", SWO_EXTENSION_MANAGEMENT_ROLE
    )
    mock_client.list_accounts.return_value = aws_accounts_factory(status="ACTIVE")
    step = DeleteFinOpsEntitlementsStep()
    order = order_factory(subscriptions=[subscription_factory(status="Terminating")])
    terminate_context = TerminateContext.from_order_data(order)
    terminate_context.aws_client = aws_client
    step(Mock(), terminate_context, next_step)

    assert ffc_client.get_entitlement_by_datasource_id.call_count == 1
    ffc_client.delete_entitlement.assert_not_called()
    ffc_client.terminate_entitlement.assert_not_called()
    next_step.assert_called_once()
