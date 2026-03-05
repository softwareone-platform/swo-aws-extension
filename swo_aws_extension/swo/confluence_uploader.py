import logging
import mimetypes

import httpx


class ConfluenceUploader:
    """A utility class for uploading attachments to Confluence pages."""
    def __init__(
        self,
        base_url: str,
        page_id: str,
        username: str,
        token: str,
        logger: logging.Logger,
    ):
        self.base_url = base_url
        self.page_id = page_id
        self.username = username
        self.token = token
        self.logger = logger

    def upload(
        self,
        filename: str,
        content: bytes,
        comment: str = "",
    ) -> bool:
        """Uploads a file as an attachment to a Confluence page.

        Args:
            filename: The name of the file to upload.
            content: The binary content of the file.
            comment: An optional comment to add to the attachment.

        Returns:
            True if the upload was successful, False otherwise.
        """
        try:
            with httpx.Client(
                base_url=self.base_url.rstrip("/"),
                timeout=60.0,
                http2=True,
                auth=(self.username, self.token),
            ) as client:
                headers = {"X-Atlassian-Token": "no-check", "Accept": "application/json"}

                search_resp = client.get(
                    f"/rest/api/content/{self.page_id}/child/attachment",
                    params={"filename": filename},
                    headers=headers,
                )
                if not (200 <= search_resp.status_code < 300):
                    self.logger.warning(
                        "Confluence: failed to search existing attachment "
                        "(%s): %s",
                        search_resp.status_code,
                        search_resp.text[:200]
                    )

                attachment_id = None
                try:
                    results = search_resp.json().get("results") or []
                    if results:
                        attachment_id = results[0].get("id")
                except Exception as e:
                    self.logger.exception("Confluence: failed to parse attachment search response")

                mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
                files = {"file": (filename, content, mime_type)}

                if attachment_id:
                    url = f"/rest/api/content/{self.page_id}/child/attachment/{attachment_id}/data"
                    resp = client.post(
                        url,
                        headers=headers,
                        files=files, data={"minorEdit": "true", "comment": comment}
                    )
                    action = "updated"
                else:
                    url = f"/rest/api/content/{self.page_id}/child/attachment"
                    resp = client.post(url, headers=headers, files=files, data={"comment": comment})
                    action = "created"

            if 200 <= resp.status_code < 300:
                self.logger.info("Confluence attachment %s: %s", action, filename)
                return True

            self.logger.error(
                "Confluence upload failed (%s): %s", resp.status_code, resp.text[:300]
            )
            return False
        except Exception as e:
            self.logger.exception("Confluence upload error: %s", e)
            return False
