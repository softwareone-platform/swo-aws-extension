import logging

import requests
from atlassian import Confluence

from swo_aws_extension.config import Config
from swo_aws_extension.constants import EXCEL_MIME_TYPE

logger = logging.getLogger(__name__)


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
            self._client.attach_content(
                content=file_content,
                name=filename,
                content_type=EXCEL_MIME_TYPE,
                page_id=page_id,
                comment=comment,
            )
        except requests.exceptions.HTTPError:
            logger.exception("Confluence HTTP error")
            return False
        except requests.exceptions.RequestException:
            logger.exception("Confluence request error")
            return False
        else:
            logger.info("File %s attached to Confluence page %s", filename, page_id)
            return True

    @property
    def _client(self) -> Confluence:
        return Confluence(
            url=self.config.confluence_base_url,
            username=self.config.confluence_user,
            password=self.config.confluence_token,
            cloud=True,
        )
