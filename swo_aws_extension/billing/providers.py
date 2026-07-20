from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.config import Config


class BillingAWSClientProvider:
    """Lazily create and reuse the billing AWS client for one authorization."""

    def __init__(self, config: Config, pma_account: str) -> None:
        self._config = config
        self._pma_account = pma_account
        self._client: AWSClient | None = None

    def __call__(self) -> AWSClient:
        """Return the cached billing AWS client."""
        if self._client is None:
            self._client = AWSClient(
                self._config,
                self._pma_account,
                self._config.billing_role_name,
            )
        return self._client
