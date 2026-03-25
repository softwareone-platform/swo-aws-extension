import re
from dataclasses import dataclass
from typing import Any, cast

from django.conf import settings
from mpt_extension_sdk.core.utils import setup_client

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError
from swo_aws_extension.config import get_config
from swo_aws_extension.constants import S3_BILLING_EXPORT_BUCKET_TEMPLATE
from swo_aws_extension.flows.jobs.billing_journal.setup.cost_usage_reports import (
    CostUsageReportsSetupService,
)
from swo_aws_extension.management.commands_helpers import StyledPrintCommand
from swo_aws_extension.swo.mpt.authorization import get_authorizations
from swo_aws_extension.swo.rql.query_builder import RQLQuery

AUTH_PATTERN = re.compile(r"^AUT-(?:\d+-)*\d+$")


@dataclass(frozen=True)
class _ProcessResult:
    processed_count: int
    completed_count: int
    error_message: str | None = None
    failed_authorization_id: str = ""


class Command(StyledPrintCommand):
    """Setup bucket and CUR exports by authorization PM account."""

    help = "Setup S3 bucket and CUR exports for authorization PM accounts"
    name = "setup_cost_usage_reports_by_authorizations"

    def add_arguments(self, parser: Any) -> None:
        """Add command arguments.

        Args:
            parser: Django command argument parser.
        """
        parser.add_argument(
            "--authorizations",
            nargs="*",
            metavar="AUTHORIZATION",
            default=[],
            help="list of specific authorizations separated by space",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Preview what would be created without making AWS API calls",
        )

    def handle(self, *args: Any, **options: Any) -> None:  # noqa: WPS110
        """Run the command.

        Args:
            *args: Positional command arguments.
            **options: Parsed command options.
        """
        authorizations = options["authorizations"]
        dry_run = options["dry_run"]
        error = self.validate(authorizations)
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
                config,
                setup_service,
                authorization,
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
                    )
                )
                return

        self.success(f"Processing {self.name} completed.")

    def _process_authorization(
        self,
        config: Any,
        setup_service: CostUsageReportsSetupService,
        authorization: dict[str, Any],
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
                failed_authorization_id=authorization_id,
            )

        self.info(f"Processing authorization {authorization_id} using PM account {pm_account_id}")
        aws_client = AWSClient(config, pm_account_id, config.management_role_name)
        try:
            setup_result = setup_service.run_for_authorization(
                aws_client,
                pm_account_id,
                fail_on_export_error=False,
                dry_run=dry_run,
            )
        except AWSError as setup_error:
            return _ProcessResult(
                processed_count=1,
                completed_count=0,
                error_message=(
                    "Failed to setup cost usage reports for authorization "
                    f"{authorization_id}: {setup_error!s}"
                ),
                failed_authorization_id=authorization_id,
            )

        self.info(
            self._build_bucket_setup_message(
                pm_account_id,
                setup_result.bucket_status,
            )
        )
        self.info(
            f"Completed authorization {authorization_id}: {setup_result.created_exports} created, "
            f"{setup_result.skipped_exports} skipped, {setup_result.failed_exports} failed"
        )
        return _ProcessResult(
            processed_count=1,
            completed_count=1,
        )

    def validate(self, authorizations: list[str]) -> str | None:
        """Validate command arguments.

        Args:
            authorizations: Authorization IDs provided to the command.

        Returns:
            Validation error text when input is invalid, otherwise ``None``.
        """
        invalid_authorizations = [
            authorization
            for authorization in authorizations
            if not AUTH_PATTERN.match(authorization)
        ]
        if invalid_authorizations:
            invalid_str = ", ".join(invalid_authorizations)
            return f"Invalid authorizations id: {invalid_str}"

        return None

    def _build_authorizations_rql_query(self, authorizations: list[str]) -> Any:
        rql_query_factory = cast(Any, RQLQuery)
        rql_query = rql_query_factory(product__id__in=settings.MPT_PRODUCTS_IDS)
        if not authorizations:
            return rql_query

        return rql_query_factory(id__in=list(set(authorizations))) & rql_query

    def _build_partial_summary(
        self,
        processed_count: int,
        completed_count: int,
        authorization_id: str,
    ) -> str:
        """Build partial summary for fail-fast output."""
        return (
            f"Partial summary - processed: {processed_count}, completed: {completed_count}, "
            f"failed authorization: {authorization_id}"
        )

    def _build_bucket_setup_message(self, pm_account_id: str, bucket_status: str) -> str:
        """Build human-readable S3 bucket setup status message.

        Args:
            pm_account_id: Program management account ID.
            bucket_status: The bucket setup status string.

        Returns:
            Formatted message describing the bucket setup outcome.
        """
        bucket_name = S3_BILLING_EXPORT_BUCKET_TEMPLATE.format(pm_account_id=pm_account_id)
        if bucket_status == "created":
            return f"S3 bucket: {bucket_name} created and is owned by {pm_account_id} account"
        if bucket_status == "skipped":
            return (
                f"S3 bucket: {bucket_name} already exists and is owned by {pm_account_id} account"
            )
        if bucket_status == "dry_run":
            return f"[DRY RUN] Would create S3 bucket: {bucket_name} for {pm_account_id} account"
        return f"S3 bucket setup status unknown for: {bucket_name}"
