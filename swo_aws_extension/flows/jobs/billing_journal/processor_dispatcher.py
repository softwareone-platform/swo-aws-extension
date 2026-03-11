from typing import Any, Self

from swo_aws_extension.config import Config
from swo_aws_extension.flows.jobs.billing_journal.models.billing_period import BillingPeriod


class JournalProcessorDispatcher:
    """Dispatcher for journal line processors based on itemSku."""

    def __init__(self, processors: list[Any]) -> None:
        """Initialize the dispatcher with processors.

        Args:
            processors: List of journal processors.
        """
        self._processors = processors

    @classmethod
    def build(cls, config: Config) -> "JournalProcessorDispatcher":
        """Build a dispatcher using the provided config.

        Args:
            config: Configuration object.

        Returns:
            Configured JournalProcessorDispatcher instance.
        """
        processors = cls._create_processors(config)
        return cls(processors)

    @classmethod
    def build_with_params(
        cls,
        config: Config,
        job_parameters: list[dict],
    ) -> Self:
        """Build a dispatcher using config and agreement parameters.

        Args:
            config: Configuration object.
            job_parameters: Agreement-specific parameters.

        Returns:
            Configured JournalProcessorDispatcher instance.
        """
        # TODO: Implement processor creation based on config and parameters
        processors = []
        return cls(processors)

    def process_all(self, agreement: dict, billing_period: BillingPeriod) -> list[dict]:
        """Process agreement with all configured processors.

        Args:
            agreement: The agreement data to process.
            billing_period: The billing period with start and end dates.

        Returns:
            Aggregated list of journal lines from all processors.
        """
        return [
            line
            for processor in self._processors
            for line in processor.process(agreement, billing_period)
        ]

    @property
    def has_processors(self) -> bool:
        """Check if there are any processors configured."""
        return bool(self._processors)

    @classmethod
    def _create_processors(cls, config: Config) -> list[Any]:
        # TODO: Implement processor creation based on config
        return []
