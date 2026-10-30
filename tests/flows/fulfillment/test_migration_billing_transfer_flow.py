import logging
from http import HTTPStatus

import pytest
from botocore.exceptions import ClientError
from freezegun import freeze_time

from swo_aws_extension.constants import (
    AccountTypesEnum,
    MigrationOrderEnum,
    OrderParametersEnum,
    OrderProcessingTemplateEnum,
    OrderQueryingTemplateEnum,
    PhasesEnum,
)
from swo_aws_extension.flows.fulfillment.base import fulfill_order
from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps.errors import ERR_CREATING_INVITATION_RESPONSE
from swo_aws_extension.parameters import get_ordering_parameter

ORDER_ID = "ORD-9010-0127-1948"
PRODUCT_ID = "PRD-1111-1111"
MPA_ID = "651706759263"
MPA_PARAMETER = OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID.value
PM_ACCOUNT_ID = "123456789012"
START_TIMESTAMP = 1767225600
INVITE_OPERATION = "InviteOrganizationToTransferResponsibility"
INELIGIBLE_MESSAGE = (
    "Ineligible for Billing Transfer. Your organization is subject to a pricing agreement"
    " with AWS that Billing Transfer does not support."
)
INELIGIBLE_FAIL_MESSAGE = (
    f"Billing transfer is not possible for account {MPA_ID}: {INELIGIBLE_MESSAGE}"
)
OTHER_CONSTRAINT_MESSAGE = "You have reached the limit of pending billing transfer invitations."
OTHER_CONSTRAINT_AWS_ERROR = (
    "AWS Client error. An error occurred (ConstraintViolationException) when calling the"
    f" {INVITE_OPERATION} operation: {OTHER_CONSTRAINT_MESSAGE}"
)
OTHER_CONSTRAINT_QUERYING_LOG = (
    "Querying due to error inviting organization to transfer billing responsibility:"
    f" {OTHER_CONSTRAINT_AWS_ERROR}"
)


# ConstraintViolationException is the name boto3 gives to the modeled error raised by
# InviteOrganizationToTransferResponsibility when the organization cannot transfer billing:
# https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/organizations/client/invite_organization_to_transfer_responsibility.html
class ConstraintViolationException(ClientError):  # ruff:ignore[error-suffix-on-exception-name]
    """Dummy exception for testing purposes."""


@pytest.fixture
def constraint_violation_factory():
    def factory(message):
        return ConstraintViolationException(
            {
                "Error": {"Code": "ConstraintViolationException", "Message": message},
                "Message": message,
                "ResponseMetadata": {"HTTPStatusCode": HTTPStatus.BAD_REQUEST},
            },
            INVITE_OPERATION,
        )

    return factory


@pytest.fixture
def organizations_client(aws_client_factory, config):
    _, boto3_client = aws_client_factory(config, PM_ACCOUNT_ID, config.management_role_name)
    boto3_client.exceptions.ConstraintViolationException = ConstraintViolationException
    return boto3_client


@pytest.fixture
def migration_order(
    order_factory, order_parameters_factory, fulfillment_parameters_factory, template_factory
):
    return order_factory(
        order_id=ORDER_ID,
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_AWS_ENVIRONMENT.value,
            mpa_id=MPA_ID,
            migration=MigrationOrderEnum.YES.value,
            constraints={"hidden": False, "readonly": False, "required": False},
        ),
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_BILLING_TRANSFER_INVITATION.value,
            responsibility_transfer_id="",
            cco_contract_number="CCO-1",
            support_discount="10",
            service_discount="2.5",
        ),
        template=template_factory(
            name=OrderProcessingTemplateEnum.MIGRATION.value, template_type="OrderProcessing"
        ),
        authorization_external_id=PM_ACCOUNT_ID,
    )


@pytest.fixture
def querying_template(template_factory):
    return template_factory(
        name=OrderQueryingTemplateEnum.INVALID_ACCOUNT_ID.value, template_type="OrderQuerying"
    )


@pytest.fixture
def mock_get_agreements_by_query(mocker):
    return mocker.patch(
        "swo_aws_extension.flows.order_utils.get_agreements_by_query",
        autospec=True,
        return_value=[],
    )


@pytest.fixture
def mock_get_product_template(mocker, querying_template):
    return mocker.patch(
        "swo_aws_extension.flows.order_utils.get_product_template_or_default",
        autospec=True,
        return_value=querying_template,
    )


@pytest.fixture
def mock_query_order(mocker):
    return mocker.patch("swo_aws_extension.flows.order_utils.query_order", autospec=True)


@pytest.fixture
def mock_fail_order(mocker):
    return mocker.patch("swo_aws_extension.flows.order_utils.fail_order", autospec=True)


@pytest.fixture
def mock_step_notify_one_time_error(mocker):
    return mocker.patch("swo_aws_extension.flows.steps.base.notify_one_time_error", autospec=True)


@pytest.fixture
def mock_pipeline_notify_one_time_error(mocker):
    return mocker.patch(
        "swo_aws_extension.flows.fulfillment.pipelines.notify_one_time_error", autospec=True
    )


@freeze_time("2025-12-22 00:00:00")
@pytest.mark.usefixtures("requests_mocker", "mock_get_agreements_by_query")
def test_migration_flow_fails_order_when_ineligible_for_billing_transfer(
    caplog,
    mocker,
    mpt_client,
    migration_order,
    organizations_client,
    constraint_violation_factory,
    mock_get_product_template,
    mock_query_order,
    mock_fail_order,
    mock_step_notify_one_time_error,
    mock_pipeline_notify_one_time_error,
):
    caplog.set_level(logging.INFO, logger="swo_aws_extension.flows.steps.base")
    organizations_client.invite_organization_to_transfer_responsibility.side_effect = (
        constraint_violation_factory(INELIGIBLE_MESSAGE)
    )
    context = InitialAWSContext.from_order_data(migration_order)

    fulfill_order(mpt_client, context)  # act

    organizations_client.invite_organization_to_transfer_responsibility.assert_called_once_with(
        Type="BILLING",
        Target={"Id": MPA_ID, "Type": "ACCOUNT"},
        StartTimestamp=START_TIMESTAMP,
        SourceName="Transfer Billing - A buyer",
    )
    mock_fail_order.assert_called_once_with(
        mpt_client,
        ORDER_ID,
        {"id": "AWS006", "message": INELIGIBLE_FAIL_MESSAGE},
        parameters=mocker.ANY,
    )
    fail_parameters = mock_fail_order.call_args.kwargs
    assert get_ordering_parameter(MPA_PARAMETER, fail_parameters)["error"] is None
    assert f"{ORDER_ID} - Fail Order: {INELIGIBLE_FAIL_MESSAGE}" in caplog.text
    mock_get_product_template.assert_not_called()
    mock_query_order.assert_not_called()
    mock_step_notify_one_time_error.assert_not_called()
    mock_pipeline_notify_one_time_error.assert_not_called()


@freeze_time("2025-12-22 00:00:00")
@pytest.mark.usefixtures("requests_mocker", "mock_get_agreements_by_query")
def test_migration_flow_queries_order_on_other_constraint_violation(
    caplog,
    mocker,
    mpt_client,
    migration_order,
    organizations_client,
    constraint_violation_factory,
    querying_template,
    mock_get_product_template,
    mock_query_order,
    mock_fail_order,
    mock_step_notify_one_time_error,
    mock_pipeline_notify_one_time_error,
):
    caplog.set_level(logging.INFO, logger="swo_aws_extension.flows.steps.base")
    organizations_client.invite_organization_to_transfer_responsibility.side_effect = (
        constraint_violation_factory(OTHER_CONSTRAINT_MESSAGE)
    )
    context = InitialAWSContext.from_order_data(migration_order)
    expected_error = ERR_CREATING_INVITATION_RESPONSE.to_dict(
        mpa_id=MPA_ID, error=OTHER_CONSTRAINT_AWS_ERROR
    )

    fulfill_order(mpt_client, context)  # act

    organizations_client.invite_organization_to_transfer_responsibility.assert_called_once_with(
        Type="BILLING",
        Target={"Id": MPA_ID, "Type": "ACCOUNT"},
        StartTimestamp=START_TIMESTAMP,
        SourceName="Transfer Billing - A buyer",
    )
    mock_get_product_template.assert_called_once_with(
        mpt_client, PRODUCT_ID, "Querying", OrderQueryingTemplateEnum.INVALID_ACCOUNT_ID.value
    )
    mock_query_order.assert_called_once_with(
        mpt_client, ORDER_ID, parameters=mocker.ANY, template=querying_template
    )
    query_parameters = mock_query_order.call_args.kwargs
    assert get_ordering_parameter(MPA_PARAMETER, query_parameters)["error"] == expected_error
    assert OTHER_CONSTRAINT_QUERYING_LOG in caplog.text
    mock_fail_order.assert_not_called()
    mock_step_notify_one_time_error.assert_not_called()
    mock_pipeline_notify_one_time_error.assert_not_called()
