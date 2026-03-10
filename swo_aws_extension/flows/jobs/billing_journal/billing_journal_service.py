from swo_aws_extension.constants import BILLING_JOURNAL_ERROR_TITLE
from swo_aws_extension.flows.jobs.billing_journal.generators.authorization import (
    AuthorizationJournalGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.models.context import BillingJournalContext
from swo_aws_extension.logger import get_logger
from swo_aws_extension.swo.mpt.authorization import get_authorizations
from swo_aws_extension.swo.rql.query_builder import RQLQuery

logger = get_logger(__name__)


class BillingJournalService:
    """Generate billing journals for authorizations."""

    def __init__(self, job_context: BillingJournalContext) -> None:
        self._context = job_context
        self._mpt_client = job_context.mpt_client
        self._product_ids = job_context.product_ids
        self._authorizations = job_context.authorizations
        self._notifier = job_context.notifier

    def run(self) -> None:
        """Entry point for generating billing journals for all selected authorizations."""
        logger.info(
            "Generating billing journals for %s",
            self._context.billing_period,
        )

        authorizations = get_authorizations(self._mpt_client, self._build_rql_query())
        if not authorizations:
            logger.info("No authorizations found")
            return

        generator = AuthorizationJournalGenerator(self._context)
        for authorization in authorizations:
            authorization_id = authorization.get("id")
            try:
                # TODO: Handle journal with the generated lines
                generator.run(authorization)
            # TODO: Catch specific exceptions and handle them accordingly
            except Exception:
                logger.exception(
                    "Failed to generate billing journals for authorization %s",
                    authorization_id,
                )
                self._notifier.send_error(
                    BILLING_JOURNAL_ERROR_TITLE,
                    f"Failed to generate billing journals for authorization {authorization_id}",
                )

    def _build_rql_query(self) -> RQLQuery:
        rql_query = RQLQuery(product__id__in=self._product_ids)
        if self._authorizations:
            unique_ids = list(set(self._authorizations))
            rql_query = RQLQuery(id__in=unique_ids) & rql_query
        return rql_query
