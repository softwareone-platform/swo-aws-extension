import pytest

from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.configure_apn_program import ConfigureAPNProgram
from swo_aws_extension.flows.steps.errors import (
    AlreadyProcessedStepError,
    ConfigurationStepError,
    SkipStepError,
    UnexpectedStopError,
)
from swo_aws_extension.parameters import get_phase, get_relationship_id


def test_skip_phase_is_not_expected(fulfillment_parameters_factory, order_factory, config):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CHECK_CUSTOMER_ROLES.value
        )
    )
    context = PurchaseContext.from_order_data(order)

    with pytest.raises(SkipStepError):
        ConfigureAPNProgram(config).pre_step(context)


def test_pre_step_already_processed(fulfillment_parameters_factory, order_factory, config):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CONFIGURE_APN_PROGRAM.value,
            relationship_id="rel-123456",
        )
    )
    context = PurchaseContext.from_order_data(order)

    with pytest.raises(AlreadyProcessedStepError):
        ConfigureAPNProgram(config).pre_step(context)

    assert get_phase(context.order) == PhasesEnum.CREATE_CHANNEL_HANDSHAKE.value


def test_pre_step_success(fulfillment_parameters_factory, order_factory, config):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CONFIGURE_APN_PROGRAM.value,
            relationship_id="",
        )
    )
    context = PurchaseContext.from_order_data(order)

    result = ConfigureAPNProgram(config).pre_step(context)

    assert result is None


def test_process_success(
    order_factory,
    aws_client_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
    buyer,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CONFIGURE_APN_PROGRAM.value,
        ),
        buyer=buyer,
    )
    context = PurchaseContext.from_order_data(order)
    _, aws_client_mock = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = aws_client_mock
    aws_client_mock.get_program_management_id_by_account.return_value = "pma-identifier-123"
    aws_client_mock.create_relationship_in_partner_central.return_value = {
        "relationshipDetail": {"id": "rel-new-123456"}
    }

    ConfigureAPNProgram(config).process(mpt_client, context)  # act

    aws_client_mock.get_program_management_id_by_account.assert_called_once()
    aws_client_mock.create_relationship_in_partner_central.assert_called_once_with(
        pma_identifier="pma-identifier-123",
        mpa_id="651706759263",
        scu="US-SCU-111111",
    )
    assert get_relationship_id(context.order) == "rel-new-123456"


def test_process_missing_pma_identifier(
    order_factory,
    aws_client_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CONFIGURE_APN_PROGRAM.value,
        )
    )
    context = PurchaseContext.from_order_data(order)
    _, aws_client_mock = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = aws_client_mock
    aws_client_mock.get_program_management_id_by_account.return_value = ""

    with pytest.raises(ConfigurationStepError) as error:
        ConfigureAPNProgram(config).process(mpt_client, context)

    assert "PMA identifier not found for account" in str(error.value)


def test_process_aws_error(
    order_factory,
    aws_client_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CONFIGURE_APN_PROGRAM.value,
        )
    )
    context = PurchaseContext.from_order_data(order)
    _, aws_client_mock = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = aws_client_mock
    aws_client_mock.get_program_management_id_by_account.return_value = "pma-identifier-123"
    aws_client_mock.create_relationship_in_partner_central.side_effect = AWSError("AWS API error")

    with pytest.raises(UnexpectedStopError) as error:
        ConfigureAPNProgram(config).process(mpt_client, context)

    assert "Error creating channel relationship" in str(error.value)


def test_process_buyer_without_scu(
    order_factory,
    aws_client_factory,
    fulfillment_parameters_factory,
    config,
    mpt_client,
    buyer_factory,
):
    buyer = buyer_factory()  # buyer without externalIds.erpCustomer
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CONFIGURE_APN_PROGRAM.value,
        ),
        buyer=buyer,
    )
    context = PurchaseContext.from_order_data(order)
    _, aws_client_mock = aws_client_factory(config, "pma-id", "role-name")
    context.aws_apn_client = aws_client_mock
    aws_client_mock.get_program_management_id_by_account.return_value = "pma-identifier-123"
    aws_client_mock.create_relationship_in_partner_central.return_value = {
        "relationshipDetail": {"id": "rel-new-123456"}
    }

    ConfigureAPNProgram(config).process(mpt_client, context)  # act

    aws_client_mock.create_relationship_in_partner_central.assert_called_once_with(
        pma_identifier="pma-identifier-123",
        mpa_id="651706759263",
        scu="SCU_NOT_PROVIDED",
    )


def test_post_step_sets_phase(
    mocker, order_factory, fulfillment_parameters_factory, mpt_client, config
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CONFIGURE_APN_PROGRAM.value,
        )
    )
    context = PurchaseContext.from_order_data(order)
    step = ConfigureAPNProgram(config)
    updated_order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.CREATE_CHANNEL_HANDSHAKE.value
        )
    )
    mocker.patch(
        "swo_aws_extension.flows.steps.configure_apn_program.update_order",
        return_value=updated_order,
    )

    step.post_step(mpt_client, context)  # act

    assert get_phase(context.order) == PhasesEnum.CREATE_CHANNEL_HANDSHAKE.value
