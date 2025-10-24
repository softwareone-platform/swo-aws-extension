import json

import pytest
from mpt_extension_sdk.flows.context import ORDER_TYPE_PURCHASE
from mpt_extension_sdk.flows.pipeline import Pipeline
from requests import RequestException, Response

from swo_aws_extension.constants import (
    HTTP_STATUS_BAD_REQUEST,
    HTTP_STATUS_OK,
    AccountTypesEnum,
    AwsHandshakeStateEnum,
    OrderProcessingTemplateEnum,
    PhasesEnum,
    TransferTypesEnum,
)
from swo_aws_extension.flows.jobs.process_aws_invitations import (
    AWSInvitationsProcessor,
    CheckInvitationLinksStep,
)
from swo_aws_extension.flows.order import MPT_ORDER_STATUS_QUERYING, PurchaseContext


@pytest.fixture
def aws_invitation_processor_factory(mocker, mpt_client, config):
    def _aws_invitation_processor(query_orders=None):
        if query_orders is not None:
            mocker.patch(
                "swo_aws_extension.flows.jobs.process_aws_invitations.AWSInvitationsProcessor.get_querying_orders",
                return_value=query_orders,
            )
        return AWSInvitationsProcessor(mpt_client, config)

    return _aws_invitation_processor


@pytest.fixture
def aws_invitation_processor(aws_invitation_processor_factory, fulfillment_parameters_factory):
    return aws_invitation_processor_factory()


def test_check_invitation_links_step(mocker, order_factory, fulfillment_parameters_factory):
    next_step = mocker.MagicMock()
    client = mocker.MagicMock()

    step = CheckInvitationLinksStep()
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_SUBSCRIPTIONS.value,
        )
    )
    context = PurchaseContext.from_order_data(order)
    step(client, context, next_step)
    next_step.assert_not_called()

    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.ASSIGN_MPA.value,
        )
    )
    context = PurchaseContext.from_order_data(order)
    step(client, context, next_step)
    next_step.assert_not_called()


def test_aws_invitation_processor_calls_pipeline(
    mocker,
    config,
    mpt_client,
    aws_invitation_processor_factory,
    order_factory,
    order_parameters_factory,
    fulfillment_parameters_factory,
):
    processor = aws_invitation_processor_factory(
        query_orders=[
            order_factory(
                order_type=ORDER_TYPE_PURCHASE,
                status=MPT_ORDER_STATUS_QUERYING,
                order_parameters=order_parameters_factory(
                    account_type=AccountTypesEnum.EXISTING_ACCOUNT.value,
                    transfer_type=TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION.value,
                    account_id="123456789012",
                ),
                fulfillment_parameters=fulfillment_parameters_factory(
                    phase=PhasesEnum.CHECK_INVITATION_LINK.value
                ),
            ),
        ]
    )
    pipeline = mocker.MagicMock(spec=Pipeline)
    processor.get_pipeline = mocker.MagicMock(return_value=pipeline)
    processor.process_aws_invitations()
    pipeline.run.assert_called_once()


def test_aws_invitation_processor_skips_pipeline(
    mocker,
    config,
    mpt_client,
    aws_invitation_processor_factory,
    order_factory,
    order_parameters_factory,
    fulfillment_parameters_factory,
):
    processor = aws_invitation_processor_factory(
        query_orders=[
            order_factory(
                order_type=ORDER_TYPE_PURCHASE,
                status=MPT_ORDER_STATUS_QUERYING,
                order_parameters=order_parameters_factory(
                    account_type=AccountTypesEnum.NEW_ACCOUNT.value,
                    transfer_type=TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION.value,
                ),
                fulfillment_parameters=fulfillment_parameters_factory(
                    phase=PhasesEnum.CHECK_INVITATION_LINK.value
                ),
            ),
        ]
    )
    pipeline = mocker.MagicMock(spec=Pipeline)
    processor.get_pipeline = mocker.MagicMock(return_value=pipeline)
    processor.process_aws_invitations()
    pipeline.run.assert_not_called()


def test_process_one_order_invitations_accepted(
    mocker,
    config,
    aws_client_factory,
    aws_invitation_processor_factory,
    order_factory,
    order_parameters_factory,
    fulfillment_parameters_factory,
    agreement_factory,
    handshake_data_factory,
    mpa_pool_factory,
):
    order_parameters = order_parameters_factory(
        account_type=AccountTypesEnum.EXISTING_ACCOUNT.value,
        transfer_type=TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION.value,
        account_id="123456789012",
    )
    order = order_factory(
        order_type=ORDER_TYPE_PURCHASE,
        status=MPT_ORDER_STATUS_QUERYING,
        order_parameters=order_parameters,
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_INVITATION_LINK.value
        ),
        agreement=agreement_factory(vendor_id="aws_mpa"),
    )
    aws_client, aws_mock = aws_client_factory(config, "aws_mpa", "aws_role")
    aws_mock.list_handshakes_for_organization.return_value = {
        "Handshakes": [
            handshake_data_factory(
                state=AwsHandshakeStateEnum.ACCEPTED.value,
                account_id="123456789012",
            )
        ]
    }

    def setup_aws(context):
        context.aws_client = aws_client

    mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.SetupContext.setup_aws",
        side_effect=setup_aws,
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.setup_context.get_mpa_account",
        return_value=mpa_pool_factory(),
    )

    mocker.patch(
        "swo_aws_extension.flows.steps.invitation_links.update_order",
        return_value=order,
    )

    mock_switch_order_status_to_process = mocker.patch(
        "swo_aws_extension.flows.jobs.process_aws_invitations.PurchaseContext.switch_order_status_to_process"
    )

    processor = aws_invitation_processor_factory(query_orders=[order])

    processor.process_aws_invitations()
    mock_switch_order_status_to_process.assert_called_once_with(
        mocker.ANY, OrderProcessingTemplateEnum.TRANSFER_WITH_ORG_TICKET_CREATED.value
    )


def response_factory(status_code, response_data):
    response = Response()
    response.status_code = status_code
    response._content = json.dumps(response_data).encode("utf-8")  # noqa: SLF001
    return response


def test_get_quering_orders(mocker, aws_invitation_processor, order_factory):
    mock_client = mocker.MagicMock()
    aws_invitation_processor.client = mock_client

    mock_client.get.side_effect = [
        response_factory(
            status_code=HTTP_STATUS_OK,
            response_data={
                "data": [
                    order_factory(),
                    order_factory(),
                ],
                "$meta": {
                    "pagination": {
                        "total": 4,
                        "limit": 2,
                        "offset": 0,
                    }
                },
            },
        ),
        response_factory(
            status_code=HTTP_STATUS_OK,
            response_data={
                "data": [
                    order_factory(),
                    order_factory(),
                ],
                "$meta": {
                    "pagination": {
                        "total": 4,
                        "limit": 2,
                        "offset": 2,
                    }
                },
            },
        ),
    ]
    orders = aws_invitation_processor.get_querying_orders()
    assert len(orders) == 4


def test_get_quering_orders_exceptions(mocker, aws_invitation_processor, order_factory):
    mock_client = mocker.MagicMock()
    aws_invitation_processor.client = mock_client

    mock_client.get.side_effect = [
        response_factory(
            status_code=HTTP_STATUS_BAD_REQUEST,
            response_data={
                "data": [
                    order_factory(),
                    order_factory(),
                ],
                "$meta": {
                    "pagination": {
                        "total": 4,
                        "limit": 2,
                        "offset": 0,
                    }
                },
            },
        )
    ]
    orders = aws_invitation_processor.get_querying_orders()
    assert len(orders) == 0

    mock_client.get.side_effect = [
        RequestException("Some error"),
    ]
    orders = aws_invitation_processor.get_querying_orders()
    assert len(orders) == 0
