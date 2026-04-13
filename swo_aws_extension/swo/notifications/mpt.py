import datetime as dt
import logging
from enum import Enum
from pathlib import Path

from django.conf import settings
from jinja2 import Environment, FileSystemLoader, select_autoescape

NotifyCategories = Enum("NotifyCategories", settings.MPT_NOTIFY_CATEGORIES)

logger = logging.getLogger(__name__)


def dateformat(date_string):
    """Formats date for notification format."""
    return dt.datetime.fromisoformat(date_string).strftime("%-d %B %Y") if date_string else ""


env = Environment(
    loader=FileSystemLoader(Path(__file__).resolve().parent / "templates"),
    autoescape=select_autoescape(),
)

env.filters["dateformat"] = dateformat
