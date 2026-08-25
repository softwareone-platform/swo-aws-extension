import logging

import requests
from atlassian import Confluence

from swo_aws_extension.config import Config
from swo_aws_extension.constants import EXCEL_MIME_TYPE

logger = logging.getLogger(__name__)

# atlassian-python-api 5.x dropped the high-level ``Confluence.attach_content`` helper and
# offers no replacement for uploading a file to Confluence Cloud, so the v1 REST attachment
# endpoint is called directly through the client's transport layer.
ATTACHMENT_PATH_TEMPLATE = "rest/api/content/{page_id}/child/attachment"


def _attachment_headers() -> dict[str, str]:
    return {"X-Atlassian-Token": "no-check", "Accept": "application/json"}


class ConfluenceClient:
    """Client for interacting with Confluence."""

    def __init__(self, config: Config):
        self.config = config

    def attach_content(
        self,
        page_id: str,
        filename: str,
        file_content: bytes,
        comment: str = "",
    ) -> bool:
        """Uploads a file as an attachment to a Confluence page.

        Args:
            page_id: The ID of the Confluence page to attach the file to.
            filename: The name of the file to upload.
            file_content: The binary content of the file.
            comment: An optional comment to add to the attachment.

        Returns:
            True if the upload was successful, False otherwise.
        """
        try:
            self._upload_attachment(page_id, filename, file_content, comment)
        except requests.exceptions.HTTPError:
            logger.exception("Confluence HTTP error")
            return False
        except requests.exceptions.RequestException:
            logger.exception("Confluence request error")
            return False
        else:
            logger.info("File %s attached to Confluence page %s", filename, page_id)
            return True

    def _upload_attachment(
        self,
        page_id: str,
        filename: str,
        file_content: bytes,
        comment: str,
    ) -> None:
        client = self._client
        client.post(
            path=self._resolve_upload_path(client, page_id, filename),
            data={
                "type": "attachment",
                "fileName": filename,
                "contentType": EXCEL_MIME_TYPE,
                "comment": comment or f"Uploaded {filename}.",
                "minorEdit": "true",
            },
            headers=_attachment_headers(),
            files={"file": (filename, file_content, EXCEL_MIME_TYPE)},
        )

    def _resolve_upload_path(self, client: Confluence, page_id: str, filename: str) -> str:
        """Point the upload at the existing attachment so a rerun adds a version, not a copy."""
        base_path = ATTACHMENT_PATH_TEMPLATE.format(page_id=page_id)
        attachments = client.get(
            path=base_path,
            headers=_attachment_headers(),
            params={"filename": filename},
        )
        matches = (attachments or {}).get("results") or []
        if not matches:
            return base_path
        attachment_id = matches[0]["id"]
        return f"{base_path}/{attachment_id}/data"

    @property
    def _client(self) -> Confluence:
        return Confluence(
            url=self.config.confluence_base_url,
            username=self.config.confluence_user,
            password=self.config.confluence_token,
            cloud=True,
        )
