from swo_aws_extension.constants import AccountTypesEnum, PhasesEnum
from swo_aws_extension.flows.order import InitialAWSContext, PurchaseContext


def test_from_order_data(order_factory, agreement_factory):
    order = order_factory()
    order["agreement"] = agreement_factory()
    order["seller"] = {"id": "SEL-123", "name": "Seller"}
    order["buyer"] = {"id": "BUY-123", "name": "Buyer"}

    result = InitialAWSContext.from_order_data(order)

    assert result.agreement is not None
    assert result.seller == {"id": "SEL-123", "name": "Seller"}
    assert result.buyer == {"id": "BUY-123", "name": "Buyer"}
    assert result.order is not None
    assert result.order_authorization is not None


def test_pm_account_id(order_factory):
    order = order_factory(authorization_external_id="123456789012")

    result = InitialAWSContext.from_order_data(order)

    assert result.pm_account_id == "123456789012"


def test_master_payer_account_id(order_factory, agreement_factory):
    order = order_factory()
    order["agreement"] = agreement_factory(vendor_id="987654321098")

    result = InitialAWSContext.from_order_data(order)

    assert result.master_payer_account_id == "987654321098"


def test_order_status(order_factory):
    order = order_factory()
    order["status"] = "Processing"

    result = InitialAWSContext.from_order_data(order)

    assert result.order_status == "Processing"


def test_template(order_factory, template_factory):
    template = template_factory(name="TestTemplate")
    order = order_factory(template=template)

    result = InitialAWSContext.from_order_data(order)

    assert result.template == template


def test_is_type_new_aws_environment(order_factory, order_parameters_factory):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.NEW_AWS_ENVIRONMENT.value
        )
    )

    result = InitialAWSContext.from_order_data(order)

    assert result.is_type_new_aws_environment() is True
    assert result.is_type_existing_aws_environment() is False


def test_is_type_existing_aws_environment(order_factory, order_parameters_factory):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_AWS_ENVIRONMENT.value
        )
    )

    result = InitialAWSContext.from_order_data(order)

    assert result.is_type_existing_aws_environment() is True
    assert result.is_type_new_aws_environment() is False


def test_purchase_context_from_order_data(order_factory):
    order = order_factory()

    result = PurchaseContext.from_order_data(order)

    assert isinstance(result, PurchaseContext)
    assert result.order is not None


def test_phase(order_factory, fulfillment_parameters_factory):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value
        )
    )

    result = PurchaseContext.from_order_data(order)

    assert result.phase == PhasesEnum.CREATE_NEW_AWS_ENVIRONMENT.value


def test_authorization_id(order_factory):
    order = order_factory()

    result = PurchaseContext.from_order_data(order)

    assert result.authorization_id == "AUT-1234-4567"


def test_currency(order_factory):
    order = order_factory()
    order["price"] = {"currency": "USD"}

    result = PurchaseContext.from_order_data(order)

    assert result.currency == "USD"


def test_purchase_context_str(order_factory):
    order = order_factory(order_id="ORD-1234", order_type="purchase")

    result = PurchaseContext.from_order_data(order)

    assert str(result) == "PurchaseContext: ORD-1234 purchase"
