import datetime as dt
from typing import Any

from django.core.management.base import CommandError

from swo_aws_extension.management.commands_helpers import StyledPrintCommand
from swo_aws_extension.swo.cco.client import get_cco_client
from swo_aws_extension.swo.cco.errors import CcoHttpError
from swo_aws_extension.swo.cco.models import CreateCcoRequest, CreateCcoResponse
from swo_aws_extension.swo.service_provisioning.client import get_service_provisioning_client
from swo_aws_extension.swo.service_provisioning.errors import ServiceProvisioningHttpError
from swo_aws_extension.swo.service_provisioning.models import (
    ServiceContact,
    ServiceOnboardingRequest,
    ServiceOnboardingResponse,
)

CONTACT_ARGUMENT_FLAGS = (
    "--contact-email",
    "--contact-first-name",
    "--contact-last-name",
    "--contact-phone-number",
    "--contact-language-code",
)


class Command(StyledPrintCommand):
    """Create a CCO contract and trigger Service Provisioning onboarding."""

    help = "Create a CCO contract and onboard it in Service Provisioning."

    def add_arguments(self, parser: Any) -> None:
        """Add command arguments for CCO record creation."""
        self._add_required_arguments(parser)
        for flag in CONTACT_ARGUMENT_FLAGS:
            parser.add_argument(flag, required=True)
        parser.add_argument("--customer-reference", default="")
        parser.add_argument("--service-description", required=True)
        parser.add_argument("--confirm-live-call", action="store_true", default=False)

    def handle(self, *args: Any, **options: Any) -> None:  # noqa: WPS110
        """Validate input and call the live CCO create endpoint."""
        if not options["confirm_live_call"]:
            raise CommandError("Live call blocked. Pass --confirm-live-call to execute.")

        start_date = self._parse_start_date(options["start_date"])
        create_request = self._build_create_request(options, start_date)
        create_response = self._create_cco_record(create_request)
        service_onboarding_response = self._create_service_onboarding_record(
            options,
            create_response.contract_number,
        )

        self.success(f"Created CCO contract number: {create_response.contract_number}")
        self.success(
            "Created Service Provisioning project number: "
            f"{service_onboarding_response.erp_project_no}",
        )

    def _add_required_arguments(self, parser: Any) -> None:
        """Register command options required by the CCO create endpoint."""
        parser.add_argument("--software-one-legal-entity", required=True)
        parser.add_argument("--contract-number-reference", required=True)
        parser.add_argument("--customer-number", required=True)
        parser.add_argument("--enrollment-number", required=True)
        parser.add_argument("--manufacturer-code", required=True)
        parser.add_argument("--start-date", required=True)
        parser.add_argument("--currency-code", required=True)
        parser.add_argument("--license-model", required=True)

    def _parse_start_date(self, start_date: str) -> dt.datetime:
        """Parse command start-date argument."""
        try:
            return dt.datetime.fromisoformat(start_date)
        except ValueError as error:
            raise CommandError(
                "Invalid --start-date format. Use ISO-8601, for example 2026-01-31T00:00:00+00:00.",
            ) from error

    def _build_create_request(
        self, options: dict[str, Any], start_date: dt.datetime
    ) -> CreateCcoRequest:
        """Build CCO create request from command options."""
        return CreateCcoRequest(
            software_one_legal_entity=options["software_one_legal_entity"],
            contract_number_reference=options["contract_number_reference"],
            customer_number=options["customer_number"],
            enrollment_number=options["enrollment_number"],
            manufacturer_code=options["manufacturer_code"],
            start_date=start_date,
            currency_code=options["currency_code"],
            license_model=options["license_model"],
            customer_reference=options["customer_reference"],
        )

    def _create_cco_record(self, create_request: CreateCcoRequest) -> CreateCcoResponse:
        """Call CCO create endpoint and map transport errors to command errors."""
        self.info("Creating CCO record with live endpoint...")
        cco_client = get_cco_client()
        try:
            return cco_client.create_cco(create_request)
        except CcoHttpError as error:
            raise CommandError(
                f"CCO create failed (status={error.status_code}): {error.message}",
            ) from error

    def _create_service_onboarding_record(
        self,
        options: dict[str, Any],
        contract_number: str,
    ) -> ServiceOnboardingResponse:
        """Call Service Provisioning onboarding endpoint and map transport errors."""
        contact = ServiceContact(
            first_name=options["contact_first_name"],
            last_name=options["contact_last_name"],
            email=options["contact_email"],
            phone_number=options["contact_phone_number"],
            language_code=options["contact_language_code"],
        )
        service_onboarding_request = ServiceOnboardingRequest(
            erp_client_id=options["software_one_legal_entity"],
            contract_no=contract_number,
            service_description=options["service_description"],
            contacts=[contact],
        )
        self.info("Creating Service Provisioning onboarding record...")
        service_provisioning_client = get_service_provisioning_client()
        try:
            return service_provisioning_client.onboard(service_onboarding_request)
        except ServiceProvisioningHttpError as error:
            raise CommandError(
                "Service Provisioning onboarding failed "
                f"(status={error.status_code}): {error.message}",
            ) from error
