import pytest
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.flows.order import InitialAWSContext
from swo_aws_extension.flows.steps.errors import FailStepError
from swo_aws_extension.flows.steps.validate_termination_order import ValidateTerminationOrder

MASTER_PAYER_VENDOR_ID = "225989344502"


def _make_context(subscriptions):
    agreement = {"externalIds": {"vendor": MASTER_PAYER_VENDOR_ID}}
    return InitialAWSContext(
        order={"id": "ORD-0000-0001"},
        agreement=agreement,
        subscriptions=subscriptions,
    )


@pytest.mark.parametrize(
    "subscriptions",
    [
        pytest.param([], id="no_matching_subscription"),
        pytest.param(
            [{"externalIds": {"vendor": MASTER_PAYER_VENDOR_ID}, "status": "Active"}],
            id="master_not_terminating",
        ),
        pytest.param(
            [{"externalIds": {"vendor": "LINKED-111111111111"}, "status": "Terminating"}],
            id="linked_account_terminating",
        ),
    ],
)
def test_process_raises_for_invalid_termination(mocker, subscriptions):
    context = _make_context(subscriptions)
    step = ValidateTerminationOrder()
    mock_client = mocker.MagicMock(spec=MPTClient)

    with pytest.raises(FailStepError) as exc_info:
        step.process(mock_client, context)

    assert exc_info.value.id == "AWS005"


def test_process_passes_when_master_terminating(mocker, caplog):
    subscriptions = [
        {"externalIds": {"vendor": MASTER_PAYER_VENDOR_ID}, "status": "Terminating"},
    ]
    context = _make_context(subscriptions)
    step = ValidateTerminationOrder()
    mock_client = mocker.MagicMock(spec=MPTClient)

    step.process(mock_client, context)  # act

    assert "Validating termination order" in caplog.text


def test_post_passes_when_master_is_terminating(mocker, caplog):
    subscriptions = [
        {"externalIds": {"vendor": MASTER_PAYER_VENDOR_ID}, "status": "Terminating"},
    ]
    context = _make_context(subscriptions)
    step = ValidateTerminationOrder()
    mock_client = mocker.MagicMock(spec=MPTClient)

    step.post_step(mock_client, context)  # act

    assert "Next - ValidateTerminationOrder completed successfully" in caplog.text
