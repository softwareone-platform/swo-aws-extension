import io
import zipfile


class InMemoryZipBuilder:
    """
    A utility class to create an in-memory ZIP file.

    This class allows adding files to a ZIP archive and retrieving the
    resulting ZIP file as a BytesIO object.
    """
    def __init__(self):
        self._buffer = io.BytesIO()
        self._zip = zipfile.ZipFile(self._buffer, "w", zipfile.ZIP_DEFLATED)

    def write(self, filename: str, data: str):
        """Write to the zip file."""
        self._zip.writestr(filename, data)

    def get_file_content(self) -> io.BytesIO:
        """Return content."""
        self._zip.close()
        self._buffer.seek(0)
        return self._buffer
