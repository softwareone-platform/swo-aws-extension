import zipfile

from swo_aws_extension.file_builder.zip_builder import InMemoryZipBuilder


def test_in_memory_zip_builder_add_and_get_zip():
    builder = InMemoryZipBuilder()
    builder.write("report1.jsonl", '{"account1": "value1"}')
    builder.write("report2.jsonl", '{"account2": "value2"}')

    zip_buffer = builder.get_file_content()
    with zipfile.ZipFile(zip_buffer, "r") as zf:
        result = (
            set(zf.namelist()),
            zf.read("report1.jsonl").decode(),
            zf.read("report2.jsonl").decode(),
        )
    assert result == (
        {"report1.jsonl", "report2.jsonl"},
        '{"account1": "value1"}',
        '{"account2": "value2"}',
    )
