import datetime as dt
from unittest.mock import MagicMock

import pytest

from swo_aws_extension.constants import OrderProcessingTemplateEnum
from swo_aws_extension.flows.order import PurchaseContext
from swo_aws_extension.processors.querying.helper import get_template_name, is_querying_timeout


@pytest.fixture
def mock_context() -> MagicMock:
    return MagicMock(spec=PurchaseContext)


def test_get_template_name_new_aws_environment(mock_context: MagicMock) -> None:
    mock_context.is_type_new_aws_environment.return_value = True

    result = get_template_name(mock_context)

    assert result == OrderProcessingTemplateEnum.NEW_ACCOUNT
    mock_context.is_type_new_aws_environment.assert_called_once()


def test_get_template_name_existing_account(mock_context: MagicMock) -> None:
    mock_context.is_type_new_aws_environment.return_value = False

    result = get_template_name(mock_context)

    assert result == OrderProcessingTemplateEnum.EXISTING_ACCOUNT
    mock_context.is_type_new_aws_environment.assert_called_once()


def test_is_querying_timeout_no_audit(mock_context: MagicMock) -> None:
    mock_context.order = {}

    result = is_querying_timeout(mock_context, querying_timeout_days=4)

    assert result is False


def test_is_querying_timeout_no_querying_at(mock_context: MagicMock) -> None:
    mock_context.order = {"audit": {}}

    result = is_querying_timeout(mock_context, querying_timeout_days=4)

    assert result is False


def test_is_querying_timeout_not_reached(mock_context: MagicMock) -> None:
    now = dt.datetime.now(dt.UTC)
    querying_at = (now - dt.timedelta(days=3)).isoformat()
    mock_context.order = {"audit": {"querying": {"at": querying_at}}}

    result = is_querying_timeout(mock_context, querying_timeout_days=4)

    assert result is False


def test_is_querying_timeout_reached(mock_context: MagicMock) -> None:
    now = dt.datetime.now(dt.UTC)
    querying_at = (now - dt.timedelta(days=5)).isoformat()
    mock_context.order = {"audit": {"querying": {"at": querying_at}}}

    result = is_querying_timeout(mock_context, querying_timeout_days=4)

    assert result is True
