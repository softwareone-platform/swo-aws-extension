import datetime as dt
from http import HTTPStatus
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from pytest_mock import MockerFixture

from swo_aws_extension.swo.cco.errors import CcoHttpError
from swo_aws_extension.swo.cco.models import CreateCcoRequest, CreateCcoResponse
from swo_aws_extension.swo.service_provisioning.errors import ServiceProvisioningHttpError
from swo_aws_extension.swo.service_provisioning.models import (
    ServiceContact,
    ServiceOnboardingRequest,
    ServiceOnboardingResponse,
)

BAD_REQUEST_STATUS_CODE = HTTPStatus.BAD_REQUEST.value


def test_create_cco_requires_confirmation() -> None:
    with pytest.raises(CommandError, match="confirm-live-call"):
        call_command(
            "create_cco",
            software_one_legal_entity="SWO_CH",
            contract_number_reference="60114e35-4283-46b4-9bce-5b29cc486062",
            customer_number="CH-SCU-171523",
            enrollment_number="AGR-2119-4550-9999",
            manufacturer_code="SWOTS",
            start_date="2026-01-31T00:00:00+00:00",
            currency_code="EUR",
            license_model="CAW-0046",
            customer_reference="live-e2e-check",
            service_description="DWE",
            contact_email="user.name@example.com",
            contact_first_name="User",
            contact_last_name="Name",
            contact_phone_number="+34666666666",
            contact_language_code="ES",
        )


def test_create_cco_calls_client(mocker: MockerFixture) -> None:
    mock_cco_client = mocker.Mock(spec=["create_cco"])
    mock_cco_client.create_cco.return_value = CreateCcoResponse(contract_number="CH-CCO-331705")
    mocked_get_cco_client = mocker.patch(
        "swo_aws_extension.management.commands.create_cco.get_cco_client",
        autospec=True,
        return_value=mock_cco_client,
    )
    mock_service_provisioning_client = mocker.Mock(spec=["onboard"])
    mock_service_provisioning_client.onboard.return_value = ServiceOnboardingResponse(
        erp_project_no="PRO-123-13-132",
    )
    mocked_get_service_provisioning_client = mocker.patch(
        "swo_aws_extension.management.commands.create_cco.get_service_provisioning_client",
        autospec=True,
        return_value=mock_service_provisioning_client,
    )
    output = StringIO()

    result = call_command(
        "create_cco",
        software_one_legal_entity="SWO_CH",
        contract_number_reference="60114e35-4283-46b4-9bce-5b29cc486062",
        customer_number="CH-SCU-171523",
        enrollment_number="AGR-2119-4550-9999",
        manufacturer_code="SWOTS",
        start_date="2026-01-31T00:00:00+00:00",
        currency_code="EUR",
        license_model="CAW-0046",
        customer_reference="live-e2e-check",
        service_description="DWE",
        contact_email="user.name@example.com",
        contact_first_name="User",
        contact_last_name="Name",
        contact_phone_number="+34666666666",
        contact_language_code="ES",
        confirm_live_call=True,
        stdout=output,
    )

    assert result is None
    mocked_get_cco_client.assert_called_once_with()
    mock_cco_client.create_cco.assert_called_once_with(
        CreateCcoRequest(
            software_one_legal_entity="SWO_CH",
            contract_number_reference="60114e35-4283-46b4-9bce-5b29cc486062",
            customer_number="CH-SCU-171523",
            enrollment_number="AGR-2119-4550-9999",
            manufacturer_code="SWOTS",
            start_date=dt.datetime.fromisoformat("2026-01-31T00:00:00+00:00"),
            currency_code="EUR",
            license_model="CAW-0046",
            customer_reference="live-e2e-check",
        ),
    )
    mocked_get_service_provisioning_client.assert_called_once_with()
    mock_service_provisioning_client.onboard.assert_called_once_with(
        ServiceOnboardingRequest(
            erp_client_id="SWO_CH",
            contract_no="CH-CCO-331705",
            service_description="DWE",
            contacts=[
                ServiceContact(
                    first_name="User",
                    last_name="Name",
                    email="user.name@example.com",
                    phone_number="+34666666666",
                    language_code="ES",
                ),
            ],
        ),
    )
    assert "Created CCO contract number: CH-CCO-331705" in output.getvalue()
    assert "Created Service Provisioning project number: PRO-123-13-132" in output.getvalue()


def test_create_cco_raises_command_error_for_cco_http_error(mocker: MockerFixture) -> None:
    mock_cco_client = mocker.Mock(spec=["create_cco"])
    mock_cco_client.create_cco.side_effect = CcoHttpError(HTTPStatus.BAD_REQUEST, "Bad Request")
    mocked_get_service_provisioning_client = mocker.patch(
        "swo_aws_extension.management.commands.create_cco.get_service_provisioning_client",
        autospec=True,
    )
    mocker.patch(
        "swo_aws_extension.management.commands.create_cco.get_cco_client",
        autospec=True,
        return_value=mock_cco_client,
    )

    with pytest.raises(CommandError, match=f"status={BAD_REQUEST_STATUS_CODE}"):
        call_command(
            "create_cco",
            software_one_legal_entity="SWO_CH",
            contract_number_reference="60114e35-4283-46b4-9bce-5b29cc486062",
            customer_number="CH-SCU-171523",
            enrollment_number="AGR-2119-4550-9999",
            manufacturer_code="SWOTS",
            start_date="2026-01-31T00:00:00+00:00",
            currency_code="EUR",
            license_model="CAW-0046",
            customer_reference="live-e2e-check",
            service_description="DWE",
            contact_email="user.name@example.com",
            contact_first_name="User",
            contact_last_name="Name",
            contact_phone_number="+34666666666",
            contact_language_code="ES",
            confirm_live_call=True,
        )

    mocked_get_service_provisioning_client.assert_not_called()


def test_create_cco_raises_command_error_for_service_provisioning_http_error(
    mocker: MockerFixture,
) -> None:
    mock_cco_client = mocker.Mock(spec=["create_cco"])
    mock_cco_client.create_cco.return_value = CreateCcoResponse(contract_number="CH-CCO-331705")
    mock_service_provisioning_client = mocker.Mock(spec=["onboard"])
    mock_service_provisioning_client.onboard.side_effect = ServiceProvisioningHttpError(
        HTTPStatus.BAD_REQUEST,
        "Bad Request",
    )
    mocker.patch(
        "swo_aws_extension.management.commands.create_cco.get_cco_client",
        autospec=True,
        return_value=mock_cco_client,
    )
    mocker.patch(
        "swo_aws_extension.management.commands.create_cco.get_service_provisioning_client",
        autospec=True,
        return_value=mock_service_provisioning_client,
    )

    with pytest.raises(CommandError, match=f"status={BAD_REQUEST_STATUS_CODE}"):
        call_command(
            "create_cco",
            software_one_legal_entity="SWO_CH",
            contract_number_reference="60114e35-4283-46b4-9bce-5b29cc486062",
            customer_number="CH-SCU-171523",
            enrollment_number="AGR-2119-4550-9999",
            manufacturer_code="SWOTS",
            start_date="2026-01-31T00:00:00+00:00",
            currency_code="EUR",
            license_model="CAW-0046",
            customer_reference="live-e2e-check",
            service_description="DWE",
            contact_email="user.name@example.com",
            contact_first_name="User",
            contact_last_name="Name",
            contact_phone_number="+34666666666",
            contact_language_code="ES",
            confirm_live_call=True,
        )
