from swo_aws_extension.constants import AccountTypesEnum, TransferTypesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.validation.purchase import validate_purchase_order
from swo_aws_extension.parameters import OrderParametersEnum


def test_validate_new_account_empty_values(mocker, order_factory, order_parameters_factory):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_name="", account_email="", account_type=AccountTypesEnum.NEW_ACCOUNT
        )
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

    client = mocker.MagicMock()
    context = PurchaseContext(order=order)
    has_errors, result = validate_purchase_order(client, context)

    transfer_type_parameter = {
        "id": "PAR-1234-5680",
        "name": "Transfer Type",
        "externalId": OrderParametersEnum.TRANSFER_TYPE,
        "type": "Choice",
        "value": "",
        "error": None,
        "constraints": {"hidden": False, "required": True, "readonly": False},
    }

    assert transfer_type_parameter in result["parameters"]["ordering"]

    account_id_parameter = {
        "id": "PAR-1234-5681",
        "name": "Account ID",
        "externalId": OrderParametersEnum.ACCOUNT_ID,
        "type": "SingleLineText",
        "value": "",
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

    client = mocker.MagicMock()
    context = PurchaseContext(order=order)
    has_errors, result = validate_purchase_order(client, context)

    transfer_type_parameter = {
        "id": "PAR-1234-5680",
        "name": "Transfer Type",
        "externalId": OrderParametersEnum.TRANSFER_TYPE,
        "type": "Choice",
        "value": TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
        "error": None,
        "constraints": {"hidden": False, "required": True, "readonly": True},
    }

    assert transfer_type_parameter in result["parameters"]["ordering"]

    account_id_parameter = {
        "id": "PAR-1234-5681",
        "name": "Account ID",
        "externalId": OrderParametersEnum.ACCOUNT_ID,
        "type": "SingleLineText",
        "value": "",
        "constraints": {"hidden": True, "required": False, "readonly": False},
        "error": None,
    }

    assert account_id_parameter in result["parameters"]["ordering"]

    master_payer_id_parameter = {
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "externalId": OrderParametersEnum.MASTER_PAYER_ID,
        "type": "Choice",
        "value": "",
        "error": {"id": "AWS006", "message": "Account id is empty. Please provide an account id."},
        "constraints": {"hidden": False, "required": True},
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

    client = mocker.MagicMock()
    context = PurchaseContext(order=order)
    has_errors, result = validate_purchase_order(client, context)

    transfer_type_parameter = {
        "id": "PAR-1234-5680",
        "name": "Transfer Type",
        "externalId": OrderParametersEnum.TRANSFER_TYPE,
        "type": "Choice",
        "value": TransferTypesEnum.TRANSFER_WITH_ORGANIZATION,
        "error": None,
        "constraints": {"hidden": False, "required": True, "readonly": True},
    }

    assert transfer_type_parameter in result["parameters"]["ordering"]

    account_id_parameter = {
        "id": "PAR-1234-5681",
        "name": "Account ID",
        "externalId": OrderParametersEnum.ACCOUNT_ID,
        "type": "SingleLineText",
        "value": "",
        "constraints": {"hidden": True, "required": False, "readonly": False},
        "error": None,
    }

    assert account_id_parameter in result["parameters"]["ordering"]

    master_payer_id_parameter = {
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "externalId": OrderParametersEnum.MASTER_PAYER_ID,
        "type": "Choice",
        "value": "123456789012",
        "error": None,
        "constraints": {"hidden": False, "readonly": False, "required": True},
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

    client = mocker.MagicMock()
    context = PurchaseContext(order=order)
    has_errors, result = validate_purchase_order(client, context)

    transfer_type_parameter = {
        "id": "PAR-1234-5680",
        "name": "Transfer Type",
        "externalId": OrderParametersEnum.TRANSFER_TYPE,
        "type": "Choice",
        "value": TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION,
        "error": None,
        "constraints": {"hidden": False, "required": True, "readonly": True},
    }

    assert transfer_type_parameter in result["parameters"]["ordering"]

    account_id_parameter = {
        "id": "PAR-1234-5681",
        "name": "Account ID",
        "externalId": OrderParametersEnum.ACCOUNT_ID,
        "type": "SingleLineText",
        "value": "",
        "constraints": {"hidden": False, "required": True},
        "error": {"id": "AWS007", "message": "Account id is empty. Please provide an account id."},
    }

    assert account_id_parameter in result["parameters"]["ordering"]

    master_payer_id_parameter = {
        "constraints": {"hidden": True, "readonly": False, "required": False},
        "error": None,
        "externalId": OrderParametersEnum.MASTER_PAYER_ID,
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "type": "Choice",
        "value": "",
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

    client = mocker.MagicMock()
    context = PurchaseContext(order=order)
    has_errors, result = validate_purchase_order(client, context)

    transfer_type_parameter = {
        "id": "PAR-1234-5680",
        "name": "Transfer Type",
        "externalId": OrderParametersEnum.TRANSFER_TYPE,
        "type": "Choice",
        "value": TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION,
        "error": None,
        "constraints": {"hidden": False, "required": True, "readonly": True},
    }

    assert transfer_type_parameter in result["parameters"]["ordering"]

    account_id_parameter = {
        "id": "PAR-1234-5681",
        "name": "Account ID",
        "externalId": OrderParametersEnum.ACCOUNT_ID,
        "type": "SingleLineText",
        "value": "123456789012",
        "constraints": {"hidden": False, "required": True, "readonly": False},
        "error": None,
    }

    assert account_id_parameter in result["parameters"]["ordering"]

    master_payer_id_parameter = {
        "constraints": {"hidden": True, "readonly": False, "required": False},
        "error": None,
        "externalId": OrderParametersEnum.MASTER_PAYER_ID,
        "id": "PAR-1234-5681",
        "name": "Master Payer ID",
        "type": "Choice",
        "value": "",
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

    client = mocker.MagicMock()
    context = PurchaseContext(order=order)
    has_errors, result = validate_purchase_order(client, context)

    transfer_type_parameter = {
        "id": "PAR-1234-5680",
        "name": "Transfer Type",
        "externalId": OrderParametersEnum.TRANSFER_TYPE,
        "type": "Choice",
        "value": TransferTypesEnum.TRANSFER_WITHOUT_ORGANIZATION,
        "error": None,
        "constraints": {"hidden": False, "required": True, "readonly": True},
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
        "type": "Choice",
        "value": "",
    }
    assert master_payer_id_parameter in result["parameters"]["ordering"]
