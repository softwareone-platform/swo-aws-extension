import datetime as dt

import pytest
from freezegun import freeze_time

from swo_aws_extension.flows.jobs.pending_orders_information_report_creator import (
    PendingOrdersInformationReportCreator,
)

MODULE = "swo_aws_extension.flows.jobs.pending_orders_information_report_creator"
CREATED_AT = "2023-12-14T18:02:16.9359"


@pytest.fixture
def report_creator(mpt_client, config):
    return PendingOrdersInformationReportCreator(mpt_client, config)


def _patch_orders(mocker, orders):
    return mocker.patch(
        f"{MODULE}.get_orders_by_query",
        autospec=True,
        return_value=orders,
    )


@freeze_time(CREATED_AT)
def test_create_report(
    mocker,
    caplog,
    report_creator,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
):
    frozen_dt = dt.datetime.now(tz=dt.UTC)
    ms = format(frozen_dt.microsecond // 1000, "03d")
    expected_date = frozen_dt.strftime("%Y-%m-%d %H:%M:%S.") + ms
    querying_order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase="Querying",
            responsibility_transfer_id="rt-8lr3q6sn",
            customer_roles_deployed="yes",
            channel_handshake_approved="yes",
        ),
        order_parameters=order_parameters_factory(mpa_id="mpa-123"),
        status="Querying",
    )
    processing_order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            phase="Processing",
            responsibility_transfer_id="rt-8lr3q6sn",
            customer_roles_deployed="yes",
            channel_handshake_approved="yes",
        ),
        order_parameters=order_parameters_factory(mpa_id="mpa-123"),
        status="Processing",
    )
    orders = [querying_order, processing_order]
    expected_querying_excel_row = [
        querying_order["id"],
        querying_order["type"],
        querying_order["status"],
        expected_date,
        expected_date,
        querying_order["product"]["name"],
        querying_order["client"]["id"],
        querying_order["client"]["name"],
        querying_order["seller"]["name"],
        "Querying",
        "mpa-123",
        "example@example.com",
        querying_order["audit"]["created"]["by"]["name"],
        querying_order["assignee"]["name"],
    ]
    expected_processing_excel_row = [
        processing_order["id"],
        processing_order["type"],
        processing_order["status"],
        expected_date,
        expected_date,
        processing_order["product"]["name"],
        processing_order["client"]["id"],
        processing_order["client"]["name"],
        processing_order["seller"]["name"],
        "Processing",
        "mpa-123",
        "example@example.com",
        processing_order["audit"]["created"]["by"]["name"],
        processing_order["assignee"]["name"],
    ]
    expected_excel_rows = [expected_querying_excel_row, expected_processing_excel_row]
    _patch_orders(mocker, orders)

    result = report_creator.create()

    assert len(result) == len(orders)
    assert result == expected_excel_rows
    assert "Creating pending orders information report..." in caplog.text


@freeze_time(CREATED_AT)
def test_create_report_with_empty_audit_dates(
    mocker,
    caplog,
    report_creator,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(),
        order_parameters=order_parameters_factory(),
        status="Querying",
    )
    order["audit"]["created"]["at"] = ""
    order["audit"]["updated"]["at"] = ""
    _patch_orders(mocker, [order])

    result = report_creator.create()

    assert not result[0][3]
    assert not result[0][4]
    assert "Creating pending orders information report..." in caplog.text


@freeze_time(CREATED_AT)
def test_create_report_with_offset_aware_audit_dates(
    mocker,
    report_creator,
    order_factory,
    fulfillment_parameters_factory,
    order_parameters_factory,
):
    created_updated_date = "2023-12-14T20:02:16.9359+02:00"
    expected_date = "2023-12-14 18:02:16.935"
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(),
        order_parameters=order_parameters_factory(),
        status="Querying",
    )
    order["audit"]["created"]["at"] = created_updated_date
    order["audit"]["updated"]["at"] = created_updated_date
    _patch_orders(mocker, [order])

    result = report_creator.create()

    assert result[0][3] == expected_date
    assert result[0][4] == expected_date
