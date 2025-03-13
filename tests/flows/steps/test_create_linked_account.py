from swo.mpt.client import MPTClient

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.error import (
    ERR_ACCOUNT_NAME_EMPTY,
    ERR_EMAIL_ALREADY_EXIST,
    ERR_EMAIL_EMPTY,
)
from swo_aws_extension.flows.order import OrderContext
from swo_aws_extension.flows.steps.create_linked_account import CreateLinkedAccount
from swo_aws_extension.parameters import set_account_request_id, set_phase


def test_create_linked_account_phase_create_linked_account(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    create_account_status,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_ACCOUNT
        )
    )

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, mock_client = aws_client_factory(
        config, "test_account_id", "test_role_name"
    )
    mock_client.create_account.return_value = create_account_status()

    context = OrderContext.from_order(order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()

    mocked_update_order = mocker.patch(
        "swo_aws_extension.flows.steps.create_linked_account.update_order",
    )

    create_linked_account = CreateLinkedAccount()

    create_linked_account(mpt_client_mock, context, next_step_mock)

    mock_client.create_account.assert_called_once_with(
        AccountName="account_name",
        Email="test@aws.com",
        IamUserAccessToBilling="DENY",
        RoleName="OrganizationAccountAccessRole",
    )

    assert (
        context.order["parameters"]["ordering"]
        == set_phase(order, PhasesEnum.CREATE_ACCOUNT)["parameters"]["ordering"]
    )
    assert (
        context.order["parameters"]["fulfillment"]
        == set_account_request_id(order, "account_request_id")["parameters"][
            "fulfillment"
        ]
    )
    mocked_update_order.assert_called_once_with(
        mpt_client_mock,
        context.order["id"],
        parameters=context.order["parameters"],
    )


def test_create_linked_account_phase_check_linked_account_in_progress(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    account_creation_status_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_ACCOUNT, account_request_id="account_request_id"
        )
    )

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")

    context = OrderContext.from_order(order)
    context.aws_client = aws_client
    context.account_creation_status = account_creation_status_factory(
        status="IN_PROGRESS"
    )
    next_step_mock = mocker.Mock()

    create_linked_account = CreateLinkedAccount()
    create_linked_account(mpt_client_mock, context, next_step_mock)

    assert (
        context.order["parameters"]
        == set_phase(order, PhasesEnum.CREATE_ACCOUNT)["parameters"]
    )


def test_create_linked_account_phase_check_linked_account_succeed(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    account_creation_status_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_ACCOUNT, account_request_id="account_request_id"
        )
    )

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")

    context = OrderContext.from_order(order)
    context.aws_client = aws_client
    context.account_creation_status = account_creation_status_factory(
        status="SUCCEEDED"
    )
    next_step_mock = mocker.Mock()

    mocked_update_order = mocker.patch(
        "swo_aws_extension.flows.steps.create_linked_account.update_order",
    )

    create_linked_account = CreateLinkedAccount()

    create_linked_account(mpt_client_mock, context, next_step_mock)

    assert (
        context.order["parameters"]
        == set_phase(order, PhasesEnum.CREATE_SUBSCRIPTIONS)["parameters"]
    )
    mocked_update_order.assert_called_once_with(
        mpt_client_mock,
        context.order["id"],
        parameters=context.order["parameters"],
    )
    next_step_mock.assert_called_once_with(mpt_client_mock, context)


def test_create_linked_account_phase_check_linked_account_email_already_exist(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    account_creation_status_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_ACCOUNT
        )
    )

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")

    context = OrderContext.from_order(order)
    context.aws_client = aws_client
    context.account_creation_status = account_creation_status_factory(
        status="FAILED", failure_reason="EMAIL_ALREADY_EXISTS"
    )
    next_step_mock = mocker.Mock()

    mocked_get_product_template_or_default = mocker.patch(
        "swo_aws_extension.flows.order.get_product_template_or_default",
        return_value={"id": "TPL-964-112"},
    )
    mocked_query_order = mocker.patch("swo_aws_extension.flows.order.query_order")

    create_linked_account = CreateLinkedAccount()

    create_linked_account(mpt_client_mock, context, next_step_mock)

    mocked_get_product_template_or_default.assert_called_once_with(
        mpt_client_mock,
        "PRD-1111-1111",
        "Querying",
        name=None,
    )
    mocked_query_order.assert_called_once_with(
        mpt_client_mock,
        context.order_id,
        parameters=context.order["parameters"],
        template={"id": "TPL-964-112"},
    )
    assert (
        context.order["parameters"]["ordering"][0]["error"]
        == ERR_EMAIL_ALREADY_EXIST.to_dict()
    )


def test_create_linked_account_phase_check_linked_account_failed(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    account_creation_status_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_ACCOUNT
        )
    )

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")

    context = OrderContext.from_order(order)
    context.aws_client = aws_client
    context.account_creation_status = account_creation_status_factory(
        status="FAILED", failure_reason="ACCOUNT_LIMIT_EXCEEDED"
    )
    next_step_mock = mocker.Mock()

    create_linked_account = CreateLinkedAccount()

    create_linked_account(mpt_client_mock, context, next_step_mock)

    next_step_mock.assert_not_called()


def test_create_linked_account_phase_empty_parameters(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_ACCOUNT
        ),
        order_parameters=order_parameters_factory(account_name="", account_email=""),
    )

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")
    context = OrderContext.from_order(order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()
    mocked_get_product_template_or_default = mocker.patch(
        "swo_aws_extension.flows.order.get_product_template_or_default",
        return_value={"id": "TPL-964-112"},
    )
    mocked_query_order = mocker.patch("swo_aws_extension.flows.order.query_order")
    create_linked_account = CreateLinkedAccount()

    create_linked_account(mpt_client_mock, context, next_step_mock)

    next_step_mock.assert_not_called()
    mocked_get_product_template_or_default.assert_called_once_with(
        mpt_client_mock,
        "PRD-1111-1111",
        "Querying",
        name=None,
    )
    mocked_query_order.assert_called_once_with(
        mpt_client_mock,
        context.order["id"],
        parameters=context.order["parameters"],
        template={"id": "TPL-964-112"},
    )
    assert (
        context.order["parameters"]["ordering"][0]["error"] == ERR_EMAIL_EMPTY.to_dict()
    )
    assert (
        context.order["parameters"]["ordering"][1]["error"]
        == ERR_ACCOUNT_NAME_EMPTY.to_dict()
    )


def test_create_linked_account_invalid_phase(
    mocker,
    order_factory,
    config,
    aws_client_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_SUBSCRIPTIONS
        )
    )

    mpt_client_mock = mocker.Mock(spec=MPTClient)
    aws_client, _ = aws_client_factory(config, "test_account_id", "test_role_name")
    context = OrderContext.from_order(order)
    context.aws_client = aws_client
    next_step_mock = mocker.Mock()
    create_linked_account = CreateLinkedAccount()

    create_linked_account(mpt_client_mock, context, next_step_mock)

    next_step_mock.assert_called_once_with(mpt_client_mock, context)
