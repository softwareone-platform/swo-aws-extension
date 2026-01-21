from abc import ABC, abstractmethod

from swo_aws_extension.flows.order import PurchaseContext


class Processor(ABC):
    """Processor interface."""

    def can_process(self, context: PurchaseContext) -> bool:
        """Check if the processor can process context."""
        return False

    @abstractmethod
    def process(self, context: PurchaseContext) -> None:
        """Process context to be implemented."""


class ProcessorChain:
    """Chain of processors will run the first one that can process context."""

    def __init__(self, processors: list[Processor]):
        self.processors = processors

    def process(self, context: PurchaseContext):
        """Process context through the chain of processors."""
        for processor in self.processors:
            if processor.can_process(context):
                processor.process(context)
                break
