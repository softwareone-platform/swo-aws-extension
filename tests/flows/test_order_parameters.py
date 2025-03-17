from swo_aws_extension.flows.order import OrderContext
from swo_aws_extension.parameters import OrderingParameters


def test_parameter(order):
    initial_order = order
    context = OrderContext(order=order)
    p = context.parameters.ordering.get_by_external_id(OrderingParameters.MPA_ACCOUNT_ID)
    assert p.value == "123-456-789"
    new_param = p.update_value("123")
    assert new_param.value == "123"
    new_order = new_param.order
    assert initial_order != new_order
    new_param = new_param.update_value("123-456-789")
    new_order = new_param.order
    assert initial_order == new_order

    value = context.parameters.ordering.get_by_external_id(OrderingParameters.MPA_ACCOUNT_ID).value
    assert value == "123-456-789"
    assert (
            context.parameters.ordering
            .get_by_external_id(OrderingParameters.PARAM_ACCOUNT_EMAIL).value
            == "test@aws.com"
    )
