class UnexpectedStopError(Exception):
    """The step should send a notification error."""

    def __init__(self, title: str, message: str) -> None:
        self.message = message
        self.title = title
        super().__init__(message)


class AlreadyProcessedStepError(Exception):
    """The step has already been processed."""


class SkipStepError(Exception):
    """The step should be skipped."""


class ConfigurationStepError(Exception):
    """The step cannot proceed due to configuration issues."""
