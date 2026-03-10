from mpt_extension_sdk.runtime.tracer import dynamic_trace_span

from swo_aws_extension.flows.jobs.billing_journal.models.context import BillingJournalContext
from swo_aws_extension.flows.jobs.billing_journal.processor_dispatcher import (
    JournalProcessorDispatcher,
)
from swo_aws_extension.logger import get_logger
from swo_aws_extension.utils.decorators import with_log_context

logger = get_logger(__name__)


class AgreementJournalGenerator:
    """Generates journal lines and attachments for Agreements."""

    def __init__(
        self,
        authorization_currency: str,
        context: BillingJournalContext,
    ) -> None:
        self._authorization_currency = authorization_currency
        self._config = context.config
        self._mpt_api_client = context.mpt_client
        self._billing_period = context.billing_period

    @with_log_context(lambda _, agreement, **kwargs: agreement.get("id"))
    @dynamic_trace_span(lambda _, agreement, **kwargs: f"Agreement {agreement.get('id')}")
    def run(self, agreement: dict) -> list[dict]:
        """Generate journal lines for the given agreement.

        Args:
            agreement: The agreement data to process.

        Returns:
            List of journal line dictionaries.
        """
        mpa_account = agreement.get("externalIds", {}).get("vendor", "")
        logger.info("Generating journal lines for account: %s", mpa_account)
        discount_params: list = []
        dispatcher = JournalProcessorDispatcher.build_with_params(self._config, discount_params)
        return dispatcher.process_all(agreement, self._billing_period)
