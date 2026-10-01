import pytest
from mpt_api_client.exceptions import MPTError

from swo_aws_extension.constants import FulfillmentParametersEnum, ParamPhasesEnum
from swo_aws_extension.flows.jobs.migration_agreement_parameters import (
    get_agreement_parameter,
    store_agreement_parameter,
)
from swo_aws_extension.parameters import get_execution_arn

MODULE = "swo_aws_extension.flows.jobs.migration_agreement_parameters"
ORDER_ID = "ORD-0792-5000-2253-4210"
AGREEMENT_ID = "AGR-2119-4550-8674-5962"
EXECUTION_ARN = "arn:aws:states:us-east-1:123456789012:execution:onboard:abc123"


@pytest.fixture
def order(fulfillment_parameters_factory):
    return {
        "id": ORDER_ID,
        "agreement": {
            "id": AGREEMENT_ID,
            "parameters": {
                "ordering": [],
                "fulfillment": fulfillment_parameters_factory(execution_arn=EXECUTION_ARN),
            },
        },
    }


def test_get_agreement_parameter(order):
    result = get_agreement_parameter(order, get_execution_arn)

    assert result == EXECUTION_ARN


@pytest.mark.parametrize("agreement", [None, {"id": AGREEMENT_ID}])
def test_get_agreement_parameter_without_agreement_parameters(agreement):
    result = get_agreement_parameter({"id": ORDER_ID, "agreement": agreement}, get_execution_arn)

    assert result is None


def test_store_agreement_parameter_updates_the_agreement(mocker, mpt_client, order):
    mock_update_agreement = mocker.patch(f"{MODULE}.update_agreement")

    result = store_agreement_parameter(
        mpt_client, order, FulfillmentParametersEnum.EXECUTION_ARN, EXECUTION_ARN
    )

    assert result is True
    mock_update_agreement.assert_called_once_with(
        mpt_client,
        AGREEMENT_ID,
        parameters={
            ParamPhasesEnum.FULFILLMENT.value: [
                {
                    "externalId": FulfillmentParametersEnum.EXECUTION_ARN.value,
                    "value": EXECUTION_ARN,
                }
            ]
        },
    )


def test_store_agreement_parameter_reports_marketplace_error(mocker, mpt_client, order):
    mocker.patch(f"{MODULE}.update_agreement", side_effect=MPTError("error"))

    result = store_agreement_parameter(
        mpt_client, order, FulfillmentParametersEnum.EXECUTION_ARN, EXECUTION_ARN
    )

    assert result is False
