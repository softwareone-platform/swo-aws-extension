from swo_aws_extension.constants import AccountTypesEnum
from swo_aws_extension.flows.error import ERR_EMAIL_ALREADY_EXIST
from swo_aws_extension.parameters import (
    PARAM_PHASE_FULFILLMENT,
    PARAM_PHASE_ORDERING,
    OrderParametersEnum,
    get_account_type,
    get_crm_termination_ticket_id,
    get_ordering_parameter,
    get_parameter,
    get_termination_type_parameter,
    prepare_parameters_for_querying,
    set_crm_termination_ticket_id,
    set_ordering_parameter_error,
)


def test_prepare_parameters_for_querying(order_factory, order_parameters_factory):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.NEW_ACCOUNT.value,
            account_name="bad-name",
            account_email="",
            termination_type="",
        )
    )
    order = set_ordering_parameter_error(
        order, OrderParametersEnum.ACCOUNT_NAME.value, ERR_EMAIL_ALREADY_EXIST.to_dict()
    )
    order = set_ordering_parameter_error(
        order, OrderParametersEnum.ROOT_ACCOUNT_EMAIL.value, ERR_EMAIL_ALREADY_EXIST.to_dict()
    )

    order = prepare_parameters_for_querying(
        order, ignore=[OrderParametersEnum.ROOT_ACCOUNT_EMAIL.value]
    )

    account_type_value = get_account_type(order)
    root_account_email_param = get_ordering_parameter(
        order, OrderParametersEnum.ROOT_ACCOUNT_EMAIL.value
    )

    actual = {
        "account_type": account_type_value,
        "root_account_email": {
            "error": root_account_email_param.get("error"),
            "constraints": root_account_email_param.get("constraints"),
        },
        "account_name_constraints": get_ordering_parameter(
            order, OrderParametersEnum.ACCOUNT_NAME.value
        ).get("constraints"),
        "account_type_value_constraints": {
            "value": get_ordering_parameter(order, OrderParametersEnum.ACCOUNT_TYPE.value).get(
                "value"
            ),
            "constraints": get_ordering_parameter(
                order, OrderParametersEnum.ACCOUNT_TYPE.value
            ).get("constraints"),
        },
        "termination_value_constraints": {
            "value": get_ordering_parameter(order, OrderParametersEnum.TERMINATION.value).get(
                "value"
            ),
            "constraints": get_ordering_parameter(order, OrderParametersEnum.TERMINATION.value).get(
                "constraints"
            ),
        },
    }
    expected = {
        "account_type": AccountTypesEnum.NEW_ACCOUNT.value,
        "root_account_email": {
            "error": ERR_EMAIL_ALREADY_EXIST.to_dict(),
            "constraints": {
                "hidden": False,
                "readonly": False,
                "required": True,
            },
        },
        "account_name_constraints": {
            "hidden": False,
            "readonly": False,
            "required": True,
        },
        "account_type_value_constraints": {
            "value": AccountTypesEnum.NEW_ACCOUNT.value,
            "constraints": {
                "hidden": False,
                "required": False,
                "readonly": True,
            },
        },
        "termination_value_constraints": {
            "value": "",
            "constraints": {"hidden": True, "readonly": True},
        },
    }
    assert actual == expected


def test_get_parameter_found():
    source = {
        "parameters": {
            PARAM_PHASE_ORDERING: [
                {"externalId": "param_1", "value": "value_1"},
                {"externalId": "param_2", "value": "value_2"},
            ]
        }
    }

    parameter = get_parameter(PARAM_PHASE_ORDERING, source, "param_1")

    assert parameter == {"externalId": "param_1", "value": "value_1"}


def test_get_parameter_not_found():
    source = {
        "parameters": {
            PARAM_PHASE_ORDERING: [
                {"externalId": "param_1", "value": "value_1"},
                {"externalId": "param_2", "value": "value_2"},
            ]
        }
    }

    parameter = get_parameter(PARAM_PHASE_ORDERING, source, "param_3")

    assert parameter == {}


def test_get_parameter_empty_source():
    source = {"parameters": {PARAM_PHASE_ORDERING: []}}

    parameter = get_parameter(PARAM_PHASE_ORDERING, source, "param_1")

    assert parameter == {}


def test_get_parameter_fulfillment_phase():
    source = {
        "parameters": {PARAM_PHASE_FULFILLMENT: [{"externalId": "param_1", "value": "value_1"}]}
    }

    parameter = get_parameter(PARAM_PHASE_FULFILLMENT, source, "param_1")

    assert parameter == {"externalId": "param_1", "value": "value_1"}


def test_set_ordering_parameter_error():
    order = {"parameters": {"ordering": [{"externalId": "param_1", "value": "value_1"}]}}
    error = {"id": "error_1", "message": "Error message"}
    updated_order = set_ordering_parameter_error(order, "param_1", error)

    parameter = get_ordering_parameter(updated_order, "param_1")

    assert parameter == {
        "externalId": "param_1",
        "value": "value_1",
        "error": error,
        "constraints": {"hidden": False, "required": True},
    }


def test_set_order_param_error_with_req_false():
    order = {"parameters": {"ordering": [{"externalId": "param_1", "value": "value_1"}]}}
    error = {"id": "error_1", "message": "Error message"}

    updated_order = set_ordering_parameter_error(order, "param_1", error, required=False)

    parameter = get_ordering_parameter(updated_order, "param_1")
    assert parameter == {
        "externalId": "param_1",
        "value": "value_1",
        "error": error,
        "constraints": {"hidden": False, "required": False},
    }


def test_get_termination_ticket_id():
    order = {
        "parameters": {
            "ordering": [
                {
                    "externalId": OrderParametersEnum.CRM_TERMINATION_TICKET_ID.value,
                    "value": "ticket_123",
                }
            ]
        }
    }

    assert get_crm_termination_ticket_id(order) == "ticket_123"


def test_get_crm_termination_ticket_id_not_set():
    order = {"parameters": {"ordering": []}}

    assert get_crm_termination_ticket_id(order) is None


def test_set_crm_termination_ticket_id():
    order = {
        "parameters": {
            "ordering": [
                {
                    "externalId": OrderParametersEnum.CRM_TERMINATION_TICKET_ID.value,
                    "value": "old_ticket",
                }
            ]
        }
    }

    updated_order = set_crm_termination_ticket_id(order, "new_ticket")

    assert updated_order["parameters"]["ordering"][0]["value"] == "new_ticket"


def test_get_termination_parameter_found(mocker):
    mock_get_fulfillment_parameter = mocker.patch(
        "swo_aws_extension.parameters.get_ordering_parameter",
        return_value={
            "externalId": OrderParametersEnum.TERMINATION.value,
            "value": "termination_flow",
        },
    )
    order = {
        "parameters": {
            "fulfillment": [
                {
                    "externalId": OrderParametersEnum.TERMINATION.value,
                    "value": "termination_flow",
                }
            ]
        }
    }

    termination_type = get_termination_type_parameter(order)

    actual = (termination_type, mock_get_fulfillment_parameter.call_args.args)
    expected = (
        "termination_flow",
        (order, OrderParametersEnum.TERMINATION.value),
    )
    assert actual == expected


def test_get_termination_parameter_not_set(mocker):
    mock_get_fulfillment_parameter = mocker.patch(
        "swo_aws_extension.parameters.get_ordering_parameter", return_value={}
    )
    order = {"parameters": {"fulfillment": []}}

    termination_type = get_termination_type_parameter(order)

    actual = (termination_type, mock_get_fulfillment_parameter.call_args.args)
    expected = (
        None,
        (order, OrderParametersEnum.TERMINATION.value),
    )
    assert actual == expected
