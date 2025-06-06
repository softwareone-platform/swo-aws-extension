from urllib.parse import urljoin

import pytest
from freezegun import freeze_time
from responses import matchers
from mpt_extension_sdk.mpt_http.mpt import (
    complete_order,
    create_agreement,
    create_agreement_subscription,
    create_listing,
    create_subscription,
    fail_order,
    get_agreement,
    get_agreement_subscription,
    get_agreement_subscription_by_external_id,
    get_agreements_by_query,
    get_all_agreements,
    get_authorizations_by_currency_and_seller_id,
    get_gc_price_list_by_currency,
    get_licensee,
    get_listing_by_id,
    get_listings_by_price_list_and_seller_and_authorization,
    get_order_subscription_by_external_id,
    get_product_items_by_skus,
    get_product_onetime_items_by_ids,
    get_product_template_or_default,
    get_rendered_template,
    get_webhook,
    query_order,
    update_agreement,
    update_agreement_subscription,
    update_order,
    update_subscription,
)


from mpt_extension_sdk.mpt_http.wrap_http_error import MPTAPIError


def test_fail_order_error(mpt_client, requests_mocker, mpt_error_factory):
    """
    Test the call to switch an order to Failed when it fails.
    """
    mock_status_notes = {
        "id": "ORD-0000",
        "message": "Order can't be processed. Failure reason: a-reason",
    }

    requests_mocker.post(
        urljoin(mpt_client.base_url, "commerce/orders/ORD-0000/fail"),
        status=404,
        json=mpt_error_factory(404, "Not Found", "Order not found"),
    )

    with pytest.raises(MPTAPIError) as cv:
        fail_order(mpt_client, "ORD-0000", mock_status_notes)

    assert cv.value.payload["status"] == 404


def test_query_order(mpt_client, requests_mocker, order_factory):
    """Test the call to switch an order to Query."""
    order = order_factory()
    requests_mocker.post(
        urljoin(mpt_client.base_url, "commerce/orders/ORD-0000/query"),
        json=order,
        match=[
            matchers.json_params_matcher(
                {
                    "parameters": {
                        "ordering": [
                            {
                                "externalId": "a-param",
                                "name": "a-param",
                                "value": "a-value",
                                "type": "SingleLineText",
                            }
                        ],
                    },
                },
            ),
        ],
    )

    qorder = query_order(
        mpt_client,
        "ORD-0000",
        parameters={
            "ordering": [
                {
                    "externalId": "a-param",
                    "name": "a-param",
                    "value": "a-value",
                    "type": "SingleLineText",
                }
            ]
        },
    )
    assert qorder == order


def test_query_order_error(mpt_client, requests_mocker, mpt_error_factory):
    """
    Test the call to switch an order to Query when it fails.
    """
    requests_mocker.post(
        urljoin(mpt_client.base_url, "commerce/orders/ORD-0000/query"),
        status=404,
        json=mpt_error_factory(404, "Not Found", "Order not found"),
    )

    with pytest.raises(MPTAPIError) as cv:
        query_order(mpt_client, "ORD-0000", parameters={})

    assert cv.value.payload["status"] == 404


def test_update_order(mpt_client, requests_mocker, order_factory):
    """Test the call to update an order."""
    order = order_factory()
    requests_mocker.put(
        urljoin(mpt_client.base_url, "commerce/orders/ORD-0000"),
        json=order,
        match=[
            matchers.json_params_matcher(
                {
                    "parameters": {
                        "ordering": [
                            {
                                "externalId": "a-param",
                                "name": "a-param",
                                "value": "a-value",
                                "type": "SingleLineText",
                            }
                        ],
                    },
                },
            ),
        ],
    )

    updated_order = update_order(
        mpt_client,
        "ORD-0000",
        parameters={
            "ordering": [
                {
                    "externalId": "a-param",
                    "name": "a-param",
                    "value": "a-value",
                    "type": "SingleLineText",
                }
            ]
        },
    )
    assert updated_order == order


def test_update_order_error(mpt_client, requests_mocker, mpt_error_factory):
    """
    Test the call to update an order when it fails.
    """
    requests_mocker.put(
        urljoin(mpt_client.base_url, "commerce/orders/ORD-0000"),
        status=404,
        json=mpt_error_factory(404, "Not Found", "Order not found"),
    )

    with pytest.raises(MPTAPIError) as cv:
        update_order(mpt_client, "ORD-0000", parameters={})

    assert cv.value.payload["status"] == 404


def test_complete_order(mpt_client, requests_mocker, order_factory):
    """Test the call to switch an order to Completed."""
    order = order_factory()
    requests_mocker.post(
        urljoin(mpt_client.base_url, "commerce/orders/ORD-0000/complete"),
        json=order,
        match=[
            matchers.json_params_matcher(
                {
                    "template": {"id": "templateId"},
                },
            ),
        ],
    )

    completed_order = complete_order(
        mpt_client,
        "ORD-0000",
        {"id": "templateId"},
    )
    assert completed_order == order


def test_complete_order_error(mpt_client, requests_mocker, mpt_error_factory):
    """
    Test the call to switch an order to Completed when it fails.
    """
    requests_mocker.post(
        urljoin(mpt_client.base_url, "commerce/orders/ORD-0000/complete"),
        status=404,
        json=mpt_error_factory(404, "Not Found", "Order not found"),
    )

    with pytest.raises(MPTAPIError) as cv:
        complete_order(mpt_client, "ORD-0000", {"id": "templateId"})

    assert cv.value.payload["status"] == 404


def test_create_subscription(mpt_client, requests_mocker, subscriptions_factory):
    """Test the call to create a subscription."""
    subscription = subscriptions_factory()[0]
    requests_mocker.post(
        urljoin(mpt_client.base_url, "commerce/orders/ORD-0000/subscriptions"),
        json=subscription,
        status=201,
        match=[
            matchers.json_params_matcher(subscription),
        ],
    )

    created_subscription = create_subscription(
        mpt_client,
        "ORD-0000",
        subscription,
    )
    assert created_subscription == subscription


def test_create_subscription_error(mpt_client, requests_mocker, mpt_error_factory):
    """
    Test the call to create a subscription when it fails.
    """
    requests_mocker.post(
        urljoin(mpt_client.base_url, "commerce/orders/ORD-0000/subscriptions"),
        status=404,
        json=mpt_error_factory(404, "Not Found", "Order not found"),
    )

    with pytest.raises(MPTAPIError) as cv:
        create_subscription(mpt_client, "ORD-0000", {})

    assert cv.value.payload["status"] == 404


def test_update_subscription(mpt_client, requests_mocker, subscriptions_factory):
    """Test the call to update a subscription."""
    subscription = subscriptions_factory()
    requests_mocker.put(
        urljoin(
            mpt_client.base_url,
            "commerce/orders/ORD-0000/subscriptions/SUB-1234",
        ),
        json=subscription,
        match=[
            matchers.json_params_matcher(
                {
                    "parameters": {
                        "fulfillment": [
                            {
                                "externalId": "a-param",
                                "name": "a-param",
                                "value": "a-value",
                                "type": "SingleLineText",
                            }
                        ],
                    },
                },
            ),
        ],
    )

    updated_subscription = update_subscription(
        mpt_client,
        "ORD-0000",
        "SUB-1234",
        parameters={
            "fulfillment": [
                {
                    "externalId": "a-param",
                    "name": "a-param",
                    "value": "a-value",
                    "type": "SingleLineText",
                }
            ]
        },
    )
    assert updated_subscription == subscription


def test_update_subscription_error(mpt_client, requests_mocker, mpt_error_factory):
    """
    Test the call to update a subscription when it fails.
    """
    requests_mocker.put(
        urljoin(mpt_client.base_url, "commerce/orders/ORD-0000/subscriptions/SUB-1234"),
        status=404,
        json=mpt_error_factory(404, "Not Found", "Order not found"),
    )

    with pytest.raises(MPTAPIError) as cv:
        update_subscription(mpt_client, "ORD-0000", "SUB-1234", parameters={})

    assert cv.value.payload["status"] == 404


def test_get_product_items_by_skus(mpt_client, requests_mocker):
    """
    Tests the call to retrieve all the item of a given product
    that matches a list of vendor SKUs.
    """
    product_id = "PRD-1234-5678"
    skus = ["sku1", "sku2"]
    rql_query = f"and(eq(product.id,{product_id}),in(externalIds.vendor,({','.join(skus)})))"
    url = f"catalog/items?{rql_query}"
    page1_url = f"{url}&limit=10&offset=0"
    page2_url = f"{url}&limit=10&offset=10"
    data = [{"id": f"ITM-{idx}"} for idx in range(13)]
    requests_mocker.get(
        urljoin(mpt_client.base_url, page1_url),
        json={
            "$meta": {
                "pagination": {
                    "offset": 0,
                    "limit": 10,
                    "total": 12,
                },
            },
            "data": data[:10],
        },
    )
    requests_mocker.get(
        urljoin(mpt_client.base_url, page2_url),
        json={
            "$meta": {
                "pagination": {
                    "offset": 10,
                    "limit": 10,
                    "total": 12,
                },
            },
            "data": data[10:],
        },
    )

    assert get_product_items_by_skus(mpt_client, product_id, skus) == data


def test_get_product_items_by_skus_error(mpt_client, requests_mocker, mpt_error_factory):
    """
    Tests the call to retrieve all the item of a given product
    that matches a list of vendor SKUs.
    """
    product_id = "PRD-1234-5678"
    skus = ["sku1", "sku2"]
    rql_query = f"and(eq(product.id,{product_id}),in(externalIds.vendor,({','.join(skus)})))"
    url = f"catalog/items?{rql_query}&limit=10&offset=0"

    requests_mocker.get(
        urljoin(mpt_client.base_url, url),
        status=500,
        json=mpt_error_factory(500, "Internal server error", "Whatever"),
    )

    with pytest.raises(MPTAPIError) as cv:
        get_product_items_by_skus(mpt_client, product_id, skus)

    assert cv.value.payload["status"] == 500


def test_get_webhoook(mpt_client, requests_mocker, webhook):
    requests_mocker.get(
        urljoin(mpt_client.base_url, f"notifications/webhooks/{webhook["id"]}"),
        json=webhook,
    )

    api_webhook = get_webhook(mpt_client, webhook["id"])
    assert api_webhook == webhook


@pytest.mark.parametrize(
    ("total", "data", "expected"),
    [
        (0, [], None),
        (1, [{"id": "SUB-1234"}], {"id": "SUB-1234"}),
    ],
)
def test_get_order_subscription_by_external_id(mpt_client, requests_mocker, total, data, expected):
    requests_mocker.get(
        urljoin(
            mpt_client.base_url,
            "/v1/commerce/orders/ORD-1234/subscriptions?eq(externalIds.vendor,a-sub-id)&limit=1",
        ),
        json={
            "$meta": {
                "pagination": {
                    "offset": 0,
                    "limit": 0,
                    "total": total,
                },
            },
            "data": data,
        },
    )

    assert get_order_subscription_by_external_id(mpt_client, "ORD-1234", "a-sub-id") == expected


@pytest.mark.parametrize("name", ["template_name", None])
def test_get_product_template_or_default(mpt_client, requests_mocker, name):
    name_or_default_filter = "eq(default,true)"
    if name:
        name_or_default_filter = f"or({name_or_default_filter},eq(name,{name}))"
    rql_filter = f"and(eq(type,OrderProcessing),{name_or_default_filter})"
    url = f"catalog/products/PRD-1111/templates?{rql_filter}&order=default&limit=1"
    requests_mocker.get(
        urljoin(
            mpt_client.base_url,
            url,
        ),
        json={
            "data": [
                {"id": "TPL-0000"},
            ]
        },
    )

    assert get_product_template_or_default(
        mpt_client,
        "PRD-1111",
        "Processing",
        name,
    ) == {"id": "TPL-0000"}


def test_update_agreement(mpt_client, requests_mocker):
    """Test the call to update an agreement."""
    requests_mocker.put(
        urljoin(mpt_client.base_url, "commerce/agreements/AGR-1111"),
        json={"id": "AGR-1111"},
        match=[
            matchers.json_params_matcher(
                {
                    "externalIds": {
                        "vendor": "1234",
                    },
                },
            ),
        ],
    )

    updated_agreement = update_agreement(
        mpt_client,
        "AGR-1111",
        externalIds={"vendor": "1234"},
    )
    assert updated_agreement == {"id": "AGR-1111"}


def test_update_agreement_error(mpt_client, requests_mocker, mpt_error_factory):
    """
    Test the call to update an order when it fails.
    """
    requests_mocker.put(
        urljoin(mpt_client.base_url, "commerce/agreements/AGR-1111"),
        status=404,
        json=mpt_error_factory(404, "Not Found", "Order not found"),
    )

    with pytest.raises(MPTAPIError) as cv:
        update_agreement(mpt_client, "AGR-1111", externalIds={"vendor": "1234"})

    assert cv.value.payload["status"] == 404


def test_update_agreement_subscription(mpt_client, requests_mocker, subscriptions_factory):
    subscription = subscriptions_factory()
    requests_mocker.put(
        urljoin(
            mpt_client.base_url,
            "commerce/subscriptions/SUB-1234",
        ),
        json=subscription,
        match=[
            matchers.json_params_matcher(
                {
                    "parameters": {
                        "fulfillment": [
                            {
                                "externalId": "a-param",
                                "name": "a-param",
                                "value": "a-value",
                                "type": "SingleLineText",
                            }
                        ],
                    },
                },
            ),
        ],
    )

    updated_subscription = update_agreement_subscription(
        mpt_client,
        "SUB-1234",
        parameters={
            "fulfillment": [
                {
                    "externalId": "a-param",
                    "name": "a-param",
                    "value": "a-value",
                    "type": "SingleLineText",
                }
            ]
        },
    )
    assert updated_subscription == subscription


def test_update_agreement_subscription_error(mpt_client, requests_mocker, mpt_error_factory):
    requests_mocker.put(
        urljoin(mpt_client.base_url, "commerce/subscriptions/SUB-1234"),
        status=404,
        json=mpt_error_factory(404, "Not Found", "Order not found"),
    )

    with pytest.raises(MPTAPIError) as cv:
        update_agreement_subscription(mpt_client, "SUB-1234", parameters={})

    assert cv.value.payload["status"] == 404


def test_get_agreement_subscription(mpt_client, requests_mocker, subscriptions_factory):
    sub = subscriptions_factory()[0]
    requests_mocker.get(
        urljoin(mpt_client.base_url, f"commerce/subscriptions/{sub["id"]}"),
        json=sub,
    )

    assert get_agreement_subscription(mpt_client, sub["id"]) == sub


def test_get_agreement_subscription_error(mpt_client, requests_mocker, mpt_error_factory):
    requests_mocker.get(
        urljoin(mpt_client.base_url, "commerce/subscriptions/SUB-1234"),
        status=404,
        json=mpt_error_factory(404, "Not Found", "Order not found"),
    )

    with pytest.raises(MPTAPIError) as cv:
        get_agreement_subscription(mpt_client, "SUB-1234")

    assert cv.value.payload["status"] == 404


def test_get_agreements_by_query(mpt_client, requests_mocker):
    rql_query = "any-rql-query&select=any-obj"
    url = f"commerce/agreements?{rql_query}"

    page1_url = f"{url}&limit=10&offset=0"
    page2_url = f"{url}&limit=10&offset=10"
    data = [{"id": f"AGR-{idx}"} for idx in range(13)]
    requests_mocker.get(
        urljoin(mpt_client.base_url, page1_url),
        json={
            "$meta": {
                "pagination": {
                    "offset": 0,
                    "limit": 10,
                    "total": 12,
                },
            },
            "data": data[:10],
        },
    )
    requests_mocker.get(
        urljoin(mpt_client.base_url, page2_url),
        json={
            "$meta": {
                "pagination": {
                    "offset": 10,
                    "limit": 10,
                    "total": 12,
                },
            },
            "data": data[10:],
        },
    )

    assert get_agreements_by_query(mpt_client, rql_query) == data


def test_get_agreements_by_query_error(mpt_client, requests_mocker, mpt_error_factory):
    rql_query = "any-rql-query&select=any-obj"
    url = f"commerce/agreements?{rql_query}"

    url = f"{url}&limit=10&offset=0"
    requests_mocker.get(
        urljoin(mpt_client.base_url, url),
        status=500,
        json=mpt_error_factory(500, "Internal server error", "Whatever"),
    )

    with pytest.raises(MPTAPIError) as cv:
        get_agreements_by_query(mpt_client, rql_query)

    assert cv.value.payload["status"] == 500


def test_get_rendered_template(mpt_client, requests_mocker):
    requests_mocker.get(
        urljoin(mpt_client.base_url, "commerce/orders/ORD-1234/template"),
        json="rendered-template",
    )

    assert get_rendered_template(mpt_client, "ORD-1234") == "rendered-template"


def test_get_rendered_template_error(mpt_client, requests_mocker, mpt_error_factory):
    requests_mocker.get(
        urljoin(mpt_client.base_url, "commerce/orders/ORD-1234/template"),
        status=404,
        json=mpt_error_factory(404, "Not Found", "Order not found"),
    )

    with pytest.raises(MPTAPIError) as cv:
        get_rendered_template(mpt_client, "ORD-1234")

    assert cv.value.payload["status"] == 404


def test_get_product_onetime_items_by_ids(mpt_client, requests_mocker):
    product_id = "PRD-1234-5678"
    ids = ["ITM-0001", "ITM-0002"]
    rql_query = (
        f"and(eq(product.id,{product_id}),in(id,({','.join(ids)})),eq(terms.period,one-time))"
    )
    url = f"catalog/items?{rql_query}"
    page1_url = f"{url}&limit=10&offset=0"
    page2_url = f"{url}&limit=10&offset=10"
    data = [{"id": f"ITM-{idx}"} for idx in range(13)]
    requests_mocker.get(
        urljoin(mpt_client.base_url, page1_url),
        json={
            "$meta": {
                "pagination": {
                    "offset": 0,
                    "limit": 10,
                    "total": 12,
                },
            },
            "data": data[:10],
        },
    )
    requests_mocker.get(
        urljoin(mpt_client.base_url, page2_url),
        json={
            "$meta": {
                "pagination": {
                    "offset": 10,
                    "limit": 10,
                    "total": 12,
                },
            },
            "data": data[10:],
        },
    )

    assert get_product_onetime_items_by_ids(mpt_client, product_id, ids) == data


def test_get_product_onetime_items_by_ids_error(mpt_client, requests_mocker, mpt_error_factory):
    product_id = "PRD-1234-5678"
    ids = ["ITM-0001", "ITM-0002"]
    rql_query = (
        f"and(eq(product.id,{product_id}),in(id,({','.join(ids)})),eq(terms.period,OneTime))"
    )
    url = f"catalog/items?{rql_query}&limit=10&offset=0"

    requests_mocker.get(
        urljoin(mpt_client.base_url, url),
        status=500,
        json=mpt_error_factory(500, "Internal server error", "Whatever"),
    )

    with pytest.raises(MPTAPIError) as cv:
        get_product_onetime_items_by_ids(mpt_client, product_id, ids)

    assert cv.value.payload["status"] == 500


def test_get_all_agreements(mocker, settings):
    product_condition = f"in(product.id,({','.join(settings.MPT_PRODUCTS_IDS)}))"
    rql_query = (
        f"and(eq(status,Active),{product_condition})"
        f"&select=lines,parameters,subscriptions,product,listing"
    )

    mocked_get_by_query = mocker.patch(
        "mpt_extension_sdk.mpt_http.mpt.get_agreements_by_query",
        return_value=[{"id": "AGR-0001"}],
    )

    mocked_client = mocker.MagicMock()

    assert get_all_agreements(mocked_client) == [{"id": "AGR-0001"}]
    mocked_get_by_query.assert_called_once_with(mocked_client, rql_query)


def test_get_agreement(mpt_client, requests_mocker, agreement):
    agreement_id = agreement["id"]
    requests_mocker.get(
        urljoin(
            mpt_client.base_url,
            f"commerce/agreements/{agreement_id}?select=seller,buyer,listing,product,subscriptions",
        ),
        json=agreement,
    )

    assert get_agreement(mpt_client, agreement_id) == agreement


def test_get_agreement_error(mpt_client, requests_mocker, mpt_error_factory):
    requests_mocker.get(
        urljoin(
            mpt_client.base_url,
            "commerce/agreements/AGR-1234?select=seller,buyer,listing,product,subscriptions",
        ),
        status=404,
        json=mpt_error_factory(404, "Not Found", "Agreement not found"),
    )

    with pytest.raises(MPTAPIError) as cv:
        get_agreement(mpt_client, "AGR-1234")

    assert cv.value.payload["status"] == 404


def test_get_licensee(mpt_client, requests_mocker, agreement):
    licensee = agreement["licensee"]
    licensee_id = licensee["id"]
    requests_mocker.get(
        urljoin(mpt_client.base_url, f"accounts/licensees/{licensee_id}"),
        json=licensee,
    )

    assert get_licensee(mpt_client, licensee_id) == licensee


def test_get_licensee_error(mpt_client, requests_mocker, mpt_error_factory):
    requests_mocker.get(
        urljoin(mpt_client.base_url, "accounts/licensees/LIC-1234"),
        status=404,
        json=mpt_error_factory(404, "Not Found", "Licensee not found"),
    )

    with pytest.raises(MPTAPIError) as cv:
        get_licensee(mpt_client, "LIC-1234")

    assert cv.value.payload["status"] == 404


def test_get_authorizations_by_currency_and_seller_id(mpt_client, requests_mocker):
    product_id = "product_id"
    currency = "currency"
    owner_id = "owner_id"
    requests_mocker.get(
        urljoin(
            mpt_client.base_url,
            f"catalog/authorizations?eq(product.id,{product_id})"
            f"&eq(currency,{currency})&eq(owner.id,{owner_id})",
        ),
        json={"data": []},
    )

    assert (
        get_authorizations_by_currency_and_seller_id(mpt_client, product_id, currency, owner_id)
        == []
    )


def test_get_gc_price_list_by_currency(mpt_client, requests_mocker):
    product_id = "product_id"
    currency = "currency"
    requests_mocker.get(
        urljoin(
            mpt_client.base_url,
            f"catalog/price-lists?eq(product.id,{product_id})&eq(currency,{currency})",
        ),
        json={"data": []},
    )

    assert get_gc_price_list_by_currency(mpt_client, product_id, currency) == []


def test_get_listings_by_currency_and_by_seller_id(mpt_client, requests_mocker):
    product_id = "product_id"
    price_list_id = "price_list_id"
    seller_id = "seller_id"
    authorization_id = "authorization_id"
    requests_mocker.get(
        urljoin(
            mpt_client.base_url,
            f"catalog/listings?eq(product.id,{product_id})&"
            f"eq(priceList.id,{price_list_id})&eq(seller.id,{seller_id})&"
            f"q(authorization.id,{authorization_id})&eq(primary,True)",
        ),
        json={"data": []},
    )

    assert (
        get_listings_by_price_list_and_seller_and_authorization(
            mpt_client, product_id, price_list_id, seller_id, authorization_id
        )
        == []
    )


def test_get_listing_by_id(mpt_client, requests_mocker):
    listing_id = "listing_id"

    requests_mocker.get(
        urljoin(mpt_client.base_url, f"catalog/listings/{listing_id}"),
        json={"data": []},
    )

    assert get_listing_by_id(mpt_client, listing_id) == {"data": []}


def test_get_subscription_by_external_id(mpt_client, requests_mocker, subscriptions_factory):
    subscription_external_id = "subscription_external_id"
    agreement_id = "agreement_id"
    subscriptions = subscriptions_factory()

    requests_mocker.get(
        urljoin(
            mpt_client.base_url,
            f"commerce/subscriptions?eq(externalIds.vendor,{subscription_external_id})"
            f"&eq(agreement.id,{agreement_id})"
            f"&in(status,(Active,Updating))"
            f"&select=agreement.id&limit=1",
        ),
        json={
            "$meta": {
                "pagination": {
                    "offset": 0,
                    "limit": 10,
                    "total": 1,
                },
            },
            "data": subscriptions,
        },
    )

    assert (
        get_agreement_subscription_by_external_id(
            mpt_client, agreement_id, subscription_external_id
        )
        == subscriptions[0]
    )


def test_create_listing(mpt_client, requests_mocker):
    listing = {
        "authorization": {"id": "authorization_id"},
        "priceList": {"id": "price_list_id"},
        "product": {"id": "product_id"},
        "seller": {"id": "seller_id"},
        "notes": "",
        "primary": True,
    }
    requests_mocker.post(
        urljoin(mpt_client.base_url, "catalog/listings"),
        json=listing,
        status=201,
        match=[
            matchers.json_params_matcher(listing),
        ],
    )

    created_listing = create_listing(mpt_client, listing)
    assert created_listing == listing


def test_create_agreement(mpt_client, requests_mocker, agreement):
    requests_mocker.post(
        urljoin(mpt_client.base_url, "commerce/agreements"),
        json=agreement,
        status=201,
        match=[
            matchers.json_params_matcher(agreement),
        ],
    )

    created_agreement = create_agreement(mpt_client, agreement)
    assert created_agreement == agreement


def test_create_agreement_subscription(mpt_client, requests_mocker, subscriptions_factory):
    subscription = subscriptions_factory()
    requests_mocker.post(
        urljoin(mpt_client.base_url, "commerce/subscriptions"),
        json=subscription,
        status=201,
        match=[
            matchers.json_params_matcher(subscription),
        ],
    )

    created_subscription = create_agreement_subscription(mpt_client, subscription)
    assert created_subscription == subscription
