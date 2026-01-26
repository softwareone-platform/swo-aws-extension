from typing import Any
from unittest.mock import MagicMock

import pytest
import requests
from mpt_extension_sdk.mpt_http.base import MPTClient

from swo_aws_extension.config import Config
from swo_aws_extension.flows.jobs.query_order_processor import (
    PurchaseOrderQueryService,
    process_query_orders,
)
from swo_aws_extension.flows.order import PurchaseContext


@pytest.fixture
def mock_client() -> MagicMock:
    return MagicMock(spec=MPTClient)


@pytest.fixture
def mock_config() -> MagicMock:
    return MagicMock(spec=Config)


@pytest.fixture
def service(mock_client: MagicMock, mock_config: MagicMock) -> PurchaseOrderQueryService:
    return PurchaseOrderQueryService(mock_client, mock_config)


def test_process_query_orders(mocker: Any, mock_client: MagicMock, mock_config: MagicMock) -> None:
    mock_service_instance = MagicMock(spec=PurchaseOrderQueryService)
    mock_context = MagicMock(spec=PurchaseContext)
    mock_service_instance.get_orders_as_context.return_value = [mock_context]
    mocker.patch(
        "swo_aws_extension.flows.jobs.query_order_processor.PurchaseOrderQueryService",
        return_value=mock_service_instance,
    )
    mock_chain_instance = MagicMock()
    mock_chain_class = mocker.patch(
        "swo_aws_extension.flows.jobs.query_order_processor.ProcessorChain",
        return_value=mock_chain_instance,
    )

    process_query_orders(mock_client, mock_config)  # act

    mock_chain_class.assert_called_once()
    mock_chain_instance.process.assert_called_once_with(mock_context)


def test_process_query_orders_exception(
    mocker: Any, mock_client: MagicMock, mock_config: MagicMock
) -> None:

    mock_service_instance = MagicMock(spec=PurchaseOrderQueryService)
    mock_context = MagicMock(spec=PurchaseContext)
    mock_service_instance.get_orders_as_context.return_value = [mock_context]
    mocker.patch(
        "swo_aws_extension.flows.jobs.query_order_processor.PurchaseOrderQueryService",
        return_value=mock_service_instance,
    )
    mock_chain_instance = MagicMock()
    mock_chain_instance.process.side_effect = Exception("Process Error")
    mocker.patch(
        "swo_aws_extension.flows.jobs.query_order_processor.ProcessorChain",
        return_value=mock_chain_instance,
    )
    mock_logger = mocker.patch("swo_aws_extension.flows.jobs.query_order_processor.logger")

    process_query_orders(mock_client, mock_config)  # act

    mock_logger.exception.assert_called_once_with(
        "Error processing order in Querying state context"
    )


def test_filter(service: PurchaseOrderQueryService) -> None:
    result = service.filter()

    assert (
        str(result)
        == "and(in(agreement.product.id,(PRD-1111-1111)),eq(status,Querying),eq(type,Purchase))"
    )


def test_has_more_pages_no_orders(service: PurchaseOrderQueryService) -> None:
    page = None

    result = service.has_more_pages(page)

    assert result is True


def test_has_more_pages_true(service: PurchaseOrderQueryService) -> None:
    page = {"$meta": {"pagination": {"total": 20, "limit": 10, "offset": 0}}}

    result = service.has_more_pages(page)

    assert result is True


def test_has_more_pages_false(service: PurchaseOrderQueryService) -> None:
    page = {"$meta": {"pagination": {"total": 10, "limit": 10, "offset": 0}}}

    result = service.has_more_pages(page)

    assert result is False


def test_fetch_orders_success(service: PurchaseOrderQueryService, mock_client: MagicMock) -> None:
    first_page = MagicMock(spec=requests.Response)
    first_page.status_code = 200
    first_page.json.return_value = {
        "data": [{"id": "ORD-1"}],
        "$meta": {"pagination": {"total": 2, "limit": 1, "offset": 0}},
    }
    second_page = MagicMock()
    second_page.status_code = 200
    second_page.json.return_value = {
        "data": [{"id": "ORD-2"}],
        "$meta": {"pagination": {"total": 2, "limit": 1, "offset": 1}},
    }
    mock_client.get.side_effect = [first_page, second_page]
    service.page_limit = 1

    result = service.fetch_orders()

    assert len(result) == 2
    assert result[0]["id"] == "ORD-1"
    assert result[1]["id"] == "ORD-2"
    assert mock_client.get.call_count == 2


def test_fetch_orders_request_exception(
    service: PurchaseOrderQueryService, mock_client: MagicMock
) -> None:
    mock_client.get.side_effect = requests.RequestException("API Error")

    result = service.fetch_orders()

    assert result == []


def test_fetch_orders_error_status(
    service: PurchaseOrderQueryService, mock_client: MagicMock
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.content = b"Bad Request"
    mock_client.get.return_value = mock_response

    result = service.fetch_orders()

    assert result == []


def test_get_orders_as_context(mocker: Any, service: PurchaseOrderQueryService) -> None:
    orders = [{"id": "ORD-1", "agreement": {}, "seller": {}, "buyer": {}}]
    mocker.patch.object(service, "fetch_orders", return_value=orders)

    result = service.get_orders_as_context()

    assert len(result) == 1
    assert isinstance(result[0], PurchaseContext)
    assert result[0].order["id"] == "ORD-1"
