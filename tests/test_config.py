from swo_aws_extension.aws.config import Config


def test_config():
    config = Config()
    full_path = config._patch_path("secrets.txt")
    assert full_path[0] == "/"
