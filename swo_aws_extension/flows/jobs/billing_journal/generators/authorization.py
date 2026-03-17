from collections.abc import Callable
from typing import Any, cast

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
from swo_aws_extension.flows.jobs.billing_journal.models.context import BillingJournalContext
from swo_aws_extension.flows.jobs.billing_journal.models.journal_result import (
    AuthorizationJournalResult,
)
from swo_aws_extension.logger import get_logger
from swo_aws_extension.swo.rql.query_builder import RQLQuery
from swo_aws_extension.utils.decorators import with_log_context

logger = get_logger(__name__)

type AuthorizationData = dict[str, Any]
type AgreementData = dict[str, Any]
type TraceDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]

authorization_trace_span = cast(
    TraceDecorator,
    dynamic_trace_span(
        lambda _, authorization, **kwargs: f"Authorization {authorization.get('id')}",
    ),
)


class AuthorizationJournalGenerator:
    """Generates a billing journal for authorizations."""

    def __init__(self, context: BillingJournalContext) -> None:
        self._context = context
        self._mpt_client = context.mpt_client
        self._config = context.config
        self._product_ids = context.product_ids
        self._billing_period = context.billing_period
        self._notifier = context.notifier

    @with_log_context(lambda _, authorization, **kwargs: authorization.get("id"))
    @authorization_trace_span
    def run(self, authorization: AuthorizationData) -> AuthorizationJournalResult:
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
        aws_client = AWSClient(self._config, pma_account, self._config.management_role_name)
        return self._process_agreements(agreements, authorization.get("currency", ""), aws_client)

    def _process_agreements(
        self,
        agreements: list[AgreementData],
        auth_currency: str,
        aws_client: AWSClient,
    ) -> AuthorizationJournalResult:
        result = AuthorizationJournalResult()
        generator = AgreementJournalGenerator(
            auth_currency,
            self._context,
            aws_client,
            aws_client.account_id,
        )
        for agreement in agreements:
            agreement_id_raw = agreement.get("id", "")
            agreement_id: str
            if isinstance(agreement_id_raw, str):
                agreement_id = agreement_id_raw
            else:
                agreement_id = ""
            try:
                agreement_result = generator.run(agreement)
            except Exception as exc:
                logger.exception(
                    "%s - Failed to generate billing journal for agreement",
                    agreement_id,
                )
                self._notifier.send_error(
                    BILLING_JOURNAL_ERROR_TITLE,
                    f"Failed to generate billing journal for {agreement_id}: {exc}",
                )
                continue

            logger.info("Generated %d journal lines", len(agreement_result.lines))
            result.lines.extend(agreement_result.lines)
            report = agreement_result.report
            if report is not None and agreement_id:
                result.reports_by_agreement[agreement_id] = report

        return result

    def _get_authorization_agreements(
        self, authorization: AuthorizationData
    ) -> list[AgreementData]:
        select = "&select=subscriptions,subscriptions.lines,parameters"
        rql_filter = (
            RQLQuery(authorization__id=authorization.get("id"))  # type: ignore[no-untyped-call]
            & RQLQuery(status__in=[AgreementStatusEnum.ACTIVE, AgreementStatusEnum.UPDATING])  # type: ignore[no-untyped-call]
            & RQLQuery(product__id__in=self._product_ids)  # type: ignore[no-untyped-call]
        )
        rql_query = f"{rql_filter}{select}"
        return cast(list[AgreementData], get_agreements_by_query(self._mpt_client, rql_query))
