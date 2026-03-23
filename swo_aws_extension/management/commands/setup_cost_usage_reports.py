import re
from dataclasses import dataclass
from typing import Any, cast

from django.conf import settings
from mpt_extension_sdk.core.utils import setup_client
from mpt_extension_sdk.mpt_http.mpt import get_agreements_by_query

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.config import get_config
from swo_aws_extension.constants import (
    AgreementStatusEnum,
    S3_BILLING_EXPORT_BUCKET_TEMPLATE,
)
from swo_aws_extension.flows.jobs.billing_journal.setup.cost_usage_reports import (
    CostUsageReportsSetupService,
)
from swo_aws_extension.management.commands_helpers import StyledPrintCommand
from swo_aws_extension.swo.mpt.authorization import get_authorizations
from swo_aws_extension.swo.rql.query_builder import RQLQuery

AUTH_PATTERN = re.compile(r"^AUT-(?:\d+-)*\d+$")
AGREEMENT_PATTERN = re.compile(r"^AGR-(?:\d+-)*\d+$")


@dataclass(frozen=True)
class _ProcessResult:
    processed_count: int
    completed_count: int
    error_message: str | None = None
    failed_agreement_id: str = ""


class Command(StyledPrintCommand):
    """Setup bucket and exports for cost usage reports."""

    help = "Setup S3 bucket and CUR exports for cost usage reports"
    name = "setup_cost_usage_reports"

    def add_arguments(self, parser: Any) -> None:
        """Add command arguments."""
        parser.add_argument(
            "--authorizations",
            nargs="*",
            metavar="AUTHORIZATION",
            default=[],
            help="list of specific authorizations separated by space",
        )
        parser.add_argument(
            "--agreements",
            nargs="*",
            metavar="AGREEMENT",
            default=[],
            help="list of specific agreements separated by space",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Preview what would be created without making AWS API calls",
        )

    def handle(self, *args: Any, **options: Any) -> None:  # noqa: WPS110
        """Run command."""
        authorizations = options["authorizations"]
        agreements = options["agreements"]
        dry_run = options["dry_run"]
        error = self.validate(authorizations, agreements)
        if error:
            self.error(error)
            return

        mpt_client = setup_client()
        config = get_config()
        setup_service = CostUsageReportsSetupService()

        self.info(f"Start processing {self.name}")
        selected_authorizations = get_authorizations(
            mpt_client,
            self._build_authorizations_rql_query(authorizations),
        )
        if not selected_authorizations:
            self.warning("No authorizations found")
            self.success(f"Processing {self.name} completed.")
            return

        processed_count = 0
        completed_count = 0

        for authorization in selected_authorizations:
            authorization_id = authorization.get("id", "")
            result = self._process_authorization(
                mpt_client,
                config,
                setup_service,
                authorization,
                agreements,
                dry_run,
            )
            processed_count += result.processed_count
            completed_count += result.completed_count
            if result.error_message:
                self.error(result.error_message)
                self.error(
                    self._build_partial_summary(
                        processed_count,
                        completed_count,
                        authorization_id,
                        result.failed_agreement_id,
                    )
                )
                return

        self.success(f"Processing {self.name} completed.")

    def _process_authorization(
        self,
        mpt_client: Any,
        config: Any,
        setup_service: CostUsageReportsSetupService,
        authorization: dict[str, Any],
        agreement_ids: list[str],
        dry_run: bool,  # noqa: FBT001
    ) -> _ProcessResult:
        authorization_id = authorization.get("id", "")
        pm_account_id = authorization.get("externalIds", {}).get("operations", "")
        if not pm_account_id:
            return _ProcessResult(
                processed_count=0,
                completed_count=0,
                error_message=(
                    f"Authorization {authorization_id} has no operations external id configured"
                ),
            )

        selected_agreements = get_agreements_by_query(
            mpt_client,
            self._build_agreements_rql_query(authorization_id, agreement_ids),
        )
        if not selected_agreements:
            self.info(f"No agreements found for authorization {authorization_id}")
            return _ProcessResult(processed_count=0, completed_count=0)

        aws_client = AWSClient(config, pm_account_id, config.management_role_name)
        return self._process_agreements(
            setup_service,
            aws_client,
            pm_account_id,
            authorization_id,
            selected_agreements,
            dry_run,
        )

    def _process_agreements(
        self,
        setup_service: CostUsageReportsSetupService,
        aws_client: AWSClient,
        pm_account_id: str,
        authorization_id: str,
        selected_agreements: list[dict[str, Any]],
        dry_run: bool,  # noqa: FBT001
    ) -> _ProcessResult:
        processed_count = 0
        completed_count = 0
        for agreement in selected_agreements:
            agreement_id = agreement.get("id", "")
            mpa_account_id = agreement.get("externalIds", {}).get("vendor", "")
            if not mpa_account_id:
                return _ProcessResult(
                    processed_count=processed_count,
                    completed_count=completed_count,
                    error_message=f"Agreement {agreement_id} has no vendor external id configured",
                    failed_agreement_id=agreement_id,
                )

            processed_count += 1
            self.info(f"Processing authorization {authorization_id} agreement {agreement_id}")
            try:
                setup_result = setup_service.run(
                    aws_client,
                    pm_account_id,
                    mpa_account_id,
                    fail_on_export_error=True,
                    dry_run=dry_run,
                )
            except AWSError as setup_error:
                return _ProcessResult(
                    processed_count=processed_count,
                    completed_count=completed_count,
                    error_message=(
                        "Failed to setup cost usage reports for authorization "
                        f"{authorization_id} agreement {agreement_id}: {setup_error!s}"
                    ),
                    failed_agreement_id=agreement_id,
                )

            self.info(
                self._build_bucket_setup_message(
                    pm_account_id,
                    setup_result.bucket_status,
                )
            )
            completed_count += 1
            self.info(
                f"Completed agreement {agreement_id}: {setup_result.created_exports} created, "
                f"{setup_result.skipped_exports} skipped, {setup_result.failed_exports} failed"
            )

        return _ProcessResult(
            processed_count=processed_count,
            completed_count=completed_count,
        )

    def validate(self, authorizations: list[str], agreements: list[str]) -> str | None:
        """Validate command arguments."""
        invalid_authorizations = [
            authorization
            for authorization in authorizations
            if not AUTH_PATTERN.match(authorization)
        ]
        if invalid_authorizations:
            invalid_str = ", ".join(invalid_authorizations)
            return f"Invalid authorizations id: {invalid_str}"

        invalid_agreements = [
            agreement for agreement in agreements if not AGREEMENT_PATTERN.match(agreement)
        ]
        if invalid_agreements:
            invalid_str = ", ".join(invalid_agreements)
            return f"Invalid agreements id: {invalid_str}"

        return None

    def _build_authorizations_rql_query(self, authorizations: list[str]) -> RQLQuery:
        rql_query_factory = cast(Any, RQLQuery)
        rql_query = rql_query_factory(product__id__in=settings.MPT_PRODUCTS_IDS)
        if not authorizations:
            return rql_query

        return rql_query_factory(id__in=list(set(authorizations))) & rql_query

    def _build_agreements_rql_query(self, authorization_id: str, agreement_ids: list[str]) -> str:
        rql_query_factory = cast(Any, RQLQuery)
        rql_filter = (
            rql_query_factory(authorization__id=authorization_id)
            & rql_query_factory(
                status__in=[AgreementStatusEnum.ACTIVE, AgreementStatusEnum.UPDATING]
            )
            & rql_query_factory(product__id__in=settings.MPT_PRODUCTS_IDS)
        )
        if agreement_ids:
            rql_filter = rql_query_factory(id__in=agreement_ids) & rql_filter

        return f"{rql_filter}&select=id,externalIds"

    def _build_partial_summary(
        self,
        processed_count: int,
        completed_count: int,
        authorization_id: str,
        agreement_id: str,
    ) -> str:
        """Build partial summary for fail-fast output."""
        return (
            f"Partial summary - processed: {processed_count}, completed: {completed_count}, "
            f"failed authorization: {authorization_id}, failed agreement: {agreement_id}"
        )

    def _build_bucket_setup_message(self, pm_account_id: str, bucket_status: str) -> str:
        bucket_name = S3_BILLING_EXPORT_BUCKET_TEMPLATE.format(pm_account_id=pm_account_id)
        if bucket_status == "created":
            return f"S3 bucket: {bucket_name} created and is owned by {pm_account_id} account"
        if bucket_status == "skipped":
            return f"S3 bucket: {bucket_name} already exists and is owned by {pm_account_id} account"
        if bucket_status == "dry_run":
            return f"[DRY RUN] Would create S3 bucket: {bucket_name} for {pm_account_id} account"
        return f"S3 bucket setup status unknown for: {bucket_name}"

