from swo_aws_extension.swo.notifications.mpt import dateformat


def test_dateformat():
    result = dateformat("2024-05-16T10:54:42.831Z")

    assert result == "16 May 2024"
    assert not dateformat("")
    assert not dateformat(None)
