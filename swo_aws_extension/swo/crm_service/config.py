from dataclasses import dataclass

from django.conf import settings


class CRMConfigError(Exception):
    """Exception raised when CRM configuration is invalid or missing."""


@dataclass(frozen=True)
class CRMConfig:
    """CRM access configuration."""

    base_url: str
    oauth_url: str
    client_id: str
    client_secret: str
    audience: str

    @classmethod
    def from_settings(cls) -> "CRMConfig":
        """Create CRMConfig from settings."""
        required_keys = [
            "CRM_API_BASE_URL",
            "CRM_OAUTH_URL",
            "CRM_CLIENT_ID",
            "CRM_CLIENT_SECRET",
            "CRM_AUDIENCE",
        ]

        extension_config = getattr(settings, "EXTENSION_CONFIG", None)
        if extension_config is None:
            raise CRMConfigError("EXTENSION_CONFIG is not defined in settings")

        missing_keys = [key for key in required_keys if key not in extension_config]
        if missing_keys:
            missing_keys_str = ", ".join(missing_keys)
            raise CRMConfigError(f"Missing required CRM configuration keys: {missing_keys_str}")

        return cls(
            base_url=extension_config["CRM_API_BASE_URL"],
            oauth_url=extension_config["CRM_OAUTH_URL"],
            client_id=extension_config["CRM_CLIENT_ID"],
            client_secret=extension_config["CRM_CLIENT_SECRET"],
            audience=extension_config["CRM_AUDIENCE"],
        )
