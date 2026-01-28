import pytest

from swo_aws_extension.constants import (
    CCP_SECRET_NOT_FOUND_IN_KEY_VAULT,
    FAILED_TO_SAVE_SECRET_TO_KEY_VAULT,
)
from swo_aws_extension.swo.key_vault import KeyVaultManager


@pytest.fixture
def key_vault_manager(config):
    return KeyVaultManager(config)


def test_get_secret_success(mocker, key_vault_manager):
    mocker.patch(
        "swo_aws_extension.swo.key_vault.KeyVault.get_secret",
        return_value="test_secret",
    )

    result = key_vault_manager.get_secret()

    assert result == "test_secret"


def test_get_secret_not_found(mocker, key_vault_manager, caplog):
    mocker.patch(
        "swo_aws_extension.swo.key_vault.KeyVault.get_secret",
        return_value=None,
    )
    mock_send_error = mocker.patch(
        "swo_aws_extension.swo.key_vault.TeamsNotificationManager.send_error"
    )

    result = key_vault_manager.get_secret()

    assert result is None
    assert CCP_SECRET_NOT_FOUND_IN_KEY_VAULT in caplog.text
    mock_send_error.assert_called_once()


def test_save_secret_success(mocker, key_vault_manager):
    mocker.patch(
        "swo_aws_extension.swo.key_vault.KeyVault.set_secret",
        return_value="saved_secret",
    )

    result = key_vault_manager.save_secret("new_secret")

    assert result == "saved_secret"


def test_save_secret_fails(mocker, key_vault_manager, caplog):
    mocker.patch(
        "swo_aws_extension.swo.key_vault.KeyVault.set_secret",
        return_value=None,
    )
    mock_send_error = mocker.patch(
        "swo_aws_extension.swo.key_vault.TeamsNotificationManager.send_error"
    )

    result = key_vault_manager.save_secret("new_secret")

    assert result is None
    assert FAILED_TO_SAVE_SECRET_TO_KEY_VAULT in caplog.text
    mock_send_error.assert_called_once()
