from swo_aws_extension.airtable.models import MPAStatusEnum
from swo_aws_extension.constants import (
    AWS_ITEM_SKU,
    AccountTypesEnum,
    SupportTypesEnum,
    TransferTypesEnum,
)
from swo_aws_extension.flows.error import (
    ERR_SPLIT_BILLING_INVALID_CLIENT_ID_MPA_ID,
    ERR_SPLIT_BILLING_INVALID_MPA_ID,
    ERR_SPLIT_BILLING_INVALID_STATUS_MPA_ID,
    ERR_TRANSFER_TYPE,
)
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.validation.purchase import validate_purchase_order
from swo_aws_extension.parameters import OrderParametersEnum


def test_validate_new_account_empty_values(mocker, order_factory, order_parameters_factory):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_name="", account_email="", account_type=AccountTypesEnum.NEW_ACCOUNT
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.purchase.get_product_items_by_skus",
        return_value=[{"id": "ITEM-123-456", "sku": AWS_ITEM_SKU}],
    )
    client = mocker.MagicMock()
    context = PurchaseContext(order=order)
    has_errors, result = validate_purchase_order(client, context)

    assert result["parameters"]["ordering"][0]["constraints"] == {
        "hidden": False,
        "readonly": False,
        "required": True,
    }
    assert result["parameters"]["ordering"][1]["constraints"] == {
        "hidden": False,
        "readonly": False,
        "required": True,
    }
    assert not has_errors


def test_validate_new_account_with_values(mocker, order_factory, order_parameters_factory):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_name="account_name",
            account_email="test@aws.com",
            account_type=AccountTypesEnum.NEW_ACCOUNT,
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.purchase.get_product_items_by_skus",
        return_value=[{"id": "ITEM-123-456", "sku": AWS_ITEM_SKU}],
    )
    client = mocker.MagicMock()
    context = PurchaseContext(order=order)
    has_errors, result = validate_purchase_order(client, context)

    assert result["parameters"]["ordering"][0]["constraints"] == {
        "hidden": True,
        "readonly": False,
        "required": False,
    }
    assert result["parameters"]["ordering"][1]["constraints"] == {
        "hidden": True,
        "readonly": False,
        "required": False,
    }
    assert not has_errors


def test_validate_selected_existing_account_empty_values(
    mocker, order_factory, order_parameters_factory
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT,
            transfer_type="",
            account_id="",
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.purchase.get_product_items_by_skus",
        return_value=[{"id": "ITEM-123-456", "sku": AWS_ITEM_SKU}],
    )

    client = mocker.MagicMock()
    context = PurchaseContext(order=order)
    has_errors, result = validate_purchase_order(client, context)

    transfer_type_parameter = {
        "id": "PAR-1234-5680",
        "name": "Transfer Type",
        "externalId": OrderParametersEnum.TRANSFER_TYPE,
        "type": "Choice",
        "value": "",
        "error": ERR_TRANSFER_TYPE.to_dict(),
        "constraints": {"hidden": False, "required": True},
    }

    assert transfer_type_parameter in result["parameters"]["ordering"]

    account_id_parameter = {
        "id": "PAR-1234-5681",
        "name": "Account ID",
        "externalId": OrderParametersEnum.ACCOUNT_ID,
        "type": "SingleLineText",
        "value": None,
        "constraints": {"hidden": True, "required": False, "readonly": False},
        "error": None,
    }

    assert account_id_parameter in result["parameters"]["ordering"]

    assert not has_errors


def test_validate_selected_transfer_with_org_empty_values(
    mocker, order_factory, order_parameters_factory
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT,
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
            account_id="",
            master_payer_id="",
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.purchase.get_product_items_by_skus",
        return_value=[{"id": "ITEM-123-456", "sku": AWS_ITEM_SKU}],
    )

    client = mocker.MagicMock()
    context = PurchaseContext(order=order)
    _, result = validate_purchase_order(client, context)

    transfer_type_parameter = {
        "id": "PAR-1234-5680",
        "name": "Transfer Type",
        "externalId": OrderParametersEnum.TRANSFER_TYPE,
        "type": "Choice",
        "value": TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
        "error": None,
    }

    assert transfer_type_parameter in result["parameters"]["ordering"]

    account_id_parameter = {
        "id": "PAR-1234-5681",
        "name": "Account ID",
        "externalId": OrderParametersEnum.ACCOUNT_ID,
        "type": "SingleLineText",
        "value": None,
        "constraints": {"hidden": True, "required": False, "readonly": False},
        "error": None,
    }

    assert account_id_parameter in result["parameters"]["ordering"]

    master_payer_id_parameter = {
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "externalId": OrderParametersEnum.MASTER_PAYER_ID,
        "type": "SingleLineText",
        "value": "",
        "constraints": {"hidden": False, "readonly": False, "required": True},
        "error": None,
    }
    assert master_payer_id_parameter in result["parameters"]["ordering"]


def test_validate_selected_transfer_with_org_with_values(
    mocker, order_factory, order_parameters_factory
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT,
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
            account_id="",
            master_payer_id="123456789012",
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.purchase.get_product_items_by_skus",
        return_value=[{"id": "ITEM-123-456", "sku": AWS_ITEM_SKU}],
    )
    client = mocker.MagicMock()
    context = PurchaseContext(order=order)
    _, result = validate_purchase_order(client, context)

    transfer_type_parameter = {
        "id": "PAR-1234-5680",
        "name": "Transfer Type",
        "externalId": OrderParametersEnum.TRANSFER_TYPE,
        "type": "Choice",
        "value": TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
        "error": None,
    }

    assert transfer_type_parameter in result["parameters"]["ordering"]

    account_id_parameter = {
        "id": "PAR-1234-5681",
        "name": "Account ID",
        "externalId": OrderParametersEnum.ACCOUNT_ID,
        "type": "SingleLineText",
        "value": None,
        "constraints": {"hidden": True, "required": False, "readonly": False},
        "error": None,
    }

    assert account_id_parameter in result["parameters"]["ordering"]

    master_payer_id_parameter = {
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "externalId": OrderParametersEnum.MASTER_PAYER_ID,
        "type": "SingleLineText",
        "value": "123456789012",
        "error": None,
    }
    assert master_payer_id_parameter in result["parameters"]["ordering"]


def test_validate_selected_transfer_without_org_empty_values(
    mocker, order_factory, order_parameters_factory
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT,
            transfer_type=TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION,
            account_id="",
            master_payer_id="",
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.purchase.get_product_items_by_skus",
        return_value=[{"id": "ITEM-123-456", "sku": AWS_ITEM_SKU}],
    )
    client = mocker.MagicMock()
    context = PurchaseContext(order=order)
    _, result = validate_purchase_order(client, context)

    transfer_type_parameter = {
        "id": "PAR-1234-5680",
        "name": "Transfer Type",
        "externalId": OrderParametersEnum.TRANSFER_TYPE,
        "type": "Choice",
        "value": TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION,
        "error": None,
    }

    assert transfer_type_parameter in result["parameters"]["ordering"]

    account_id_parameter = {
        "id": "PAR-1234-5681",
        "name": "Account ID",
        "externalId": OrderParametersEnum.ACCOUNT_ID,
        "type": "SingleLineText",
        "value": "",
        "constraints": {"hidden": False, "readonly": False, "required": True},
        "error": None,
    }

    assert account_id_parameter in result["parameters"]["ordering"]

    master_payer_id_parameter = {
        "constraints": {"hidden": True, "readonly": False, "required": False},
        "error": None,
        "externalId": OrderParametersEnum.MASTER_PAYER_ID,
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "type": "SingleLineText",
        "value": None,
    }
    assert master_payer_id_parameter in result["parameters"]["ordering"]


def test_validate_selected_transfer_without_org_with_values(
    mocker, order_factory, order_parameters_factory
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT,
            transfer_type=TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION,
            account_id="123456789012",
            master_payer_id="",
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.purchase.get_product_items_by_skus",
        return_value=[{"id": "ITEM-123-456", "sku": AWS_ITEM_SKU}],
    )

    client = mocker.MagicMock()
    context = PurchaseContext(order=order)
    _, result = validate_purchase_order(client, context)

    transfer_type_parameter = {
        "id": "PAR-1234-5680",
        "name": "Transfer Type",
        "externalId": OrderParametersEnum.TRANSFER_TYPE,
        "type": "Choice",
        "value": TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION,
        "error": None,
    }

    assert transfer_type_parameter in result["parameters"]["ordering"]

    account_id_parameter = {
        "id": "PAR-1234-5681",
        "name": "Account ID",
        "externalId": OrderParametersEnum.ACCOUNT_ID,
        "type": "SingleLineText",
        "value": "123456789012",
        "constraints": {"hidden": True, "readonly": False, "required": False},
        "error": None,
    }

    assert account_id_parameter in result["parameters"]["ordering"]

    master_payer_id_parameter = {
        "constraints": {"hidden": True, "readonly": False, "required": False},
        "error": None,
        "externalId": OrderParametersEnum.MASTER_PAYER_ID,
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "type": "SingleLineText",
        "value": None,
    }
    assert master_payer_id_parameter in result["parameters"]["ordering"]


def test_validate_selected_transfer_without_org_with_invalid_values(
    mocker, order_factory, order_parameters_factory
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT,
            transfer_type=TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION,
            account_id="invalid",
            master_payer_id="",
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.purchase.get_product_items_by_skus",
        return_value=[{"id": "ITEM-123-456", "sku": AWS_ITEM_SKU}],
    )

    client = mocker.MagicMock()
    context = PurchaseContext(order=order)
    _, result = validate_purchase_order(client, context)

    transfer_type_parameter = {
        "id": "PAR-1234-5680",
        "name": "Transfer Type",
        "externalId": OrderParametersEnum.TRANSFER_TYPE,
        "type": "Choice",
        "value": TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION,
        "error": None,
    }

    assert transfer_type_parameter in result["parameters"]["ordering"]

    account_id_parameter = {
        "id": "PAR-1234-5681",
        "name": "Account ID",
        "externalId": OrderParametersEnum.ACCOUNT_ID,
        "type": "SingleLineText",
        "value": "invalid",
        "constraints": {"hidden": False, "required": True},
        "error": {
            "id": "AWS008",
            "message": "Invalid list of accounts ids. Introduce the 12 digits "
            "account numbers separated by new line.",
        },
    }

    assert account_id_parameter in result["parameters"]["ordering"]

    master_payer_id_parameter = {
        "constraints": {"hidden": True, "readonly": False, "required": False},
        "error": None,
        "externalId": OrderParametersEnum.MASTER_PAYER_ID,
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "type": "SingleLineText",
        "value": None,
    }
    assert master_payer_id_parameter in result["parameters"]["ordering"]


def test_validate_selected_split_billing_empty_mpa_id(
    mocker, order_factory, order_parameters_factory
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT,
            transfer_type=TransferTypesEnum.SPLIT_BILLING,
            master_payer_id="",
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.purchase.get_product_items_by_skus",
        return_value=[{"id": "ITEM-123-456", "sku": AWS_ITEM_SKU}],
    )

    client = mocker.MagicMock()
    context = PurchaseContext(order=order)
    _, result = validate_purchase_order(client, context)

    master_payer_id_parameter = {
        "constraints": {"hidden": False, "readonly": False, "required": True},
        "error": None,
        "externalId": OrderParametersEnum.MASTER_PAYER_ID,
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "type": "SingleLineText",
        "value": "",
    }
    assert master_payer_id_parameter in result["parameters"]["ordering"]


def test_validate_selected_split_billing_mpa_not_found_in_airtable(
    mocker, order_factory, order_parameters_factory
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT,
            transfer_type=TransferTypesEnum.SPLIT_BILLING,
            master_payer_id="123456789012",
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.purchase.get_product_items_by_skus",
        return_value=[{"id": "ITEM-123-456", "sku": AWS_ITEM_SKU}],
    )

    mocker.patch(
        "swo_aws_extension.flows.validation.purchase.get_mpa_account",
        return_value=None,
    )

    client = mocker.MagicMock()
    context = PurchaseContext(order=order)
    _, result = validate_purchase_order(client, context)

    master_payer_id_parameter = {
        "constraints": {"hidden": False, "required": True},
        "error": ERR_SPLIT_BILLING_INVALID_MPA_ID.to_dict(),
        "externalId": OrderParametersEnum.MASTER_PAYER_ID,
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "type": "SingleLineText",
        "value": "123456789012",
    }
    assert master_payer_id_parameter in result["parameters"]["ordering"]


def test_validate_selected_split_billing_invalid_client(
    mocker, order_factory, order_parameters_factory, mpa_pool
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT,
            transfer_type=TransferTypesEnum.SPLIT_BILLING,
            master_payer_id="123456789012",
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.purchase.get_product_items_by_skus",
        return_value=[{"id": "ITEM-123-456", "sku": AWS_ITEM_SKU}],
    )

    mocker.patch(
        "swo_aws_extension.flows.validation.purchase.get_mpa_account",
        return_value=mpa_pool,
    )

    client = mocker.MagicMock()
    context = PurchaseContext(order=order)
    _, result = validate_purchase_order(client, context)

    master_payer_id_parameter = {
        "constraints": {"hidden": False, "required": True},
        "error": ERR_SPLIT_BILLING_INVALID_CLIENT_ID_MPA_ID.to_dict(),
        "externalId": OrderParametersEnum.MASTER_PAYER_ID,
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "type": "SingleLineText",
        "value": "123456789012",
    }
    assert master_payer_id_parameter in result["parameters"]["ordering"]


def test_validate_selected_split_billing_invalid_status(
    mocker, order_factory, order_parameters_factory, mpa_pool
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT,
            transfer_type=TransferTypesEnum.SPLIT_BILLING,
            master_payer_id="123456789012",
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.purchase.get_product_items_by_skus",
        return_value=[{"id": "ITEM-123-456", "sku": AWS_ITEM_SKU}],
    )
    mpa_pool.client_id = "CLI-1111-1111"
    mocker.patch(
        "swo_aws_extension.flows.validation.purchase.get_mpa_account",
        return_value=mpa_pool,
    )

    client = mocker.MagicMock()
    context = PurchaseContext(order=order)
    _, result = validate_purchase_order(client, context)

    master_payer_id_parameter = {
        "constraints": {"hidden": False, "required": True},
        "error": ERR_SPLIT_BILLING_INVALID_STATUS_MPA_ID.to_dict(),
        "externalId": OrderParametersEnum.MASTER_PAYER_ID,
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "type": "SingleLineText",
        "value": "123456789012",
    }
    assert master_payer_id_parameter in result["parameters"]["ordering"]


def test_validate_selected_split_billing_pls_enabled(
    mocker, order_factory, order_parameters_factory, mpa_pool
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT,
            transfer_type=TransferTypesEnum.SPLIT_BILLING,
            master_payer_id="123456789012",
        )
    )

    mocker.patch(
        "swo_aws_extension.flows.validation.purchase.get_product_items_by_skus",
        return_value=[{"id": "ITEM-123-456", "sku": AWS_ITEM_SKU}],
    )
    mpa_pool.client_id = "CLI-1111-1111"
    mpa_pool.status = MPAStatusEnum.ASSIGNED
    mocker.patch(
        "swo_aws_extension.flows.validation.purchase.get_mpa_account",
        return_value=mpa_pool,
    )

    client = mocker.MagicMock()
    context = PurchaseContext(order=order)
    _, result = validate_purchase_order(client, context)

    master_payer_id_parameter = {
        "error": None,
        "externalId": OrderParametersEnum.MASTER_PAYER_ID,
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "type": "SingleLineText",
        "value": "123456789012",
    }
    assert master_payer_id_parameter in result["parameters"]["ordering"]

    support_type_parameter = {
        "constraints": {"hidden": False, "readonly": True, "required": False},
        "error": None,
        "externalId": OrderParametersEnum.SUPPORT_TYPE,
        "id": "PAR-1234-5679",
        "name": "Support Type",
        "type": "Choice",
        "value": SupportTypesEnum.PARTNER_LED_SUPPORT,
    }
    assert support_type_parameter in result["parameters"]["ordering"]


def test_validate_no_items(mocker, order_factory, order_parameters_factory, mpa_pool):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT,
            transfer_type=TransferTypesEnum.SPLIT_BILLING,
            master_payer_id="123456789012",
        )
    )

    mocker.patch(
        "swo_aws_extension.flows.validation.purchase.get_product_items_by_skus",
        return_value=[],
    )
    mpa_pool.client_id = "CLI-1111-1111"
    mpa_pool.status = MPAStatusEnum.ASSIGNED
    mocker.patch(
        "swo_aws_extension.flows.validation.purchase.get_mpa_account",
        return_value=mpa_pool,
    )

    client = mocker.MagicMock()
    context = PurchaseContext(order=order)
    _, result = validate_purchase_order(client, context)

    master_payer_id_parameter = {
        "error": None,
        "externalId": OrderParametersEnum.MASTER_PAYER_ID,
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "type": "SingleLineText",
        "value": "123456789012",
    }
    assert master_payer_id_parameter in result["parameters"]["ordering"]

    support_type_parameter = {
        "constraints": {"hidden": False, "required": False, "readonly": True},
        "error": None,
        "externalId": OrderParametersEnum.SUPPORT_TYPE,
        "id": "PAR-1234-5679",
        "name": "Support Type",
        "type": "Choice",
        "value": SupportTypesEnum.PARTNER_LED_SUPPORT,
    }
    assert support_type_parameter in result["parameters"]["ordering"]
