from swo_aws_extension.logger import (
    ContextLogger,
    clear_log_context,
    get_logger,
    set_log_context,
)


def test_get_logger_returns_context_logger():
    result = get_logger("test.module")

    assert isinstance(result, ContextLogger)


def test_process_without_context_returns_original_message(mocker):
    mock_ctx = mocker.patch("swo_aws_extension.logger._log_context")
    mock_ctx.get.return_value = None
    logger = get_logger("test.no_context")

    result = logger.process("hello world", {})

    msg, kwargs = result
    assert msg == "hello world"
    assert kwargs == {}


def test_process_with_context_prepends_values(mocker):
    mock_ctx = mocker.patch("swo_aws_extension.logger._log_context")
    mock_ctx.get.return_value = ["AUTH-1"]
    logger = get_logger("test.with_context")

    result = logger.process("hello world", {})

    msg, _ = result
    assert msg == "AUTH-1 - hello world"


def test_process_with_multiple_context_values(mocker):
    mock_ctx = mocker.patch("swo_aws_extension.logger._log_context")
    mock_ctx.get.return_value = ["AUTH-1", "AGR-2"]
    logger = get_logger("test.multi_context")

    result = logger.process("hello world", {})

    msg, _ = result
    assert "AUTH-1" in msg
    assert "AGR-2" in msg
    assert msg.endswith("- hello world")


def test_set_log_context_adds_values(mocker):
    mock_ctx = mocker.patch("swo_aws_extension.logger._log_context")
    mock_ctx.get.return_value = ["val1"]

    result = set_log_context("val2")

    mock_ctx.set.assert_called_once_with(["val1", "val2"])
    assert result is None


def test_clear_log_context_removes_values(mocker):
    mock_ctx = mocker.patch("swo_aws_extension.logger._log_context")
    mock_ctx.get.return_value = ["val1", "val2"]

    result = clear_log_context("val1")

    mock_ctx.set.assert_called_once_with(["val2"])
    assert result is None


def test_clear_log_context_ignores_missing_values(mocker):
    mock_ctx = mocker.patch("swo_aws_extension.logger._log_context")
    mock_ctx.get.return_value = ["val1"]

    result = clear_log_context("nonexistent")

    mock_ctx.set.assert_called_once_with(["val1"])
    assert result is None
