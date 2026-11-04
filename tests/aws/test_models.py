import datetime as dt

from swo_aws_extension.aws.models import ChannelHandshakeServicePeriod
from swo_aws_extension.constants import ServicePeriodTypeEnum

COMMITMENT_YEAR = 2026
COMMITMENT_END = dt.datetime(COMMITMENT_YEAR, 1, 1, tzinfo=dt.UTC)


def _build_handshake(service_period_type, end_date=None):
    detail = {"servicePeriodType": service_period_type}
    if end_date:
        detail["endDate"] = end_date
    return {"detail": {"startServicePeriodHandshakeDetail": detail}}


def test_from_handshake_fixed_commitment():
    handshake = _build_handshake(
        ServicePeriodTypeEnum.FIXED_COMMITMENT_PERIOD.value,
        end_date=COMMITMENT_END,
    )

    service_period = ChannelHandshakeServicePeriod.from_handshake(handshake)  # act

    assert service_period.period_type == ServicePeriodTypeEnum.FIXED_COMMITMENT_PERIOD
    assert service_period.end_date == COMMITMENT_END
    assert service_period.is_fixed_commitment()


def test_from_handshake_minimum_notice_period():
    handshake = _build_handshake(ServicePeriodTypeEnum.MINIMUM_NOTICE_PERIOD.value)

    service_period = ChannelHandshakeServicePeriod.from_handshake(handshake)  # act

    assert service_period.period_type == ServicePeriodTypeEnum.MINIMUM_NOTICE_PERIOD
    assert service_period.end_date is None
    assert not service_period.is_fixed_commitment()


def test_from_handshake_without_detail():
    service_period = ChannelHandshakeServicePeriod.from_handshake({})  # act

    assert not service_period.period_type
    assert service_period.end_date is None
    assert not service_period.is_fixed_commitment()


def test_commitment_ends_after_deadline():
    service_period = ChannelHandshakeServicePeriod(
        period_type=ServicePeriodTypeEnum.FIXED_COMMITMENT_PERIOD,
        end_date=COMMITMENT_END,
    )

    result = service_period.commitment_ends_after(COMMITMENT_END - dt.timedelta(days=1))

    assert result


def test_commitment_ends_before_deadline():
    service_period = ChannelHandshakeServicePeriod(
        period_type=ServicePeriodTypeEnum.FIXED_COMMITMENT_PERIOD,
        end_date=COMMITMENT_END,
    )

    result = service_period.commitment_ends_after(COMMITMENT_END + dt.timedelta(days=1))

    assert not result


def test_commitment_ends_after_without_end_date():
    service_period = ChannelHandshakeServicePeriod(
        period_type=ServicePeriodTypeEnum.MINIMUM_NOTICE_PERIOD,
        end_date=None,
    )

    result = service_period.commitment_ends_after(COMMITMENT_END)

    assert not result
