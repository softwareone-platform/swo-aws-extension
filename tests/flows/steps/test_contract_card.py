import logging

import pytest

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.contract_card import ContractCardStep
from swo_aws_extension.flows.steps.errors import SkipStepError
from swo_aws_extension.parameters import get_cco_contract_number, get_phase
from swo_aws_extension.swo.cco.errors import CcoError
from swo_aws_extension.swo.cco.models import CcoContract, CreateCcoResponse

MODULE = "swo_aws_extension.flows.steps.contract_card"
SAMPLE_CONTRACT_NUMBER = "CH-CCO-331705"
SAMPLE_MPA_ID = "651706759263"


@pytest.fixture
def purchase_context(order_factory, fulfillment_parameters_factory, order_parameters_factory):
    def factory(phase=PhasesEnum.PROJECT_CREATION.value, cco_contract_number=""):
        order = order_factory(
            order_parameters=order_parameters_factory(mpa_id=SAMPLE_MPA_ID),
            fulfillment_parameters=fulfillment_parameters_factory(
                phase=phase,
                cco_contract_number=cco_contract_number,
            ),
        )
        return PurchaseContext.from_order_data(order)

    return factory


def test_pre_step_skips_wrong_phase(purchase_context, config):
    context = purchase_context(phase=PhasesEnum.CHECK_ONBOARD_STATUS.value)

    with pytest.raises(SkipStepError):
        ContractCardStep(config).pre_step(context)


def test_pre_step_skips_when_contract_number_already_set(purchase_context, config):
    context = purchase_context(cco_contract_number=SAMPLE_CONTRACT_NUMBER)

    with pytest.raises(SkipStepError):
        ContractCardStep(config).pre_step(context)


def test_pre_step_proceeds_when_phase_matches_and_no_contract(purchase_context, config):
    context = purchase_context()

    result = ContractCardStep(config).pre_step(context)

    assert result is None
    assert context.order is not None


def test_process_uses_existing_contract(mocker, purchase_context, mpt_client, config, caplog):
    context = purchase_context()
    existing = CcoContract(contract_number=SAMPLE_CONTRACT_NUMBER)
    mock_client = mocker.patch(f"{MODULE}.get_cco_client")
    mock_client.return_value.get_all_contracts.return_value = [existing]

    with caplog.at_level(logging.INFO):
        ContractCardStep(config).process(mpt_client, context)  # act

    assert get_cco_contract_number(context.order) == SAMPLE_CONTRACT_NUMBER
    mock_client.return_value.create_cco.assert_not_called()
    assert "Found existing CCO contract" in caplog.text


def test_process_creates_contract_when_none_exist(
    mocker, purchase_context, mpt_client, config, caplog
):
    context = purchase_context()
    mock_client = mocker.patch(f"{MODULE}.get_cco_client")
    mock_client.return_value.get_all_contracts.return_value = []
    mock_client.return_value.create_cco.return_value = CreateCcoResponse(
        contract_number=SAMPLE_CONTRACT_NUMBER
    )

    with caplog.at_level(logging.INFO):
        ContractCardStep(config).process(mpt_client, context)  # act

    assert get_cco_contract_number(context.order) == SAMPLE_CONTRACT_NUMBER
    mock_client.return_value.create_cco.assert_called_once()
    assert "Created CCO contract" in caplog.text


def test_process_get_all_contracts_error_logs_and_notifies(
    mocker, purchase_context, mpt_client, config, caplog
):
    context = purchase_context()
    mock_client = mocker.patch(f"{MODULE}.get_cco_client")
    mock_client.return_value.get_all_contracts.side_effect = CcoError("API failure")
    mock_notify = mocker.patch(f"{MODULE}.TeamsNotificationManager.send_error", autospec=True)

    with caplog.at_level(logging.ERROR):
        ContractCardStep(config).process(mpt_client, context)  # act

    mock_notify.assert_called_once()
    assert not get_cco_contract_number(context.order)
    assert "CcoError" in caplog.text


def test_process_create_cco_error_logs_and_notifies(
    mocker, purchase_context, mpt_client, config, caplog
):
    context = purchase_context()
    mock_client = mocker.patch(f"{MODULE}.get_cco_client")
    mock_client.return_value.get_all_contracts.return_value = []
    mock_client.return_value.create_cco.side_effect = CcoError("Create failed")
    mock_notify = mocker.patch(f"{MODULE}.TeamsNotificationManager.send_error", autospec=True)

    with caplog.at_level(logging.ERROR):
        ContractCardStep(config).process(mpt_client, context)  # act

    mock_notify.assert_called_once()
    assert not get_cco_contract_number(context.order)
    assert "CcoError" in caplog.text


def test_post_step_updates_order(mocker, purchase_context, mpt_client, config):
    context = purchase_context()
    mock_update = mocker.patch(f"{MODULE}.update_order", return_value=context.order)

    ContractCardStep(config).post_step(mpt_client, context)  # act

    mock_update.assert_called_once_with(
        mpt_client, context.order_id, parameters=context.order["parameters"]
    )


def test_process_does_not_raise_on_error(mocker, purchase_context, mpt_client, config):
    """Errors must not raise — fulfillment must continue."""
    context = purchase_context()
    mock_client = mocker.patch(f"{MODULE}.get_cco_client")
    mock_client.return_value.get_all_contracts.side_effect = CcoError("hard fail")
    mocker.patch(f"{MODULE}.TeamsNotificationManager.send_error", autospec=True)

    result = ContractCardStep(config).process(mpt_client, context)

    assert result is None


def test_post_step_sets_phase_unchanged(mocker, purchase_context, mpt_client, config):
    """post_step should NOT advance the phase — SWOJobStep is responsible for that."""
    context = purchase_context()
    mocker.patch(f"{MODULE}.update_order", return_value=context.order)

    ContractCardStep(config).post_step(mpt_client, context)  # act

    assert get_phase(context.order) == PhasesEnum.PROJECT_CREATION.value
