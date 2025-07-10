"""
Billing Journal Generator

This module provides the BillingJournalGenerator class, which is responsible for generating
and uploading billing journals for AWS Marketplace accounts, based on agreements, subscriptions,
and usage reports. It integrates with MPT API and AWS cost reports.

Entry point: BillingJournalGenerator.generate_billing_journals()
"""

import calendar
import json
import logging
from contextlib import contextmanager
from datetime import date
from io import BytesIO

from mpt_extension_sdk.mpt_http.mpt import _paginated, get_agreements_by_query
from mpt_extension_sdk.mpt_http.utils import find_first
from swo.mpt.extensions.runtime.tracer import dynamic_trace_span

from swo_aws_extension.constants import (
    DATE_FORMAT,
    EXTERNAL_IDS,
    JOURNAL_PENDING_STATUS,
    STATUS,
    VENDOR,
    AgreementStatusEnum,
    SubscriptionStatusEnum,
)
from swo_aws_extension.notifications import send_error
from swo_mpt_api import MPTAPIClient
from swo_rql import RQLQuery

logger = logging.getLogger(__name__)


# TODO: SDK candidate
def get_authorizations(mpt_client, rql_query, limit=10):  # pragma: no cover
    """
    Retrieve authorizations based on the provided RQL query.

        Args:
            mpt_client (MPTClient): MPT API client instance.
            rql_query (RQLQuery): Query to filter authorizations.
            limit (int): Maximum number of authorizations to retrieve.
        Returns:
            list or None: List of authorizations or None if request fails.
    """
    url = (
        f"/catalog/authorizations?{rql_query}&select=externalIds,product"
        if rql_query
        else "/catalog/authorizations?select=externalIds,product"
    )
    return _paginated(mpt_client, url, limit=limit)


class BillingJournalGenerator:
    def __init__(self, mpt_client, config, year, month, product_ids, authorizations=None):
        """
        Initializes the billing journal generator with the required parameters.

        Args:
            mpt_client (MPTClient): MPT API client instance.
            config (dict): Configuration dictionary.
            year (int): Billing year.
            month (int): Billing month.
            product_ids (list): List of product IDs to process.
            authorizations (list, optional): List of authorization IDs to filter.
        """
        self.mpt_client = mpt_client
        self.config = config
        self.year = year
        self.month = month
        self.product_ids = product_ids
        self.authorizations = authorizations
        self.start_date, self.end_date = self._get_billing_period(year, month)
        self.mpt_api_client = MPTAPIClient(mpt_client)
        self.logger_context = {}

    def _log(self, level, msg):
        log_func = getattr(logger, level, logger.info)
        context_str = " ".join(str(v) for v in self.logger_context.values())
        log_func(f"{context_str} - {msg}")

    @staticmethod
    def _get_billing_period(year, month):
        """
        Returns the billing period (start and end) as date strings for a given year and month.

        Args:
        year (int): The year for the billing period.
        month (int): The month for the billing period (1-12).

        Returns:
        tuple: A tuple containing the start and end dates in "YYYY-MM-DD" format.
        """
        start_date = date(year, month, 1)
        end_date = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        return start_date.strftime(DATE_FORMAT), end_date.strftime(DATE_FORMAT)

    def _obtain_journal_id(self, authorization_id):
        """
        Gets or creates the journal ID associated with an authorization and period.

        Args:
            authorization_id (str): Authorization ID.
        Returns:
            str: Journal ID.
        """
        month_name = calendar.month_name[self.month]
        external_id = f"AWS-{self.year}-{month_name}"
        rql_query = RQLQuery(externalIds__vendor=external_id) & RQLQuery(
            authorization__id=authorization_id
        )
        journals = self.mpt_api_client.billing.journal.query(rql_query).all()
        if not journals:
            journal_payload = {
                "name": f"1 {month_name} {self.year} #1",
                "authorization": {"id": authorization_id},
                "dueDate": f"{self.year}-{self.month}-01",
                "externalIds": {"vendor": external_id},
            }
            self._log(
                "info",
                f"Creating new journal for authorization {authorization_id}: {journal_payload}",
            )
            journal = self.mpt_api_client.billing.journal.create(journal_payload)
        else:
            self._log(
                "info", f"Found {len(journals)} journals for authorization {authorization_id}"
            )
            journal = find_first(
                lambda j: j.get(STATUS) in JOURNAL_PENDING_STATUS,
                journals,
                None,
            )
            if not journal:
                journal_payload = {
                    "name": f"1 {month_name} {self.year} #{len(journals)}",
                    "authorization": {"id": authorization_id},
                    "dueDate": f"{self.year}-{self.month}-01",
                    "externalIds": {"vendor": external_id},
                }
                self._log(
                    "info",
                    f"Not found journals in {JOURNAL_PENDING_STATUS} status. Creating new journal "
                    f"for authorization {authorization_id}: {journal_payload}",
                )
                journal = self.mpt_api_client.billing.journal.create(journal_payload)
        return journal.get("id")

    def _get_authorization_agreements(self, authorization):
        """
        Retrieves agreements associated with an authorization.

        Args:
            authorization (dict): Authorization object.
        Returns:
            list: List of agreements.
        """
        select = "&select=subscriptions,subscriptions.lines"
        rql_filter = (
            RQLQuery(authorization__id=authorization.get("id"))
            & RQLQuery(status__in=[AgreementStatusEnum.ACTIVE, AgreementStatusEnum.UPDATING])
            & RQLQuery(product__id__in=self.product_ids)
        )
        rql_query = f"{rql_filter}{select}"
        return get_agreements_by_query(self.mpt_client, rql_query)

    @contextmanager
    def _temp_context(self, key, value):
        self.logger_context[key] = value
        try:
            yield
        finally:
            self.logger_context.pop(key, None)

    @dynamic_trace_span(lambda *args: f"Agreement {args[1]['id']}")
    def _generate_agreement_journal_lines(self, agreement):
        """
        Generates journal lines for an agreement, including all its active subscriptions.

        Args:
            agreement (dict): Agreement object.
        Returns:
            list: List of journal line dictionaries.
        """
        agreement_journal_lines = []
        try:
            self._log("info", f"Processing agreement {agreement.get('id')}")
            mpa_account = agreement.get(EXTERNAL_IDS, {}).get(VENDOR, "")
            if not mpa_account:
                self._log("error", f"{agreement.get('id')} - Skipping - MPA not found")
                return agreement_journal_lines

            first_active_subscription = None
            for subscription in agreement.get("subscriptions", []):
                with self._temp_context("subscription_id", subscription.get("id")):
                    if subscription.get(STATUS) == SubscriptionStatusEnum.TERMINATED:
                        continue
                    if not first_active_subscription:
                        first_active_subscription = subscription
                    agreement_journal_lines.extend(
                        self._generate_subscription_journal_lines(subscription)
                    )

            self._log("info", f"Generating journal lines for MPA account: {mpa_account}")
            # TODO Generate journal lines for the MPA account in the fist active subscription

            return agreement_journal_lines
        except Exception as exc:
            self._log(
                "exception", f"{agreement.get('id')} - Failed to synchronize agreement: {exc}"
            )
            send_error(
                "AWS Billing Journal Synchronization Error",
                f"Failed to generate billing journal for {agreement.get('id')}: {exc}",
            )
            return agreement_journal_lines

    @dynamic_trace_span(lambda *args: f"Authorization {args[1]['id']}")
    def _generate_authorization_journal(self, authorization):
        """
        Generates and uploads the billing journal for a specific authorization.

        Args:
            authorization (dict): Authorization object.
        Returns:
            None
        """
        self._log("info", f"Generating billing journals for {authorization['id']}")
        journal_file_lines = []
        journal_id = self._obtain_journal_id(authorization["id"])
        self._log("info", f"Generating journal lines for journal ID: {journal_id}")
        agreements = self._get_authorization_agreements(authorization)
        if not agreements:
            self._log("info", f"No agreements found for authorization {authorization['id']}")
            return
        self._log(
            "info", f"Found {len(agreements)} agreements for authorization {authorization['id']}"
        )

        for agreement in agreements:
            with self._temp_context("agreement_id", agreement.get("id")):
                journal_file_lines.extend(self._generate_agreement_journal_lines(agreement))

        if not journal_file_lines:
            self._log("info", f"No journal lines generated for authorization {authorization['id']}")
            return
        self._log(
            "info", f"Found {len(journal_file_lines)} journal lines for journal ID {journal_id}"
        )
        journal_file = "".join(json.dumps(entry) + "\n" for entry in journal_file_lines)
        final_file = BytesIO(journal_file.encode("utf-8"))
        self.mpt_api_client.billing.journal.upload(journal_id, final_file, "journal.jsonl")
        self._log("info", f"Uploaded journal file for journal ID {journal_id}")

    def generate_billing_journals(self):
        """
        Entry point for generating billing journals for all selected authorizations.

        Returns:
            None
        """
        self._log("info", f"Generating billing journals for {self.start_date} / {self.end_date}")
        rql_query = RQLQuery(product__id__in=self.product_ids)
        if self.authorizations:
            authorizations = list(set(self.authorizations))
            rql_query = RQLQuery(id__in=authorizations) & rql_query
        try:
            list_authorizations = get_authorizations(self.mpt_client, rql_query)
            if list_authorizations is None:
                return
            for authorization in list_authorizations:
                with self._temp_context("authorization_id", authorization.get("id")):
                    self._generate_authorization_journal(authorization)
        except Exception as exc:
            self._log("exception", f"Failed to generate billing journals: {exc}")

    @staticmethod
    def _generate_subscription_journal_lines(subscription):
        """
        Generates journal lines for a specific subscription.
        """

        # TODO Generate journal lines for the subscription
        return []
