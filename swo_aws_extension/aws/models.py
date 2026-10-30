import datetime as dt
from dataclasses import dataclass

from swo_aws_extension.constants import ServicePeriodTypeEnum
from swo_aws_extension.utils import date_parser


@dataclass(frozen=True)
class ChannelHandshakeServicePeriod:
    """Service period of a Partner Central channel handshake."""

    period_type: str
    end_date: dt.datetime | None

    @classmethod
    def from_handshake(cls, handshake: dict) -> "ChannelHandshakeServicePeriod":
        """
        Builds the service period from a channel handshake payload.

        A missing or null detail yields an empty service period.

        Raises:
            ValueError: If the end date is a string that isn't ISO 8601.
            TypeError: If the end date is neither a datetime nor a string.
        """
        handshake_detail = handshake.get("detail") or {}
        detail = handshake_detail.get("startServicePeriodHandshakeDetail") or {}
        return cls(
            period_type=detail.get("servicePeriodType", ""),
            end_date=_parse_end_date(detail.get("endDate")),
        )

    def is_fixed_commitment(self) -> bool:
        """Whether the handshake holds a fixed commitment period."""
        return self.period_type == ServicePeriodTypeEnum.FIXED_COMMITMENT_PERIOD

    def commitment_ends_after(self, deadline: dt.datetime) -> bool:
        """Whether the fixed commitment is still active after the given deadline."""
        return self.end_date is not None and self.end_date > deadline


def _parse_end_date(end_date: dt.datetime | str | None) -> dt.datetime | None:
    if not end_date:
        return None
    if isinstance(end_date, str):
        end_date = dt.datetime.fromisoformat(end_date)
    if not isinstance(end_date, dt.datetime):
        raise TypeError(f"Invalid channel handshake end date: {end_date!r}")
    return date_parser.to_utc(end_date)
