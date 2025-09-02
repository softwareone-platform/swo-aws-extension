from swo_rql import R


def test_in_and_namespaces():
    products = ["PRD-1", "PRD-2"]
    q1 = R().n("agreement").n("product").n("id").in_(products)
    q2 = R().agreement.product.id.in_(products)
    assert str(q1) == str(q2)


def test_query_expression_get_querying_orders():
    products = ["PRD-1", "PRD-2"]
    products_str = ",".join(products)
    expected_rql_query = f"and(in(agreement.product.id,({products_str})),eq(status,Querying))"
    expected_url = (
        f"/commerce/orders?{expected_rql_query}&select=audit,parameters,lines,subscriptions,"
        f"subscriptions.lines,agreement,buyer&order=audit.created.at"
    )
    query = R().agreement.product.id.in_(products) & R(status="Querying")
    url = (
        f"/commerce/orders?{query}&select=audit,parameters,lines,subscriptions,"
        f"subscriptions.lines,agreement,buyer&order=audit.created.at"
    )
    assert expected_rql_query == str(query)
    assert expected_url == url


def test_in():
    product_ids = ["PRD-1", "PRD-2"]
    q = R(product__id__in=product_ids)
    assert str(q) == "in(product.id,(PRD-1,PRD-2))"
