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
from swo_aws_extension.flows.jobs.billing_journal.generators.usage import (
    CostExplorerUsageGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.models.context import BillingJournalContext
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
    def run(self, authorization: dict) -> list[dict]:
        """Generate billing journal for the given authorization.

        Args:
            authorization: The authorization data to process.

        Returns:
            List of journal line dictionaries.
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
            return []
        logger.info("Found %d agreements", len(agreements))
        cost_explorer_usage_generator = CostExplorerUsageGenerator(
            AWSClient(self._config, pma_account, self._config.management_role_name)
        )
        return self._process_agreements(
            agreements, authorization.get("currency", ""), cost_explorer_usage_generator
        )

    def _process_agreements(
        self,
        agreements: list[dict],
        auth_currency: str,
        cost_explorer_usage_generator: CostExplorerUsageGenerator,
    ) -> list[dict]:
        journal_file_lines: list[dict] = []
        generator = AgreementJournalGenerator(
            auth_currency,
            self._context,
            cost_explorer_usage_generator,
        )
        for agreement in agreements:
            agreement_id = agreement.get("id")
            try:
                lines = generator.run(agreement)
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
            journal_file_lines.extend(lines)
        return journal_file_lines

    def _get_authorization_agreements(self, authorization: dict) -> list[dict]:
        select = "&select=subscriptions,subscriptions.lines,parameters"
        rql_filter = (
            RQLQuery(authorization__id=authorization.get("id"))
            & RQLQuery(status__in=[AgreementStatusEnum.ACTIVE, AgreementStatusEnum.UPDATING])
            & RQLQuery(product__id__in=self._product_ids)
        )
        rql_query = f"{rql_filter}{select}"
        return get_agreements_by_query(self._mpt_client, rql_query)
