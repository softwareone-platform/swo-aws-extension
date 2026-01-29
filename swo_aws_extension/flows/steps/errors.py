from mpt_extension_sdk.mpt_http.wrap_http_error import ValidationError


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

    def __init__(self, title: str, message: str) -> None:
        self.message = message
        self.title = title
        super().__init__(message)


class FailStepError(Exception):
    """The step has failed and cannot proceed."""

    def __init__(self, message_id: str, message: str) -> None:
        self.id = message_id
        self.message = message
        super().__init__(message)


class QueryStepError(Exception):
    """The step cannot proceed and requires querying."""

    def __init__(self, message: str, template_id=None) -> None:
        self.message = message
        self.template_id = template_id
        super().__init__(message)


ERR_CREATING_INVITATION_RESPONSE = ValidationError(
    "AWS001",
    "Error creating billing transfer invitation for account {mpa_id} with error: {error}."
    " Kindly provide a valid Account ID.",
)

ERR_MISSING_MPA_ID = ValidationError(
    "AWS002",
    "Account id is empty. Please provide an account id.",
)


class OrderStatusChangeError(RuntimeError):
    """Exception raised when the order status cannot be changed."""

    def __init__(self, target_status, current_status):
        message = (
            f"Order is already in `{current_status}` status. "
            f"Unable to switch and order to `{target_status}` "
            f"when it is in `{current_status}` status."
        )
        super().__init__(message)
