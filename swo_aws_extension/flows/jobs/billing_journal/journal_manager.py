import calendar
from io import BytesIO
from urllib.parse import urljoin

from swo_aws_extension.constants import BILLING_JOURNAL_SUCCESS_TITLE
from swo_aws_extension.flows.jobs.billing_journal.models.context import BillingJournalContext
from swo_aws_extension.flows.jobs.billing_journal.models.journal import Journal
from swo_aws_extension.logger import get_logger
from swo_aws_extension.swo.notifications.teams import Button
from swo_aws_extension.swo.rql.query_builder import RQLQuery

logger = get_logger(__name__)


class JournalManager:  # noqa: WPS214
    """Manages the creation, retrieval and upload of billing journals via MPT API."""

    def __init__(
        self,
        context: BillingJournalContext,
        authorization_id: str,
    ) -> None:
        self._context = context
        self._billing_api_client = context.billing_api_client
        self._authorization_id = authorization_id
        self._billing_period = context.billing_period
        self._config = context.config
        self._notifier = context.notifier

    def get_pending_journal(self) -> Journal | None:
        """Obtain an existing pending journal or return None."""
        external_id = self._build_external_id()
        journal = self._query_pending_journal(external_id)
        if journal:
            logger.info("Found pending journal for %s: %s", self._authorization_id, journal.name)
        return journal

    def create_new_journal(self) -> Journal:
        """Create a new journal for the current billing period."""
        external_id = self._build_external_id()
        total_journals = self._query_count_journals(external_id)
        index = total_journals + 1

        journal_payload = {
            "name": self._build_journal_name(index),
            "authorization": {"id": self._authorization_id},
            "dueDate": self._billing_period.start_date,
            "externalIds": {"vendor": external_id},
        }
        return Journal.from_dict(
            self._billing_api_client.journal.create(journal_payload),
        )

    def upload_journal(self, journal_id: str, journal_file_lines: list) -> None:
        """Upload the journal lines as a file to the MPT API."""
        journal_file = "".join(entry.to_jsonl() for entry in journal_file_lines)
        final_file = BytesIO(journal_file.encode("utf-8"))

        self._billing_api_client.journal.upload(journal_id, final_file, "journal.jsonl")

        logger.info(
            "Uploaded journal file for journal ID %s with %d lines",
            journal_id,
            len(journal_file_lines),
        )

        journal_link = urljoin(
            self._config.mpt_portal_base_url,
            f"/billing/journals/{journal_id}",
        )
        self._notifier.send_success(
            BILLING_JOURNAL_SUCCESS_TITLE,
            f"Billing journal {journal_id} uploaded for {self._authorization_id} "
            f"with {len(journal_file_lines)} lines.",
            button=Button(f"Open journal {journal_id}", journal_link),
        )

    def _build_external_id(self) -> str:
        year = self._billing_period.year
        month_name = calendar.month_name[self._billing_period.month]
        return f"AWS-{year}-{month_name}"

    def _build_journal_name(self, index: int) -> str:
        year = self._billing_period.year
        month_name = calendar.month_name[self._billing_period.month]
        return f"1 {month_name} {year} #{index}"

    def _query_pending_journal(self, external_id: str) -> Journal | None:
        rql_query = (
            RQLQuery(externalIds__vendor=external_id)
            & RQLQuery(authorization__id=self._authorization_id)
            & RQLQuery(status__in=["Error", "Draft", "Validated"])
        )
        journals_raw = self._billing_api_client.journal.query(rql_query).page(limit=1)
        return Journal.from_dict(journals_raw["data"][0]) if journals_raw["data"] else None

    def _query_count_journals(self, external_id: str) -> int:
        rql_query = RQLQuery(externalIds__vendor=external_id) & RQLQuery(
            authorization__id=self._authorization_id
        )
        journals_raw = self._billing_api_client.journal.query(rql_query).page(limit=0)
        return journals_raw["$meta"]["pagination"]["total"]
