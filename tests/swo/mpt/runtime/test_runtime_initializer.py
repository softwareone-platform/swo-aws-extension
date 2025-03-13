import pytest
from swo.mpt.extensions.runtime.initializer import get_extension_variables


def test_get_extension_variables_valid(
    monkeypatch, mock_valid_env_values, mock_ext_expected_environment_values
):
    for key, value in mock_valid_env_values.items():
        monkeypatch.setenv(key, value)

    extension_variables = get_extension_variables()

    assert mock_ext_expected_environment_values.items() <= extension_variables.items()
