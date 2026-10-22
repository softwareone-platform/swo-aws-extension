"""Cloud Orchestrator client errors."""

from http import HTTPStatus


class CloudOrchestratorError(Exception):
    """Base exception for Cloud Orchestrator client errors."""


class CloudOrchestratorHttpError(CloudOrchestratorError):
    """HTTP error from Cloud Orchestrator API."""

    def __init__(self, status_code: int, response_content: str):
        self.status_code = status_code
        self.response_content = response_content
        super().__init__(f"{self.status_code} - {self.response_content}")


class CloudOrchestratorNotFoundError(CloudOrchestratorHttpError):
    """Resource not found error (404)."""

    def __init__(self, response_content: str):
        super().__init__(HTTPStatus.NOT_FOUND, response_content)


class CloudOrchestratorMissingScuError(CloudOrchestratorError):
    """The buyer has no SCU, so no Cloud Orchestrator request can be sent."""

    def __init__(self, order_id: str, master_payer_id: str, buyer_id: str):
        super().__init__(
            f"Buyer SCU is not set for order {order_id} (MPA {master_payer_id}, buyer {buyer_id})"
        )
