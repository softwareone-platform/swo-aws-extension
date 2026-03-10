from collections.abc import Callable
from functools import wraps
from typing import Any

from swo_aws_extension.logger import (
    clear_log_context,
    set_log_context,
)


def with_log_context(value_extractor: Callable[..., str | None]) -> Callable:
    """Set log context and clear it after the function call."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            extracted_value = value_extractor(*args, **kwargs)

            if extracted_value is not None:
                set_log_context(extracted_value)

            try:
                return func(*args, **kwargs)
            finally:
                if extracted_value is not None:
                    clear_log_context(extracted_value)

        return wrapper

    return decorator
