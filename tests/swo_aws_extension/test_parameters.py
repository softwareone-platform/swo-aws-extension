from swo_aws_extension.parameters import (
    PARAM_PHASE_FULFILLMENT,
    PARAM_PHASE_ORDERING,
    OrderParametersEnum,
    get_crm_termination_ticket_id,
    get_ordering_parameter,
    get_parameter,
    get_termination_type_parameter,
    set_crm_termination_ticket_id,
    set_ordering_parameter_error,
)


def test_get_parameter_found():
    source = {
        "parameters": {
            PARAM_PHASE_ORDERING: [
                {"externalId": "param_1", "value": "value_1"},
                {"externalId": "param_2", "value": "value_2"},
            ]
        }
    }
    param = get_parameter(PARAM_PHASE_ORDERING, source, "param_1")
    assert param == {"externalId": "param_1", "value": "value_1"}


def test_get_parameter_not_found():
    source = {
        "parameters": {
            PARAM_PHASE_ORDERING: [
                {"externalId": "param_1", "value": "value_1"},
                {"externalId": "param_2", "value": "value_2"},
            ]
        }
    }
    param = get_parameter(PARAM_PHASE_ORDERING, source, "param_3")
    assert param == {}


def test_get_parameter_empty_source():
    source = {"parameters": {PARAM_PHASE_ORDERING: []}}
    param = get_parameter(PARAM_PHASE_ORDERING, source, "param_1")
    assert param == {}


def test_get_parameter_fulfillment_phase():
    source = {
        "parameters": {PARAM_PHASE_FULFILLMENT: [{"externalId": "param_1", "value": "value_1"}]}
    }
    param = get_parameter(PARAM_PHASE_FULFILLMENT, source, "param_1")
    assert param == {"externalId": "param_1", "value": "value_1"}


def test_set_ordering_parameter_error():
    order = {"parameters": {"ordering": [{"externalId": "param_1", "value": "value_1"}]}}
    error = {"id": "error_1", "message": "Error message"}
    updated_order = set_ordering_parameter_error(order, "param_1", error)

    param = get_ordering_parameter(updated_order, "param_1")
    assert param["error"] == error
    assert param["constraints"] == {"hidden": False, "required": True}


def test_set_ordering_parameter_error_with_required_false():
    order = {"parameters": {"ordering": [{"externalId": "param_1", "value": "value_1"}]}}
    error = {"id": "error_1", "message": "Error message"}
    updated_order = set_ordering_parameter_error(order, "param_1", error, required=False)

    param = get_ordering_parameter(updated_order, "param_1")
    assert param["error"] == error
    assert param["constraints"] == {"hidden": False, "required": False}


def test_get_termination_ticket_id():
    order = {
        "parameters": {
            "ordering": [
                {
                    "externalId": OrderParametersEnum.CRM_TERMINATION_TICKET_ID,
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
                    "externalId": OrderParametersEnum.CRM_TERMINATION_TICKET_ID,
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
            "externalId": OrderParametersEnum.TERMINATION,
            "value": "termination_flow",
        },
    )
    order = {
        "parameters": {
            "fulfillment": [
                {
                    "externalId": OrderParametersEnum.TERMINATION,
                    "value": "termination_flow",
                }
            ]
        }
    }
    result = get_termination_type_parameter(order)
    assert result == "termination_flow"
    mock_get_fulfillment_parameter.assert_called_once_with(order, OrderParametersEnum.TERMINATION)


def test_get_termination_parameter_not_set(mocker):
    mock_get_fulfillment_parameter = mocker.patch(
        "swo_aws_extension.parameters.get_ordering_parameter", return_value={}
    )
    order = {"parameters": {"fulfillment": []}}
    result = get_termination_type_parameter(order)
    assert result is None
    mock_get_fulfillment_parameter.assert_called_once_with(order, OrderParametersEnum.TERMINATION)
