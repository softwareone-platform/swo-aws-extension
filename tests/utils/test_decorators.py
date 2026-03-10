import pytest

from swo_aws_extension.utils.decorators import with_log_context


class _FakeService:
    @with_log_context(lambda _, entity, **kwargs: entity.get("id"))
    def run(self, entity: dict) -> str:
        return "ok"


class _FailingService:
    @with_log_context(lambda _, entity, **kwargs: entity.get("id"))
    def run(self, entity: dict) -> None:
        raise ValueError("fail")


@pytest.fixture
def mock_set_log_context(mocker):
    return mocker.patch("swo_aws_extension.utils.decorators.set_log_context")


@pytest.fixture
def mock_clear_log_context(mocker):
    return mocker.patch("swo_aws_extension.utils.decorators.clear_log_context")


def test_with_log_context_sets_context_during_call(
    mock_set_log_context,
    mock_clear_log_context,
):
    service = _FakeService()

    result = service.run({"id": "ENT-123"})

    assert result == "ok"
    mock_set_log_context.assert_called_once_with("ENT-123")
    mock_clear_log_context.assert_called_once_with("ENT-123")


def test_with_log_context_clears_context_on_exception(
    mock_set_log_context,
    mock_clear_log_context,
):
    service = _FailingService()

    with pytest.raises(ValueError, match="fail"):
        result = service.run({"id": "ENT-456"})  # noqa: F841

    mock_set_log_context.assert_called_once_with("ENT-456")
    mock_clear_log_context.assert_called_once_with("ENT-456")


def test_with_log_context_handles_missing_id(
    mock_set_log_context,
    mock_clear_log_context,
):
    service = _FakeService()

    result = service.run({})

    assert result == "ok"
    mock_set_log_context.assert_not_called()
    mock_clear_log_context.assert_not_called()
