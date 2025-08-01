from swo_aws_extension.airtable.models import MPAStatusEnum
from swo_aws_extension.constants import (
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


def test_validate_new_account_empty_values(
    mocker, order_factory, order_parameters_factory, product_items
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_name="", account_email="", account_type=AccountTypesEnum.NEW_ACCOUNT.value
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.steps.get_product_items_by_skus",
        return_value=product_items,
    )
    client = mocker.MagicMock()
    context = PurchaseContext.from_order_data(order)
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


def test_validate_new_account_with_values(
    mocker, order_factory, order_parameters_factory, product_items
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_name="account_name",
            account_email="test@aws.com",
            account_type=AccountTypesEnum.NEW_ACCOUNT.value,
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.steps.get_product_items_by_skus",
        return_value=product_items,
    )
    client = mocker.MagicMock()
    context = PurchaseContext.from_order_data(order)
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
    mocker, order_factory, order_parameters_factory, product_items
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT.value,
            transfer_type="",
            account_id="",
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.steps.get_product_items_by_skus",
        return_value=product_items,
    )

    client = mocker.MagicMock()
    context = PurchaseContext.from_order_data(order)
    has_errors, result = validate_purchase_order(client, context)

    transfer_type_parameter = {
        "id": "PAR-1234-5680",
        "name": "Transfer Type",
        "externalId": OrderParametersEnum.TRANSFER_TYPE.value,
        "type": "Choice",
        "value": "",
        "error": ERR_TRANSFER_TYPE.to_dict(),
        "constraints": {"hidden": False, "required": True},
    }

    assert transfer_type_parameter in result["parameters"]["ordering"]

    account_id_parameter = {
        "id": "PAR-1234-5681",
        "name": "Account ID",
        "externalId": OrderParametersEnum.ACCOUNT_ID.value,
        "type": "SingleLineText",
        "value": None,
        "constraints": {"hidden": True, "required": False, "readonly": False},
        "error": None,
    }

    assert account_id_parameter in result["parameters"]["ordering"]

    assert not has_errors


def test_validate_selected_transfer_with_org_empty_values(
    mocker, order_factory, order_parameters_factory, product_items
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT.value,
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION.value,
            account_id="",
            master_payer_id="",
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.steps.get_product_items_by_skus",
        return_value=product_items,
    )

    client = mocker.MagicMock()
    context = PurchaseContext.from_order_data(order)
    _, result = validate_purchase_order(client, context)

    transfer_type_parameter = {
        "id": "PAR-1234-5680",
        "name": "Transfer Type",
        "externalId": OrderParametersEnum.TRANSFER_TYPE.value,
        "type": "Choice",
        "value": TransferTypesEnum.TRANSFER_WITH_ORGANIZATION.value,
        "error": None,
    }

    assert transfer_type_parameter in result["parameters"]["ordering"]

    account_id_parameter = {
        "id": "PAR-1234-5681",
        "name": "Account ID",
        "externalId": OrderParametersEnum.ACCOUNT_ID.value,
        "type": "SingleLineText",
        "value": None,
        "constraints": {"hidden": True, "required": False, "readonly": False},
        "error": None,
    }

    assert account_id_parameter in result["parameters"]["ordering"]

    master_payer_id_parameter = {
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "externalId": OrderParametersEnum.MASTER_PAYER_ID.value,
        "type": "SingleLineText",
        "value": "",
        "constraints": {"hidden": False, "readonly": False, "required": True},
        "error": None,
    }
    assert master_payer_id_parameter in result["parameters"]["ordering"]


def test_validate_selected_transfer_with_org_with_values(
    mocker, order_factory, order_parameters_factory, product_items
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT.value,
            transfer_type=TransferTypesEnum.TRANSFER_WITH_ORGANIZATION.value,
            account_id="",
            master_payer_id="123456789012",
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.steps.get_product_items_by_skus",
        return_value=product_items,
    )
    client = mocker.MagicMock()
    context = PurchaseContext.from_order_data(order)
    _, result = validate_purchase_order(client, context)

    transfer_type_parameter = {
        "id": "PAR-1234-5680",
        "name": "Transfer Type",
        "externalId": OrderParametersEnum.TRANSFER_TYPE.value,
        "type": "Choice",
        "value": TransferTypesEnum.TRANSFER_WITH_ORGANIZATION.value,
        "error": None,
    }

    assert transfer_type_parameter in result["parameters"]["ordering"]

    account_id_parameter = {
        "id": "PAR-1234-5681",
        "name": "Account ID",
        "externalId": OrderParametersEnum.ACCOUNT_ID.value,
        "type": "SingleLineText",
        "value": None,
        "constraints": {"hidden": True, "required": False, "readonly": False},
        "error": None,
    }

    assert account_id_parameter in result["parameters"]["ordering"]

    master_payer_id_parameter = {
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "externalId": OrderParametersEnum.MASTER_PAYER_ID.value,
        "type": "SingleLineText",
        "value": "123456789012",
        "error": None,
    }
    assert master_payer_id_parameter in result["parameters"]["ordering"]


def test_validate_selected_transfer_without_org_empty_values(
    mocker, order_factory, order_parameters_factory, product_items
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT.value,
            transfer_type=TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION.value,
            account_id="",
            master_payer_id="",
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.steps.get_product_items_by_skus",
        return_value=product_items,
    )
    client = mocker.MagicMock()
    context = PurchaseContext.from_order_data(order)
    _, result = validate_purchase_order(client, context)

    transfer_type_parameter = {
        "id": "PAR-1234-5680",
        "name": "Transfer Type",
        "externalId": OrderParametersEnum.TRANSFER_TYPE.value,
        "type": "Choice",
        "value": TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION.value,
        "error": None,
    }

    assert transfer_type_parameter in result["parameters"]["ordering"]

    account_id_parameter = {
        "id": "PAR-1234-5681",
        "name": "Account ID",
        "externalId": OrderParametersEnum.ACCOUNT_ID.value,
        "type": "SingleLineText",
        "value": "",
        "constraints": {"hidden": False, "readonly": False, "required": True},
        "error": None,
    }

    assert account_id_parameter in result["parameters"]["ordering"]

    master_payer_id_parameter = {
        "constraints": {"hidden": True, "readonly": False, "required": False},
        "error": None,
        "externalId": OrderParametersEnum.MASTER_PAYER_ID.value,
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "type": "SingleLineText",
        "value": None,
    }
    assert master_payer_id_parameter in result["parameters"]["ordering"]


def test_validate_selected_transfer_without_org_with_values(
    mocker, order_factory, order_parameters_factory, product_items
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT.value,
            transfer_type=TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION.value,
            account_id="123456789012",
            master_payer_id="",
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.steps.get_product_items_by_skus",
        return_value=product_items,
    )

    client = mocker.MagicMock()
    context = PurchaseContext.from_order_data(order)
    _, result = validate_purchase_order(client, context)

    transfer_type_parameter = {
        "id": "PAR-1234-5680",
        "name": "Transfer Type",
        "externalId": OrderParametersEnum.TRANSFER_TYPE.value,
        "type": "Choice",
        "value": TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION.value,
        "error": None,
    }

    assert transfer_type_parameter in result["parameters"]["ordering"]

    account_id_parameter = {
        "id": "PAR-1234-5681",
        "name": "Account ID",
        "externalId": OrderParametersEnum.ACCOUNT_ID.value,
        "type": "SingleLineText",
        "value": "123456789012",
        "constraints": {"hidden": True, "readonly": False, "required": False},
        "error": None,
    }

    assert account_id_parameter in result["parameters"]["ordering"]

    master_payer_id_parameter = {
        "constraints": {"hidden": True, "readonly": False, "required": False},
        "error": None,
        "externalId": OrderParametersEnum.MASTER_PAYER_ID.value,
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "type": "SingleLineText",
        "value": None,
    }
    assert master_payer_id_parameter in result["parameters"]["ordering"]


def test_validate_selected_transfer_without_org_with_invalid_values(
    mocker, order_factory, order_parameters_factory, product_items
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT.value,
            transfer_type=TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION.value,
            account_id="invalid",
            master_payer_id="",
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.steps.get_product_items_by_skus",
        return_value=product_items,
    )

    client = mocker.MagicMock()
    context = PurchaseContext.from_order_data(order)
    _, result = validate_purchase_order(client, context)

    transfer_type_parameter = {
        "id": "PAR-1234-5680",
        "name": "Transfer Type",
        "externalId": OrderParametersEnum.TRANSFER_TYPE.value,
        "type": "Choice",
        "value": TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION.value,
        "error": None,
    }

    assert transfer_type_parameter in result["parameters"]["ordering"]

    account_id_parameter = {
        "id": "PAR-1234-5681",
        "name": "Account ID",
        "externalId": OrderParametersEnum.ACCOUNT_ID.value,
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
        "externalId": OrderParametersEnum.MASTER_PAYER_ID.value,
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "type": "SingleLineText",
        "value": None,
    }
    assert master_payer_id_parameter in result["parameters"]["ordering"]


def test_validate_selected_split_billing_empty_mpa_id(
    mocker, order_factory, order_parameters_factory, product_items
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT.value,
            transfer_type=TransferTypesEnum.SPLIT_BILLING.value,
            master_payer_id="",
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.steps.get_product_items_by_skus",
        return_value=product_items,
    )

    client = mocker.MagicMock()
    context = PurchaseContext.from_order_data(order)
    _, result = validate_purchase_order(client, context)

    master_payer_id_parameter = {
        "constraints": {"hidden": False, "readonly": False, "required": True},
        "error": None,
        "externalId": OrderParametersEnum.MASTER_PAYER_ID.value,
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "type": "SingleLineText",
        "value": "",
    }
    assert master_payer_id_parameter in result["parameters"]["ordering"]


def test_validate_selected_split_billing_mpa_not_found_in_airtable(
    mocker, order_factory, order_parameters_factory, product_items
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT.value,
            transfer_type=TransferTypesEnum.SPLIT_BILLING.value,
            master_payer_id="123456789012",
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.steps.get_product_items_by_skus",
        return_value=product_items,
    )

    mocker.patch(
        "swo_aws_extension.flows.validation.purchase.get_mpa_account",
        return_value=None,
    )

    client = mocker.MagicMock()
    context = PurchaseContext.from_order_data(order)
    _, result = validate_purchase_order(client, context)

    master_payer_id_parameter = {
        "constraints": {"hidden": False, "required": True},
        "error": ERR_SPLIT_BILLING_INVALID_MPA_ID.to_dict(),
        "externalId": OrderParametersEnum.MASTER_PAYER_ID.value,
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "type": "SingleLineText",
        "value": "123456789012",
    }
    assert master_payer_id_parameter in result["parameters"]["ordering"]


def test_validate_selected_split_billing_invalid_client(
    mocker, order_factory, order_parameters_factory, mpa_pool_factory, product_items
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT.value,
            transfer_type=TransferTypesEnum.SPLIT_BILLING.value,
            master_payer_id="123456789012",
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.steps.get_product_items_by_skus",
        return_value=product_items,
    )

    mocker.patch(
        "swo_aws_extension.flows.validation.purchase.get_mpa_account",
        return_value=mpa_pool_factory(),
    )

    client = mocker.MagicMock()
    context = PurchaseContext.from_order_data(order)
    _, result = validate_purchase_order(client, context)

    master_payer_id_parameter = {
        "constraints": {"hidden": False, "required": True},
        "error": ERR_SPLIT_BILLING_INVALID_CLIENT_ID_MPA_ID.to_dict(),
        "externalId": OrderParametersEnum.MASTER_PAYER_ID.value,
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "type": "SingleLineText",
        "value": "123456789012",
    }
    assert master_payer_id_parameter in result["parameters"]["ordering"]


def test_validate_selected_split_billing_invalid_status(
    mocker, order_factory, order_parameters_factory, mpa_pool_factory, product_items
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT.value,
            transfer_type=TransferTypesEnum.SPLIT_BILLING.value,
            master_payer_id="123456789012",
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.steps.get_product_items_by_skus",
        return_value=product_items,
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.purchase.get_mpa_account",
        return_value=mpa_pool_factory(client_id="CLI-1111-1111"),
    )

    client = mocker.MagicMock()
    context = PurchaseContext.from_order_data(order)
    _, result = validate_purchase_order(client, context)

    master_payer_id_parameter = {
        "constraints": {"hidden": False, "required": True},
        "error": ERR_SPLIT_BILLING_INVALID_STATUS_MPA_ID.to_dict(),
        "externalId": OrderParametersEnum.MASTER_PAYER_ID.value,
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "type": "SingleLineText",
        "value": "123456789012",
    }
    assert master_payer_id_parameter in result["parameters"]["ordering"]


def test_validate_selected_split_billing_pls_enabled(
    mocker, order_factory, order_parameters_factory, mpa_pool_factory, product_items
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT.value,
            transfer_type=TransferTypesEnum.SPLIT_BILLING.value,
            master_payer_id="123456789012",
        )
    )

    mocker.patch(
        "swo_aws_extension.flows.validation.steps.get_product_items_by_skus",
        return_value=product_items,
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.purchase.get_mpa_account",
        return_value=mpa_pool_factory(
            client_id="CLI-1111-1111", status=MPAStatusEnum.ASSIGNED.value
        ),
    )

    client = mocker.MagicMock()
    context = PurchaseContext.from_order_data(order)
    _, result = validate_purchase_order(client, context)

    master_payer_id_parameter = {
        "error": None,
        "externalId": OrderParametersEnum.MASTER_PAYER_ID.value,
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
        "value": SupportTypesEnum.PARTNER_LED_SUPPORT.value,
    }
    assert support_type_parameter in result["parameters"]["ordering"]


def test_validate_no_items(mocker, order_factory, order_parameters_factory, mpa_pool_factory):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_ACCOUNT.value,
            transfer_type=TransferTypesEnum.SPLIT_BILLING.value,
            master_payer_id="123456789012",
        )
    )

    mocker.patch(
        "swo_aws_extension.flows.validation.steps.get_product_items_by_skus",
        return_value=[],
    )
    mocker.patch(
        "swo_aws_extension.flows.validation.purchase.get_mpa_account",
        return_value=mpa_pool_factory(
            client_id="CLI-1111-1111", status=MPAStatusEnum.ASSIGNED.value
        ),
    )

    client = mocker.MagicMock()
    context = PurchaseContext.from_order_data(order)
    _, result = validate_purchase_order(client, context)

    master_payer_id_parameter = {
        "error": None,
        "externalId": OrderParametersEnum.MASTER_PAYER_ID.value,
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "type": "SingleLineText",
        "value": "123456789012",
    }
    assert master_payer_id_parameter in result["parameters"]["ordering"]

    support_type_parameter = {
        "constraints": {"hidden": False, "required": False, "readonly": True},
        "error": None,
        "externalId": OrderParametersEnum.SUPPORT_TYPE.value,
        "id": "PAR-1234-5679",
        "name": "Support Type",
        "type": "Choice",
        "value": SupportTypesEnum.PARTNER_LED_SUPPORT.value,
    }
    assert support_type_parameter in result["parameters"]["ordering"]
