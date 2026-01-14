from swo_aws_extension.constants import (
    AccountTypesEnum,
    OrderParametersEnum,
    ResoldSupportPlansEnum,
    SupportTypesEnum,
)
from swo_aws_extension.flows.validation.base import update_parameters_visibility
from swo_aws_extension.parameters import get_ordering_parameter


def test_new_aws_environment(order_factory, order_parameters_factory):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.NEW_AWS_ENVIRONMENT.value,
            constraints={"hidden": None, "required": None, "readonly": None},
        )
    )

    result = update_parameters_visibility(order)

    order_account_name_param = get_ordering_parameter(
        OrderParametersEnum.ORDER_ACCOUNT_NAME.value, result
    )
    assert order_account_name_param == {
        "constraints": {"hidden": False, "readonly": False, "required": True},
        "error": None,
        "externalId": "orderAccountName",
        "id": "PAR-1234-5680",
        "name": "Order Account Name",
        "type": "choice",
        "value": "Order Account Name",
    }
    order_account_email = get_ordering_parameter(
        OrderParametersEnum.ORDER_ACCOUNT_EMAIL.value, result
    )
    assert order_account_email == {
        "constraints": {"hidden": False, "readonly": False, "required": True},
        "error": None,
        "externalId": "orderAccountEmail",
        "id": "PAR-1234-5680",
        "name": "Order Root Account Email",
        "type": "choice",
        "value": "example@example.com",
    }
    master_payer_param = get_ordering_parameter(
        OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID.value, result
    )
    assert master_payer_param == {
        "constraints": {"hidden": True, "readonly": True, "required": False},
        "error": None,
        "externalId": "masterPayerID",
        "id": "PAR-1234-5680",
        "name": "Master Payer Account ID",
        "type": "choice",
        "value": None,
    }


def test_existing_aws_environment(order_factory, order_parameters_factory):
    """Test update params visibility for an existing AWS environment."""
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_AWS_ENVIRONMENT.value,
            constraints={"hidden": None, "required": None, "readonly": None},
        )
    )

    result = update_parameters_visibility(order)

    master_payer_param = get_ordering_parameter(
        OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID.value, result
    )
    assert master_payer_param == {
        "constraints": {"hidden": False, "readonly": False, "required": True},
        "error": None,
        "externalId": "masterPayerID",
        "id": "PAR-1234-5680",
        "name": "Master Payer Account ID",
        "type": "choice",
        "value": "651706759263",
    }
    order_account_name_param = get_ordering_parameter(
        OrderParametersEnum.ORDER_ACCOUNT_NAME.value, result
    )
    assert order_account_name_param == {
        "constraints": {"hidden": True, "readonly": True, "required": False},
        "error": None,
        "externalId": "orderAccountName",
        "id": "PAR-1234-5680",
        "name": "Order Account Name",
        "type": "choice",
        "value": None,
    }
    order_account_email = get_ordering_parameter(
        OrderParametersEnum.ORDER_ACCOUNT_EMAIL.value, result
    )
    assert order_account_email == {
        "constraints": {"hidden": True, "readonly": True, "required": False},
        "error": None,
        "externalId": "orderAccountEmail",
        "id": "PAR-1234-5680",
        "name": "Order Root Account Email",
        "type": "choice",
        "value": None,
    }


def test_existing_aws_env_with_support_resold_support(order_factory, order_parameters_factory):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_AWS_ENVIRONMENT.value,
            support_type=SupportTypesEnum.AWS_RESOLD_SUPPORT.value,
            aws_type_of_support=ResoldSupportPlansEnum.ENTERPRISE_SUPPORT.value,
            constraints={"hidden": None, "required": None, "readonly": None},
        )
    )

    result = update_parameters_visibility(order)

    order_aws_type_of_support = get_ordering_parameter(
        OrderParametersEnum.RESOLD_SUPPORT_PLANS.value, result
    )
    assert order_aws_type_of_support == {
        "constraints": {"hidden": False, "readonly": False, "required": False},
        "error": None,
        "externalId": "resoldSupportPlans",
        "id": "PAR-1234-5682",
        "value": "EnterpriseSupport",
        "name": "AWS type of support",
        "type": "choice",
    }


def test_aws_environment_resold_support_without_aws_type_of_support(
    order_factory, order_parameters_factory
):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_AWS_ENVIRONMENT.value,
            support_type=SupportTypesEnum.AWS_RESOLD_SUPPORT.value,
            aws_type_of_support=None,
            constraints={"hidden": None, "required": None, "readonly": None},
        )
    )

    result = update_parameters_visibility(order)

    order_aws_type_of_support = get_ordering_parameter(
        OrderParametersEnum.RESOLD_SUPPORT_PLANS.value, result
    )
    assert order_aws_type_of_support == {
        "constraints": {"hidden": False, "readonly": False, "required": False},
        "error": {
            "id": "AWS002",
            "message": "You should select the type of support",
        },
        "externalId": "resoldSupportPlans",
        "id": "PAR-1234-5682",
        "value": None,
        "name": "AWS type of support",
        "type": "choice",
    }


def test_existing_aws_env_with_support_partner_led_support(order_factory, order_parameters_factory):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.EXISTING_AWS_ENVIRONMENT.value,
            support_type=SupportTypesEnum.PARTNER_LED_SUPPORT.value,
            aws_type_of_support=None,
            constraints={"hidden": None, "required": None, "readonly": None},
        )
    )

    result = update_parameters_visibility(order)

    order_aws_type_of_support = get_ordering_parameter(
        OrderParametersEnum.RESOLD_SUPPORT_PLANS.value, result
    )
    assert order_aws_type_of_support == {
        "constraints": {"hidden": True, "readonly": True, "required": False},
        "error": None,
        "externalId": "resoldSupportPlans",
        "id": "PAR-1234-5682",
        "value": None,
        "name": "AWS type of support",
        "type": "choice",
    }


def test_empty_values(order_factory, order_parameters_factory):
    """Test the update_parameters_visibility function when parameter values are empty."""
    order = order_factory(order_parameters=order_parameters_factory(account_type=None))

    result = update_parameters_visibility(order)

    account_type_param = get_ordering_parameter(OrderParametersEnum.ACCOUNT_TYPE.value, result)
    assert account_type_param["error"] == {
        "id": "AWS001",
        "message": "Invalid account type: None",
    }
