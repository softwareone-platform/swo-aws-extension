from swo_aws_extension.constants import BILLING_JOURNAL_ERROR_TITLE
from swo_aws_extension.flows.jobs.billing_journal.generators.authorization import (
    AuthorizationJournalGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.journal_manager import JournalManager
from swo_aws_extension.flows.jobs.billing_journal.models.context import BillingJournalContext
from swo_aws_extension.flows.jobs.billing_journal.models.journal_result import (
    AuthorizationJournalResult,
)
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
        self._generator = AuthorizationJournalGenerator(job_context)

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

        for authorization in authorizations:
            self._process_authorization(authorization)

    def _process_authorization(self, authorization: dict) -> None:
        authorization_id = authorization.get("id")
        journal_manager = JournalManager(self._context, authorization_id)

        journal = journal_manager.get_pending_journal()
        if not journal:
            journal = journal_manager.create_new_journal()
            logger.info("Created new journal: %s", journal.name)

        generator_result = self._generate_journal_lines(authorization, authorization_id)
        if not generator_result:
            return

        logger.info(
            "Generated %d journal lines for authorization %s",
            len(generator_result.lines),
            authorization_id,
        )
        if generator_result.lines:
            journal_manager.upload_journal(journal.id, generator_result.lines)
            if generator_result.reports_by_agreement:
                journal_manager.upload_attachments(
                    journal.id,
                    generator_result.reports_by_agreement,
                )
            journal_manager.notify_success(journal.id, len(generator_result.lines))
        else:
            logger.info(
                "No journal lines generated for authorization %s. Skipping upload.",
                authorization_id,
            )

    def _generate_journal_lines(
        self, authorization: dict, authorization_id: str
    ) -> AuthorizationJournalResult | None:
        try:
            return self._generator.run(authorization)
        except Exception:  # TODO: Catch specific exceptions and handle them accordingly
            logger.exception(
                "Failed to generate billing journals for authorization %s",
                authorization_id,
            )
            self._notifier.send_error(
                BILLING_JOURNAL_ERROR_TITLE,
                f"Failed to generate billing journals for authorization {authorization_id}",
            )
            return None

    def _build_rql_query(self) -> RQLQuery:
        rql_query = RQLQuery(product__id__in=self._product_ids)
        if self._authorizations:
            unique_ids = list(set(self._authorizations))
            rql_query = RQLQuery(id__in=unique_ids) & rql_query
        return rql_query
