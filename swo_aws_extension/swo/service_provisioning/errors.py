class ServiceProvisioningError(Exception):
    """Base exception for Service Provisioning client errors."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.status_code:
            return f"ServiceProvisioningError ({self.status_code}): {self.message}"
        return f"ServiceProvisioningError: {self.message}"


class ServiceProvisioningHttpError(ServiceProvisioningError):
    """HTTP error from Service Provisioning API."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message, status_code)
