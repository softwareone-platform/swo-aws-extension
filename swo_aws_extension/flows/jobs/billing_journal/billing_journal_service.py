from collections import defaultdict
from decimal import Decimal

from swo_aws_extension.constants import BILLING_JOURNAL_ERROR_TITLE
from swo_aws_extension.flows.jobs.billing_journal.billing_report_creator import (
    BillingReportCreator,
)
from swo_aws_extension.flows.jobs.billing_journal.generators.authorization import (
    AuthorizationJournalGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.journal_manager import JournalManager
from swo_aws_extension.flows.jobs.billing_journal.models.context import BillingJournalContext
from swo_aws_extension.flows.jobs.billing_journal.models.journal_line import JournalLine
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
        if self._context.dry_run:
            logger.info(
                "Starting execution in DRY-RUN mode. No journals will be created or uploaded."
            )

        logger.info(
            "Generating billing journals for %s",
            self._context.billing_period,
        )

        authorizations = get_authorizations(self._mpt_client, self._build_rql_query())
        if not authorizations:
            logger.info("No authorizations found")
            return

        all_report_rows = []
        for authorization in authorizations:
            generator_result = self._process_authorization(authorization)
            if generator_result and generator_result.billing_report_rows:
                all_report_rows.extend(generator_result.billing_report_rows)

        if all_report_rows and not self._context.dry_run:
            report_creator = BillingReportCreator(self._context.config, self._context.notifier)
            report_creator.create_and_notify_teams(
                str(self._context.billing_period), all_report_rows
            )

    def _process_authorization(self, authorization: dict) -> AuthorizationJournalResult | None:
        authorization_id = authorization.get("id")

        generator_result = self._generate_journal_lines(authorization, authorization_id)
        if not generator_result or not generator_result.lines:
            logger.info(
                "No journal lines generated for authorization %s",
                authorization_id,
            )
            return None

        logger.info(
            "Generated %d journal lines for authorization %s",
            len(generator_result.lines),
            authorization_id,
        )

        if self._context.dry_run:
            self._log_dry_run_results(authorization_id, generator_result)
            return None

        journal_manager = JournalManager(self._context, authorization_id)

        journal = journal_manager.get_pending_journal()
        if not journal:
            journal = journal_manager.create_new_journal()
            logger.info("Created new journal: %s", journal.name)

        journal_manager.upload_journal(journal.id, generator_result.lines)
        if generator_result.reports_by_agreement:
            journal_manager.upload_attachments(
                journal.id,
                generator_result.reports_by_agreement,
            )
        journal_manager.notify_success(journal.id, len(generator_result.lines))

        return generator_result

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

    def _log_dry_run_results(
        self, authorization_id: str, generator_result: AuthorizationJournalResult
    ) -> None:
        logger.info(
            "[DRY-RUN] Generated %d journal lines for authorization %s",
            len(generator_result.lines),
            authorization_id,
        )
        logger.info("".join(entry.to_jsonl() for entry in generator_result.lines))
        self._log_totals_by_mpa(generator_result.lines)

        attachments = [
            f"{agr}.json"
            for agr, rep in generator_result.reports_by_agreement.items()
            if rep.organization_data or rep.accounts_data
        ]
        if attachments:
            logger.info("[DRY-RUN] Attachments: %s", attachments)

    def _log_totals_by_mpa(self, journal_lines: list[JournalLine]) -> None:
        total_by_mpa: dict[str, Decimal] = defaultdict(Decimal)
        for line in journal_lines:
            total_by_mpa[line.external_ids.vendor] += line.price.pp_x1

        for mpa, total_amount in total_by_mpa.items():
            logger.info(
                "[DRY-RUN] MPA %s total amount: %s",
                mpa,
                total_amount,
            )
