from mpt_extension_sdk.mpt_http.mpt import get_agreements_by_query
from mpt_extension_sdk.runtime.tracer import dynamic_trace_span

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.constants import (
    BILLING_JOURNAL_ERROR_TITLE,
    AgreementStatusEnum,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.agreement import (
    AgreementJournalGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.invoice import InvoiceGenerator
from swo_aws_extension.flows.jobs.billing_journal.generators.usage import (
    CostExplorerUsageGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.models.context import (
    AuthorizationContext,
    BillingJournalContext,
)
from swo_aws_extension.flows.jobs.billing_journal.models.journal_result import (
    AuthorizationJournalResult,
)
from swo_aws_extension.logger import get_logger
from swo_aws_extension.swo.rql.query_builder import RQLQuery
from swo_aws_extension.utils.decorators import with_log_context

logger = get_logger(__name__)


class AuthorizationJournalGenerator:
    """Generates a billing journal for Authorizations."""

    def __init__(self, context: BillingJournalContext) -> None:
        self._context = context
        self._mpt_client = context.mpt_client
        self._config = context.config
        self._product_ids = context.product_ids
        self._billing_period = context.billing_period
        self._notifier = context.notifier

    @with_log_context(lambda _, authorization, **kwargs: authorization.get("id"))
    @dynamic_trace_span(
        lambda _, authorization, **kwargs: f"Authorization {authorization.get('id')}",
    )
    def run(self, authorization: dict) -> AuthorizationJournalResult:
        """Generate billing journal for the given authorization.

        Args:
            authorization: The authorization data to process.

        Returns:
            AuthorizationJournalResult containing lines and generated reports.
        """
        auth_id = authorization.get("id")
        pma_account = authorization.get("externalIds", {}).get("operations", "")

        logger.info(
            "Generating billing journals for %s and PMA account %s",
            auth_id,
            pma_account,
        )
        agreements = self._get_authorization_agreements(authorization)

        if not agreements:
            logger.info("No agreements found")
            return AuthorizationJournalResult()
        logger.info("Found %d agreements", len(agreements))
        aws_client = AWSClient(self._config, pma_account, self._config.billing_role_name)

        auth_context = AuthorizationContext(
            id=auth_id or "",
            pma_account=pma_account,
            currency=authorization.get("currency", ""),
        )

        return self._process_agreements(
            auth_context,
            agreements,
            CostExplorerUsageGenerator(aws_client),
            InvoiceGenerator(aws_client),
        )

    def _process_agreements(
        self,
        auth_context: AuthorizationContext,
        agreements: list[dict],
        cost_explorer_usage_generator: CostExplorerUsageGenerator,
        invoice_generator: InvoiceGenerator,
    ) -> AuthorizationJournalResult:
        result = AuthorizationJournalResult()
        generator = AgreementJournalGenerator(
            auth_context,
            self._context,
            cost_explorer_usage_generator,
            invoice_generator,
        )
        for agreement in agreements:
            agreement_id = agreement.get("id")
            try:
                agreement_result = generator.run(agreement)
            # TODO: Catch specific exceptions and handle them accordingly
            except Exception as exc:
                logger.exception(
                    "%s - Failed to synchronize agreement",
                    agreement_id,
                )
                self._notifier.send_error(
                    BILLING_JOURNAL_ERROR_TITLE,
                    f"Failed to generate billing journal for {agreement_id}: {exc}",
                )
                continue

            result.lines.extend(agreement_result.lines)
            if agreement_result.report:
                result.reports_by_agreement[agreement_id] = agreement_result.report
            if agreement_result.billing_report_rows:
                result.billing_report_rows.extend(agreement_result.billing_report_rows)

        return result

    def _get_authorization_agreements(self, authorization: dict) -> list[dict]:
        select = "&select=subscriptions,subscriptions.lines,parameters"
        rql_filter = (
            RQLQuery(authorization__id=authorization.get("id"))
            & RQLQuery(status__in=[AgreementStatusEnum.ACTIVE, AgreementStatusEnum.UPDATING])
            & RQLQuery(product__id__in=self._product_ids)
        )
        rql_query = f"{rql_filter}{select}"
        return get_agreements_by_query(self._mpt_client, rql_query)
