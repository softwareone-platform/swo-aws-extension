import io
import zipfile


class InMemoryZipBuilder:
    """A utility class to create an in-memory ZIP file.
    This class allows adding files to a ZIP archive and retrieving the
    resulting ZIP file as a BytesIO object."""

    def __init__(self):
        self._buffer = io.BytesIO()
        self._zip = zipfile.ZipFile(self._buffer, "w", zipfile.ZIP_DEFLATED)

    def write(self, filename: str, data: str):
        self._zip.writestr(filename, data)

    def get_file(self) -> io.BytesIO:
        self._zip.close()
        self._buffer.seek(0)
        return self._buffer
