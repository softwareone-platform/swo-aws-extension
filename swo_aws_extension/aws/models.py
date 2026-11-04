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
        """Builds the service period from a channel handshake payload."""
        detail = handshake.get("detail", {}).get("startServicePeriodHandshakeDetail", {})
        end_date = detail.get("endDate")
        return cls(
            period_type=detail.get("servicePeriodType", ""),
            end_date=date_parser.to_utc(end_date) if end_date else None,
        )

    def is_fixed_commitment(self) -> bool:
        """Whether the handshake holds a fixed commitment period."""
        return self.period_type == ServicePeriodTypeEnum.FIXED_COMMITMENT_PERIOD

    def commitment_ends_after(self, deadline: dt.datetime) -> bool:
        """Whether the fixed commitment is still active after the given deadline."""
        return self.end_date is not None and self.end_date > deadline
