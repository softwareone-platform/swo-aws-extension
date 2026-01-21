from unittest.mock import MagicMock

from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.processors.processor import Processor, ProcessorChain


class ConcreteProcessor(Processor):
    def process(self, context: PurchaseContext) -> None: ...


def test_processor_can_process_default() -> None:
    processor = ConcreteProcessor()
    context = MagicMock(spec=PurchaseContext)

    result = processor.can_process(context)

    assert result is False


def test_processor_chain() -> None:
    mock_processor = MagicMock(spec=Processor)
    mock_processor.can_process.return_value = True
    context = MagicMock(spec=PurchaseContext)
    chain = ProcessorChain([mock_processor])

    chain.process(context)  # act

    mock_processor.can_process.assert_called_once_with(context)
    mock_processor.process.assert_called_once_with(context)


def test_processor_chain_stops_after_first_match() -> None:
    mock_processor1 = MagicMock(spec=Processor)
    mock_processor1.can_process.return_value = True
    mock_processor2 = MagicMock(spec=Processor)
    mock_processor2.can_process.return_value = True
    context = MagicMock(spec=PurchaseContext)
    chain = ProcessorChain([mock_processor1, mock_processor2])

    chain.process(context)  # act

    mock_processor1.can_process.assert_called_once_with(context)
    mock_processor1.process.assert_called_once_with(context)
    mock_processor2.can_process.assert_not_called()
    mock_processor2.process.assert_not_called()


def test_processor_chain_skips_until_match() -> None:
    mock_processor1 = MagicMock(spec=Processor)
    mock_processor1.can_process.return_value = False
    mock_processor2 = MagicMock(spec=Processor)
    mock_processor2.can_process.return_value = True
    context = MagicMock(spec=PurchaseContext)
    chain = ProcessorChain([mock_processor1, mock_processor2])

    chain.process(context)  # act

    mock_processor1.can_process.assert_called_once_with(context)
    mock_processor1.process.assert_not_called()
    mock_processor2.can_process.assert_called_once_with(context)
    mock_processor2.process.assert_called_once_with(context)
