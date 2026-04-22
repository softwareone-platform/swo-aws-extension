import logging

import pytest

from swo_aws_extension.constants import PhasesEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.flows.steps.errors import SkipStepError
from swo_aws_extension.flows.steps.swo_job import SWOJobStep
from swo_aws_extension.parameters import get_erp_project_no, get_phase
from swo_aws_extension.swo.cco.errors import SellerCountryNotFoundError
from swo_aws_extension.swo.service_provisioning.errors import ServiceProvisioningError
from swo_aws_extension.swo.service_provisioning.models import ServiceOnboardingResponse

MODULE = "swo_aws_extension.flows.steps.swo_job"
SAMPLE_CONTRACT_NUMBER = "CH-CCO-331705"
SAMPLE_ERP_PROJECT_NO = "ERP-123456"


@pytest.fixture
def purchase_context(order_factory, fulfillment_parameters_factory, order_parameters_factory):
    def factory(
        phase=PhasesEnum.PROJECT_CREATION.value, cco_contract_number=SAMPLE_CONTRACT_NUMBER
    ):
        order = order_factory(
            order_parameters=order_parameters_factory(),
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
        SWOJobStep().pre_step(context)


def test_pre_step_proceeds_when_phase_matches(purchase_context):
    context = purchase_context()

    result = SWOJobStep().pre_step(context)

    assert result is None
    assert context.order is not None


def test_process_creates_swo_job_and_sets_erp_project_no(
    mocker, purchase_context, mpt_client, caplog
):
    context = purchase_context()
    mock_client = mocker.patch(f"{MODULE}.get_service_provisioning_client")
    mock_client.return_value.onboard.return_value = ServiceOnboardingResponse(
        erp_project_no=SAMPLE_ERP_PROJECT_NO
    )

    with caplog.at_level(logging.INFO):
        SWOJobStep().process(mpt_client, context)  # act

    assert get_erp_project_no(context.order) == SAMPLE_ERP_PROJECT_NO
    mock_client.return_value.onboard.assert_called_once()
    assert "SWO Job created with ERP project number" in caplog.text


def test_process_missing_contract_number_logs_and_notifies(
    mocker, purchase_context, mpt_client, caplog
):
    context = purchase_context(cco_contract_number="")
    mock_client = mocker.patch(f"{MODULE}.get_service_provisioning_client")
    mock_notify = mocker.patch(f"{MODULE}.notify_one_time_error")

    with caplog.at_level(logging.WARNING):
        SWOJobStep().process(mpt_client, context)  # act

    mock_client.return_value.onboard.assert_not_called()
    mock_notify.assert_called_once()
    assert "ccoContractNumber is not set" in caplog.text


def test_process_missing_contract_does_not_raise(mocker, purchase_context, mpt_client):
    context = purchase_context(cco_contract_number="")
    mocker.patch(f"{MODULE}.get_service_provisioning_client")
    mocker.patch(f"{MODULE}.notify_one_time_error")

    result = SWOJobStep().process(mpt_client, context)

    assert result is None


def test_process_service_provisioning_error_logs_and_notifies(
    mocker, purchase_context, mpt_client, caplog
):
    context = purchase_context()
    mock_client = mocker.patch(f"{MODULE}.get_service_provisioning_client")
    mock_client.return_value.onboard.side_effect = ServiceProvisioningError("API error")
    mock_notify = mocker.patch(f"{MODULE}.notify_one_time_error")

    with caplog.at_level(logging.ERROR):
        SWOJobStep().process(mpt_client, context)  # act

    mock_notify.assert_called_once()
    assert "ServiceProvisioningError" in caplog.text


def test_process_service_provisioning_error_does_not_raise(mocker, purchase_context, mpt_client):
    context = purchase_context()
    mock_client = mocker.patch(f"{MODULE}.get_service_provisioning_client")
    mock_client.return_value.onboard.side_effect = ServiceProvisioningError("hard fail")
    mocker.patch(f"{MODULE}.notify_one_time_error")

    result = SWOJobStep().process(mpt_client, context)

    assert result is None


def test_process_seller_country_not_found_logs_and_notifies(
    mocker, purchase_context, mpt_client, caplog
):
    context = purchase_context()
    mocker.patch(f"{MODULE}.SellerMapper.map", side_effect=SellerCountryNotFoundError("XX"))
    mock_notify = mocker.patch(f"{MODULE}.notify_one_time_error")

    with caplog.at_level(logging.ERROR):
        result = SWOJobStep().process(mpt_client, context)

    assert result is None
    mock_notify.assert_called_once()
    assert "SellerCountryNotFoundError" in caplog.text


def test_post_step_sets_completed_phase(
    mocker,
    purchase_context,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
    mpt_client,
):
    context = purchase_context()
    updated_order = order_factory(
        order_parameters=order_parameters_factory(),
        fulfillment_parameters=fulfillment_parameters_factory(
            phase=PhasesEnum.COMPLETED.value,
            cco_contract_number=SAMPLE_CONTRACT_NUMBER,
        ),
    )
    mock_update = mocker.patch(f"{MODULE}.update_order", autospec=True, return_value=updated_order)

    SWOJobStep().post_step(mpt_client, context)  # act

    assert get_phase(context.order) == PhasesEnum.COMPLETED.value
    mock_update.assert_called_once()


def test_process_onboard_called_with_correct_contract_no(mocker, purchase_context, mpt_client):
    context = purchase_context()
    mock_client = mocker.patch(f"{MODULE}.get_service_provisioning_client")
    mock_client.return_value.onboard.return_value = ServiceOnboardingResponse(
        erp_project_no=SAMPLE_ERP_PROJECT_NO
    )

    SWOJobStep().process(mpt_client, context)  # act

    onboard_call = mock_client.return_value.onboard.call_args
    request = onboard_call.args[0]
    assert request.contract_no == SAMPLE_CONTRACT_NUMBER
