import logging

import pytest

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.contract_card import (
    ContractCardStep,
    map_software_one_legal_entity,
)
from swo_aws_extension.flows.steps.errors import SkipStepError
from swo_aws_extension.parameters import get_cco_contract_number, get_phase
from swo_aws_extension.swo.cco.errors import CcoError, SellerCountryNotFoundError
from swo_aws_extension.swo.cco.models import CcoContract, CreateCcoRequest, CreateCcoResponse

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


def test_pre_step_skips_wrong_phase(purchase_context):
    context = purchase_context(phase=PhasesEnum.CHECK_ONBOARD_STATUS.value)

    with pytest.raises(SkipStepError):
        ContractCardStep().pre_step(context)


def test_pre_step_skips_when_contract_number_already_set(purchase_context):
    context = purchase_context(cco_contract_number=SAMPLE_CONTRACT_NUMBER)

    with pytest.raises(SkipStepError):
        ContractCardStep().pre_step(context)


def test_pre_step_proceeds_when_phase_matches_and_no_contract(purchase_context):
    context = purchase_context()

    result = ContractCardStep().pre_step(context)

    assert result is None
    assert context.order is not None


def test_process_uses_existing_contract(mocker, purchase_context, mpt_client, caplog):
    context = purchase_context()
    existing = CcoContract(contract_number=SAMPLE_CONTRACT_NUMBER)
    mock_client = mocker.patch(f"{MODULE}.get_cco_client")
    mock_client.return_value.get_all_contracts.return_value = [existing]

    with caplog.at_level(logging.INFO):
        ContractCardStep().process(mpt_client, context)  # act

    assert get_cco_contract_number(context.order) == SAMPLE_CONTRACT_NUMBER
    mock_client.return_value.create_cco.assert_not_called()
    assert "Found existing CCO contract" in caplog.text


def test_process_creates_contract_when_none_exist(mocker, purchase_context, mpt_client, caplog):
    context = purchase_context()
    mock_client = mocker.patch(f"{MODULE}.get_cco_client")
    mock_client.return_value.get_all_contracts.return_value = []
    mock_client.return_value.create_cco.return_value = CreateCcoResponse(
        contract_number=SAMPLE_CONTRACT_NUMBER
    )

    with caplog.at_level(logging.INFO):
        ContractCardStep().process(mpt_client, context)  # act

    create_cco = mock_client.return_value.create_cco
    request: CreateCcoRequest = create_cco.call_args.args[0]
    assert get_cco_contract_number(context.order) == SAMPLE_CONTRACT_NUMBER
    assert request.software_one_legal_entity == "SWO_US"
    assert not request.customer_reference
    assert request.manufacturer_code == "SWOTS"
    assert "Created CCO contract" in caplog.text


def test_process_sets_customer_reference_from_agreement_external_id(
    mocker, purchase_context, mpt_client
):
    context = purchase_context()
    context.agreement.setdefault("externalIds", {})["client"] = "live-e2e-check"
    mock_client = mocker.patch(f"{MODULE}.get_cco_client")
    mock_client.return_value.get_all_contracts.return_value = []
    mock_client.return_value.create_cco.return_value = CreateCcoResponse(
        contract_number=SAMPLE_CONTRACT_NUMBER
    )

    ContractCardStep().process(mpt_client, context)  # act

    create_cco = mock_client.return_value.create_cco
    request: CreateCcoRequest = create_cco.call_args.args[0]
    assert request.customer_reference == "live-e2e-check"


def test_process_sets_manufacturer_code_from_config_when_vendor_external_id_missing(
    mocker, purchase_context, mpt_client
):
    context = purchase_context()
    context.agreement["externalIds"].pop("vendor", None)
    mock_client = mocker.patch(f"{MODULE}.get_cco_client")
    mock_client.return_value.get_all_contracts.return_value = []
    mock_client.return_value.create_cco.return_value = CreateCcoResponse(
        contract_number=SAMPLE_CONTRACT_NUMBER
    )

    ContractCardStep().process(mpt_client, context)  # act

    create_cco = mock_client.return_value.create_cco
    request: CreateCcoRequest = create_cco.call_args.args[0]
    assert request.manufacturer_code == "SWOTS"


def test_process_get_all_contracts_error_logs_and_notifies(
    mocker, purchase_context, mpt_client, caplog
):
    context = purchase_context()
    mock_client = mocker.patch(f"{MODULE}.get_cco_client")
    mock_client.return_value.get_all_contracts.side_effect = CcoError("API failure")
    mock_notify = mocker.patch(f"{MODULE}.notify_one_time_error")

    with caplog.at_level(logging.ERROR):
        ContractCardStep().process(mpt_client, context)  # act

    mock_notify.assert_called_once()
    assert not get_cco_contract_number(context.order)
    assert "CcoError" in caplog.text


def test_process_create_cco_error_logs_and_notifies(mocker, purchase_context, mpt_client, caplog):
    context = purchase_context()
    mock_client = mocker.patch(f"{MODULE}.get_cco_client")
    mock_client.return_value.get_all_contracts.return_value = []
    mock_client.return_value.create_cco.side_effect = CcoError("Create failed")
    mock_notify = mocker.patch(f"{MODULE}.notify_one_time_error")

    with caplog.at_level(logging.ERROR):
        ContractCardStep().process(mpt_client, context)  # act

    assert mock_notify.call_count == 2
    assert not get_cco_contract_number(context.order)
    assert "CcoError" in caplog.text


def test_post_step_updates_order(mocker, purchase_context, mpt_client):
    context = purchase_context()
    mock_update = mocker.patch(f"{MODULE}.update_order", return_value=context.order)

    ContractCardStep().post_step(mpt_client, context)  # act

    mock_update.assert_called_once_with(
        mpt_client, context.order_id, parameters=context.order["parameters"]
    )


def test_process_does_not_raise_on_error(mocker, purchase_context, mpt_client):
    """Errors must not raise — fulfillment must continue."""
    context = purchase_context()
    mock_client = mocker.patch(f"{MODULE}.get_cco_client")
    mock_client.return_value.get_all_contracts.side_effect = CcoError("hard fail")
    mocker.patch(f"{MODULE}.notify_one_time_error")

    result = ContractCardStep().process(mpt_client, context)

    assert result is None


def test_post_step_sets_phase_unchanged(mocker, purchase_context, mpt_client):
    """post_step should NOT advance the phase — SWOJobStep is responsible for that."""
    context = purchase_context()
    mocker.patch(f"{MODULE}.update_order", return_value=context.order)

    ContractCardStep().post_step(mpt_client, context)  # act

    assert get_phase(context.order) == PhasesEnum.PROJECT_CREATION.value


def test_map_software_one_legal_entity_returns_mapped_value():
    result = map_software_one_legal_entity("US")

    assert result == "SWO_US"


def test_map_software_one_legal_entity_is_case_insensitive():
    result = map_software_one_legal_entity("us")

    assert result == "SWO_US"


def test_map_software_one_legal_entity_raises_for_unknown_country():
    with pytest.raises(SellerCountryNotFoundError):
        map_software_one_legal_entity("XX")


def test_process_missing_seller_country_logs_and_notifies(
    mocker, purchase_context, mpt_client, caplog
):
    context = purchase_context()
    mock_client = mocker.patch(f"{MODULE}.get_cco_client")
    mock_client.return_value.get_all_contracts.return_value = []
    mocker.patch(
        f"{MODULE}.map_software_one_legal_entity",
        side_effect=SellerCountryNotFoundError("XX"),
    )
    mock_notify = mocker.patch(f"{MODULE}.notify_one_time_error")

    with caplog.at_level(logging.ERROR):
        result = ContractCardStep().process(mpt_client, context)

    assert result is None
    assert not get_cco_contract_number(context.order)
    mock_notify.assert_called_once()
    assert "SellerCountryNotFoundError" in caplog.text
