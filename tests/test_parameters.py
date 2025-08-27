from swo_aws_extension.constants import AccountTypesEnum
from swo_aws_extension.flows.error import ERR_EMAIL_ALREADY_EXIST
from swo_aws_extension.parameters import (
    OrderParametersEnum,
    get_account_type,
    get_ordering_parameter,
    prepare_parameters_for_querying,
    set_ordering_parameter_error,
)


# TODO: make one assert
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
    assert get_account_type(order) == AccountTypesEnum.NEW_ACCOUNT.value
    error_parameters = [OrderParametersEnum.ROOT_ACCOUNT_EMAIL.value]

    order = prepare_parameters_for_querying(order, ignore=error_parameters)

    # Check order paramters is not hidden and not readonly
    root_account_email_param = get_ordering_parameter(
        order, OrderParametersEnum.ROOT_ACCOUNT_EMAIL.value
    )
    assert root_account_email_param["error"] == ERR_EMAIL_ALREADY_EXIST.to_dict()
    assert root_account_email_param["constraints"] == {
        "hidden": False,
        "readonly": False,
        "required": True,
    }

    # Check hidden parameter is not hiding parameters with errors
    account_name_parameter = get_ordering_parameter(order, OrderParametersEnum.ACCOUNT_NAME.value)
    assert account_name_parameter["constraints"] == {
        "hidden": False,
        "readonly": False,
        "required": True,
    }

    # Check set paramter is not hidden but readonly
    account_type_parameter = get_ordering_parameter(order, OrderParametersEnum.ACCOUNT_TYPE.value)
    assert account_type_parameter["value"] == AccountTypesEnum.NEW_ACCOUNT.value
    assert account_type_parameter["constraints"] == {
        "hidden": False,
        "required": False,
        "readonly": True,
    }

    # Check empty parameter is hidden
    termination_parameter = get_ordering_parameter(order, OrderParametersEnum.TERMINATION.value)
    assert not termination_parameter["value"]
    assert termination_parameter["constraints"] == {"hidden": True, "readonly": True}
