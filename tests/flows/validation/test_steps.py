from mpt_extension_sdk.flows.context import ORDER_TYPE_CHANGE

from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.validation.steps import (
    InitializeItemStep,
)


def test_initialize_item_step(mocker, mpt_client, aws_client_factory, order_factory, items_factory):
    order = order_factory(order_type=ORDER_TYPE_CHANGE)
    items = items_factory()
    get_product_items_by_skus = mocker.patch(
        "swo_aws_extension.flows.validation.steps.get_product_items_by_skus",
        return_value=items,
    )

    context = InitialAWSContext.from_order_data(order)
    next = mocker.MagicMock()

    step = InitializeItemStep()
    step(mpt_client, context, next)

    next.assert_called_once()
    get_product_items_by_skus.assert_called_once()

    order_lines = [
        {
            "item": {
                "externalIds": {"vendor": "65304578CA"},
                "id": "ITM-1234-1234-1234-0001",
                "name": "Awesome product",
            },
            "quantity": 1,
        }
    ]
    assert context.order["lines"] == order_lines
