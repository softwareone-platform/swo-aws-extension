from swo_aws_extension.management.commands_helpers import StyledPrintCommand


class DummyCommand(StyledPrintCommand):
    def handle(self, *args, **options):  # noqa: WPS110
        self.success("Happy world")
        self.info("Hello, world!")
        self.warning("Dangerous world")
        self.error("Broken world")


def test_dummy_command_messages(mocker):
    mock_stdout = mocker.Mock()
    mock_stderr = mocker.Mock()
    command = DummyCommand(
        stdout=mock_stdout,
        stderr=mock_stderr,
    )

    command.handle()

    stdout_calls = mock_stdout.write.call_args_list
    stderr_calls = mock_stderr.write.call_args_list
    assert any("Happy world" in str(call) for call in stdout_calls)
    assert any("Hello, world!" in str(call) for call in stdout_calls)
    assert any("Dangerous world" in str(call) for call in stdout_calls)
    assert any("Broken world" in str(call) for call in stderr_calls)
