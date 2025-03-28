import pytest

from swo_aws_extension.aws.errors import AWSHttpError
from swo_aws_extension.flows.error import strip_trace_id
from swo_aws_extension.flows.fulfillment import fulfill_order
from swo_aws_extension.flows.fulfillment.base import setup_contexts
from swo_aws_extension.flows.order import InitialAWSContext


def test_fulfill_order_exception(mocker, mpt_error_factory, order_factory):
    error_data = mpt_error_factory(500, "Internal Server Error", "Oops!")
    error = AWSHttpError(500, error_data)
    mocked_notify = mocker.patch(
        "swo_aws_extension.flows.fulfillment.base.notify_unhandled_exception_in_teams"
    )
    mocker.patch(
        "swo_aws_extension.flows.fulfillment.base.purchase.run",
        side_effect=error,
    )

    new_order = order_factory(order_id="ORD-FFFF")
    context = InitialAWSContext(order=new_order)
    with pytest.raises(AWSHttpError):
        fulfill_order(mocker.MagicMock(), context)

    process, order_id, tb = mocked_notify.mock_calls[0].args
    assert process == "fulfillment"
    assert order_id == new_order["id"]
    assert strip_trace_id(str(error)) in tb


def test_setup_contexts(mpt_client, order_factory):
    orders = [order_factory()]
    contexts = setup_contexts(mpt_client, orders)
    assert len(contexts) == 1
    assert contexts[0].order == orders[0]


def test_setup_contexts_without_mpa_account_id(
    mocker,
    mpt_client,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    mpa_pool,
    buyer,
):
    order_without_mpa = order_factory(
        order_id="ORD-1",
        fulfillment_parameters=fulfillment_parameters_factory(mpa_account_id=""),
    )

    orders = [order_without_mpa]
    mocked_master_payer_account_pool_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_master_payer_account_pool_model",
        return_value=mocked_master_payer_account_pool_model,
    )
    mocked_master_payer_account_pool_model.all.return_value = [mpa_pool]

    contexts = setup_contexts(mpt_client, orders)
    assert len(contexts) == 1
    assert contexts[0] == InitialAWSContext(order=order_without_mpa, airtable_mpa=mpa_pool)
    assert contexts[0].airtable_mpa == mpa_pool

    mocked_master_payer_account_pool_model.all.assert_called_once()


def test_setup_contexts_without_mpa_account_id_empty_pool(
    mocker,
    mpt_client,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    buyer,
):
    order_without_mpa = order_factory(
        order_id="ORD-1",
        fulfillment_parameters=fulfillment_parameters_factory(mpa_account_id=""),
    )

    orders = [order_without_mpa]
    mocked_master_payer_account_pool_model = mocker.MagicMock()
    mocker.patch(
        "swo_aws_extension.airtable.models.get_master_payer_account_pool_model",
        return_value=mocked_master_payer_account_pool_model,
    )
    mocked_master_payer_account_pool_model.all.return_value = []

    contexts = setup_contexts(mpt_client, orders)
    assert len(contexts) == 1
    assert contexts[0].order == order_without_mpa
    assert contexts[0].airtable_mpa is None

    mocked_master_payer_account_pool_model.all.assert_called_once()
