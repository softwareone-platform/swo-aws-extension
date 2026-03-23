import logging
from dataclasses import dataclass

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.errors import AWSError, S3BucketAlreadyOwnedError
from swo_aws_extension.constants import (
    S3_BILLING_EXPORT_BUCKET_TEMPLATE,
    S3_BILLING_EXPORT_PREFIX_TEMPLATE,
    S3_BILLING_EXPORT_REGION,
)

logger = logging.getLogger(__name__)

_BILLING_TRANSFER_PREFIX = "billing-transfer-"
_VIEW_S3_PREFIX_TEMPLATE = "{s3_prefix}/{billing_view_tail}"
_BUCKET_STATUS_CREATED = "created"
_BUCKET_STATUS_SKIPPED = "skipped"
_BUCKET_STATUS_DRY_RUN = "dry_run"
_BUCKET_STATUS_NOT_ATTEMPTED = "not_attempted"


def extract_billing_view_id(billing_view_arn: str) -> str:
    """Extract the billing view identifier from a billing view ARN.

    Args:
        billing_view_arn: Full billing view ARN.

    Returns:
        The billing view identifier used for export naming.
    """
    tail = billing_view_arn.rsplit("/", 1)[-1]
    if tail.startswith(_BILLING_TRANSFER_PREFIX):
        return tail[len(_BILLING_TRANSFER_PREFIX) :]
    return tail


@dataclass(frozen=True)
class CostUsageReportsSetupResult:
    """Result of cost usage reports setup for one agreement."""

    created_exports: int
    skipped_exports: int
    failed_exports: int
    bucket_status: str = _BUCKET_STATUS_NOT_ATTEMPTED


class CostUsageReportsSetupService:
    """Setup S3 bucket and CUR exports used by cost usage reports."""

    def run(
        self,
        aws_client: AWSClient,
        pm_account_id: str,
        mpa_account_id: str,
        *,
        fail_on_export_error: bool = False,
        dry_run: bool = False,
    ) -> CostUsageReportsSetupResult:
        """Run bucket setup and billing export setup.

        Args:
            aws_client: AWS client configured for the PM account.
            pm_account_id: Program management account ID.
            mpa_account_id: Master payer account ID.
            fail_on_export_error: Whether a single export creation error should stop processing.
            dry_run: If True, skip actual AWS API calls and log what would be done.

        Returns:
            Result with export counters.
        """
        bucket_status = self.setup_s3_bucket(aws_client, pm_account_id, dry_run=dry_run)
        export_result = self.create_billing_exports(
            aws_client,
            pm_account_id,
            mpa_account_id,
            fail_on_export_error=fail_on_export_error,
            dry_run=dry_run,
        )
        return CostUsageReportsSetupResult(
            created_exports=export_result.created_exports,
            skipped_exports=export_result.skipped_exports,
            failed_exports=export_result.failed_exports,
            bucket_status=bucket_status,
        )

    def setup_s3_bucket(
        self,
        aws_client: AWSClient,
        pm_account_id: str,
        *,
        dry_run: bool = False,
    ) -> str:
        """Create the billing exports S3 bucket if it does not exist.

        Args:
            aws_client: AWS client configured for the PM account.
            pm_account_id: Program management account ID.
            dry_run: If True, skip actual S3 API call.

        Returns:
            Bucket setup status: ``created``, ``skipped``, or ``dry_run``.

        Raises:
            AWSError: When bucket setup fails (not raised in dry-run mode).
        """
        bucket_name = S3_BILLING_EXPORT_BUCKET_TEMPLATE.format(pm_account_id=pm_account_id)
        if dry_run:
            logger.info("[DRY RUN] Would create S3 bucket: %s", bucket_name)
            return _BUCKET_STATUS_DRY_RUN

        try:
            aws_client.create_s3_bucket(bucket_name, S3_BILLING_EXPORT_REGION)
        except S3BucketAlreadyOwnedError:
            logger.info("S3 bucket: %s already exists and is owned by this account", bucket_name)
            return _BUCKET_STATUS_SKIPPED

        logger.info("S3 bucket created: %s", bucket_name)
        return _BUCKET_STATUS_CREATED

    def create_billing_exports(  # noqa: C901
        self,
        aws_client: AWSClient,
        pm_account_id: str,
        mpa_account_id: str,
        *,
        fail_on_export_error: bool = False,
        dry_run: bool = False,
    ) -> CostUsageReportsSetupResult:
        """Create missing CUR exports for billing transfer views.

        Args:
            aws_client: AWS client configured for the PM account.
            pm_account_id: Program management account ID.
            mpa_account_id: Master payer account ID.
            fail_on_export_error: Whether a single export creation error should stop processing.
            dry_run: If True, skip actual export creation calls.

        Returns:
            Result with export counters.

        Raises:
            AWSError: When listing views/exports fails, or when export creation fails and
                ``fail_on_export_error`` is True.
        """
        s3_bucket = S3_BILLING_EXPORT_BUCKET_TEMPLATE.format(pm_account_id=pm_account_id)
        s3_prefix = S3_BILLING_EXPORT_PREFIX_TEMPLATE.format(mpa_account_id=mpa_account_id)
        billing_views = aws_client.get_current_billing_view_by_account_id(mpa_account_id)
        existing_arns = (
            set()
            if dry_run
            else aws_client.list_existing_billing_exports(s3_bucket, s3_prefix)
        )

        created_count = 0
        skipped_count = 0
        failed_count = 0

        for billing_view in billing_views:
            billing_view_arn = billing_view.get("arn") or billing_view.get("billingViewArn", "")
            if not billing_view_arn:
                logger.warning(
                    "Billing view has no arn or billingViewArn, skipping: %s",
                    billing_view,
                )
                logger.debug("Billing view keys available: %s", billing_view.keys())
                continue
            if billing_view_arn in existing_arns:
                logger.debug("Billing view export already exists, skipping: %s", billing_view_arn)
                skipped_count += 1
                continue

            source_account_id = billing_view.get("sourceAccountId", mpa_account_id)
            billing_view_tail = billing_view_arn.rsplit("/", 1)[-1]
            billing_view_id = extract_billing_view_id(billing_view_arn)
            view_s3_prefix = _VIEW_S3_PREFIX_TEMPLATE.format(
                s3_prefix=s3_prefix,
                billing_view_tail=billing_view_tail,
            )
            export_name = f"{source_account_id}-{billing_view_id}"
            logger.info(
                "Creating billing export %s for view %s to s3://%s/%s",
                export_name,
                billing_view_arn,
                s3_bucket,
                view_s3_prefix,
            )
            try:
                if dry_run:
                    logger.info(
                        "[DRY RUN] Would create billing export %s for view %s to s3://%s/%s",
                        export_name,
                        billing_view_arn,
                        s3_bucket,
                        view_s3_prefix,
                    )
                else:
                    aws_client.create_billing_export(
                        billing_view_arn=billing_view_arn,
                        export_name=export_name,
                        s3_bucket=s3_bucket,
                        s3_prefix=view_s3_prefix,
                    )
            except AWSError as error:
                failed_count += 1
                if fail_on_export_error:
                    raise AWSError(
                        f"Failed to create billing export for view {billing_view_arn}: {error!s}"
                    ) from error
                logger.warning(
                    "Failed to create billing export for view %s: %s",
                    billing_view_arn,
                    error,
                )
                continue
            created_count += 1
            logger.info("Successfully created billing export %s", export_name)

        return CostUsageReportsSetupResult(
            created_exports=created_count,
            skipped_exports=skipped_count,
            failed_exports=failed_count,
        )
