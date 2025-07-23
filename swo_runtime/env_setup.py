"""
Automatic Django settings detection and setup.
This module is imported early to set up the correct Django settings based on context.
"""

import os


def setup_django_settings():
    """
    Automatically set Django settings based on execution context.
    """
    if "DJANGO_SETTINGS_MODULE" not in os.environ:
        # Default to production settings
        # (pytest will override this via conftest.py)
        os.environ["DJANGO_SETTINGS_MODULE"] = "swo_runtime.default"


# Run setup when module is imported
setup_django_settings()


