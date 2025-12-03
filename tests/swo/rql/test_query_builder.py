import datetime as dt
from decimal import Decimal

import pytest

from swo_aws_extension.swo.rql import constants
from swo_aws_extension.swo.rql.query_builder import RQLQuery, parse_kwargs


def test_create():
    result = RQLQuery()

    assert result.op == RQLQuery.OP_EXPR
    assert result.children == []
    assert result.negated is False


def test_create_with_field():
    result = RQLQuery("field")

    result.eq("value")
    assert result.op == RQLQuery.OP_EXPR
    assert str(result) == "eq(field,value)"


def test_create_single_kwarg():
    result = RQLQuery(id="ID")

    assert result.op == RQLQuery.OP_EXPR
    assert str(result) == "eq(id,ID)"
    assert result.children == []
    assert result.negated is False


def test_create_multiple_kwargs():
    result = RQLQuery(id="ID", status__in=("a", "b"), ok=True)

    assert result.op == RQLQuery.AND
    assert str(result) == "and(eq(id,ID),in(status,(a,b)),eq(ok,true))"
    assert len(result.children) == 3
    assert result.children[0].op == RQLQuery.OP_EXPR
    assert result.children[0].children == []
    assert str(result.children[0]) == "eq(id,ID)"
    assert result.children[1].op == RQLQuery.OP_EXPR
    assert result.children[1].children == []
    assert str(result.children[1]) == "in(status,(a,b))"
    assert result.children[2].op == RQLQuery.OP_EXPR
    assert result.children[2].children == []
    assert str(result.children[2]) == "eq(ok,true)"


@pytest.mark.parametrize(
    ("params", "expected"),
    [({}, 0), ({"id": "ID"}, 1), ({"id": "ID", "status__in": ("a", "b")}, 2)],
)
def test_len(params, expected):
    result = RQLQuery(**params)

    assert len(result) == expected


@pytest.mark.parametrize(
    ("params", "expected"),
    [({}, False), ({"id": "ID"}, True), ({"id": "ID", "status__in": ("a", "b")}, True)],
)
def test_bool(params, expected):
    result = bool(RQLQuery(**params))

    assert result is expected


@pytest.mark.parametrize(
    "params",
    [{}, {"id": "ID"}, {"id": "ID", "status__in": ("a", "b")}],
)
def test_eq(params):
    result = RQLQuery(**params)

    result2 = RQLQuery(**params)
    assert result == result2


def test_tild():
    result = ~RQLQuery(id="ID")

    result2 = ~RQLQuery(id="ID")
    assert result == result2


def test_ne():
    result = RQLQuery()

    result2 = RQLQuery(id="ID", status__in=("a", "b"))
    assert result != result2


def test_or():
    r1 = RQLQuery()
    r2 = RQLQuery()

    r3 = r1 | r2

    assert r3 == r1
    assert r3 == r2

    r1 = RQLQuery(id="ID")
    r2 = RQLQuery(id="ID")

    r3 = r1 | r2

    assert r3 == r1
    assert r3 == r2

    r1 = RQLQuery(id="ID")
    r2 = RQLQuery(name="name")

    r3 = r1 | r2

    assert r3 != r1
    assert r3 != r2

    assert r3.op == RQLQuery.OR
    assert r1 in r3.children
    assert r2 in r3.children

    r = RQLQuery(id="ID")
    assert r | RQLQuery() == r
    assert RQLQuery() | r == r


def test_or_merge():
    r1 = RQLQuery(id="ID")
    r2 = RQLQuery(name="name")

    r3 = RQLQuery(field="value")
    r4 = RQLQuery(field__in=("v1", "v2"))

    or1 = r1 | r2

    or2 = r3 | r4

    or3 = or1 | or2

    assert or3.op == RQLQuery.OR
    assert len(or3.children) == 4
    assert [r1, r2, r3, r4] == or3.children

    r1 = RQLQuery(id="ID")
    r2 = RQLQuery(field="value")

    r3 = r1 | r2 | r2

    assert len(r3) == 2
    assert r3.op == RQLQuery.OR
    assert [r1, r2] == r3.children

    r3 = r1 | r2

    assert r3.op == RQLQuery.OR
    assert str(r3) == "or(eq(id,ID),eq(field,value))"


def test_and():
    r1 = RQLQuery()
    r2 = RQLQuery()

    r3 = r1 & r2

    assert r3 == r1
    assert r3 == r2

    r1 = RQLQuery(id="ID")
    r2 = RQLQuery(id="ID")

    r3 = r1 & r2

    assert r3 == r1
    assert r3 == r2

    r1 = RQLQuery(id="ID")
    r2 = RQLQuery(name="name")

    r3 = r1 & r2

    assert r3 != r1
    assert r3 != r2

    assert r3.op == RQLQuery.AND
    assert r1 in r3.children
    assert r2 in r3.children

    r = RQLQuery(id="ID")
    assert r & RQLQuery() == r
    assert RQLQuery() & r == r

    r1 = RQLQuery(id="ID")
    r2 = RQLQuery(field="value")

    r3 = r1 & r2 & r2

    assert len(r3) == 2
    assert r3.op == RQLQuery.AND
    assert [r1, r2] == r3.children


def test_and_or():
    r1 = RQLQuery(id="ID")
    r2 = RQLQuery(field="value")

    r3 = RQLQuery(other="value2")
    r4 = RQLQuery(inop__in=("a", "b"))

    r5 = r1 & r2 & (r3 | r4)

    assert r5.op == RQLQuery.AND
    assert str(r5) == "and(eq(id,ID),eq(field,value),or(eq(other,value2),in(inop,(a,b))))"

    r5 = r1 & r2 | r3

    assert str(r5) == "or(and(eq(id,ID),eq(field,value)),eq(other,value2))"

    r5 = r1 & (r2 | r3)

    assert str(r5) == "and(eq(id,ID),or(eq(field,value),eq(other,value2)))"

    r5 = (r1 & r2) | (r3 & r4)

    assert str(r5) == "or(and(eq(id,ID),eq(field,value)),and(eq(other,value2),in(inop,(a,b))))"

    r5 = (r1 & r2) | ~r3

    assert str(r5) == "or(and(eq(id,ID),eq(field,value)),not(eq(other,value2)))"


def test_and_merge():
    r1 = RQLQuery(id="ID")
    r2 = RQLQuery(name="name")

    r3 = RQLQuery(field="value")
    r4 = RQLQuery(field__in=("v1", "v2"))

    and1 = r1 & r2

    and2 = r3 & r4

    and3 = and1 & and2

    assert and3.op == RQLQuery.AND
    assert len(and3.children) == 4
    assert [r1, r2, r3, r4] == and3.children


@pytest.mark.parametrize("op", ["eq", "ne", "gt", "ge", "le", "lt"])
def test_dotted_path_comp(op):
    assert str(getattr(RQLQuery().asset.id, op)("value")) == f"{op}(asset.id,value)"
    assert str(getattr(RQLQuery().asset.id, op)(True)) == f"{op}(asset.id,true)"  # noqa: FBT003
    assert str(getattr(RQLQuery().asset.id, op)(False)) == f"{op}(asset.id,false)"  # noqa: FBT003
    assert str(getattr(RQLQuery().asset.id, op)(10)) == f"{op}(asset.id,10)"
    assert str(getattr(RQLQuery().asset.id, op)(10.678937)) == f"{op}(asset.id,10.678937)"

    d = Decimal("32983.328238273")
    assert str(getattr(RQLQuery().asset.id, op)(d)) == f"{op}(asset.id,{d})"

    d = dt.datetime.now(tz=dt.UTC).date()
    assert str(getattr(RQLQuery().asset.id, op)(d)) == f"{op}(asset.id,{d.isoformat()})"

    d = dt.datetime.now(tz=dt.UTC)
    assert str(getattr(RQLQuery().asset.id, op)(d)) == f"{op}(asset.id,{d.isoformat()})"

    class Test:
        pass

    test = Test()

    with pytest.raises(TypeError):
        getattr(RQLQuery().asset.id, op)(test)


@pytest.mark.parametrize("op", ["like", "ilike"])
def test_dotted_path_search(op):
    assert str(getattr(RQLQuery().asset.id, op)("value")) == f"{op}(asset.id,value)"
    assert str(getattr(RQLQuery().asset.id, op)("*value")) == f"{op}(asset.id,*value)"
    assert str(getattr(RQLQuery().asset.id, op)("value*")) == f"{op}(asset.id,value*)"
    assert str(getattr(RQLQuery().asset.id, op)("*value*")) == f"{op}(asset.id,*value*)"


@pytest.mark.parametrize(
    "parameters",
    [("first", "second"), ["first", "second"]],
)
@pytest.mark.parametrize(
    ("method", "op"),
    [
        ("in_", "in"),
        ("oneof", "in"),
        ("out", "out"),
    ],
)
def test_dotted_path_list(method, op, parameters):
    rexpr = getattr(RQLQuery().asset.id, method)(parameters)
    assert str(rexpr) == f"{op}(asset.id,(first,second))"


@pytest.mark.parametrize("op", ["in", "out"])
def test_dotted_path_list_raise_exception(op):
    with pytest.raises(TypeError):
        getattr(RQLQuery().asset.id, op)("Test")


@pytest.mark.parametrize(
    ("expr", "value", "expected_op"),
    [
        ("null", True, "eq"),
        ("null", False, "ne"),
        ("empty", True, "eq"),
        ("empty", False, "ne"),
    ],
)
def test_dotted_path_bool(expr, value, expected_op):
    rql_str = str(getattr(RQLQuery().asset.id, expr)(value=value))
    assert rql_str == f"{expected_op}(asset.id,{expr}())"


def test_dotted_path_already_evaluated():
    q = RQLQuery().first.second.eq("value")

    with pytest.raises(AttributeError):
        _ = q.third


def test_str():
    assert str(RQLQuery(id="ID")) == "eq(id,ID)"
    assert str(~RQLQuery(id="ID")) == "not(eq(id,ID))"
    assert str(~RQLQuery(id="ID", field="value")) == "not(and(eq(id,ID),eq(field,value)))"
    assert not str(RQLQuery())


def test_hash():
    s = set()

    r = RQLQuery(id="ID", field="value")

    s.add(r)
    s.add(r)

    assert len(s) == 1


def test_empty():
    assert RQLQuery("value").empty() == RQLQuery("value").empty(value=True)
    assert str(RQLQuery("value").empty()) == "eq(value,empty())"
    assert str(RQLQuery("value").not_empty()) == "ne(value,empty())"
    assert RQLQuery("value").empty(value=False) == RQLQuery("value").not_empty()


def test_in_and_namespaces():
    products = ["PRD-1", "PRD-2"]
    q1 = RQLQuery().n("agreement").n("product").n("id").in_(products)
    q2 = RQLQuery().agreement.product.id.in_(products)
    assert str(q1) == str(q2)


def test_query_expression_get_querying_orders():
    products = ["PRD-1", "PRD-2"]
    products_str = ",".join(products)
    expected_rql_query = f"and(in(agreement.product.id,({products_str})),eq(status,Querying))"
    expected_url = (
        f"/commerce/orders?{expected_rql_query}&select=audit,parameters,lines,subscriptions,"
        f"subscriptions.lines,agreement,buyer&order=audit.created.at"
    )
    query = RQLQuery().agreement.product.id.in_(products) & RQLQuery(status="Querying")
    url = (
        f"/commerce/orders?{query}&select=audit,parameters,lines,subscriptions,"
        f"subscriptions.lines,agreement,buyer&order=audit.created.at"
    )
    assert expected_rql_query == str(query)
    assert expected_url == url


def test_in():
    product_ids = ["PRD-1", "PRD-2"]
    q = RQLQuery(product__id__in=product_ids)
    assert str(q) == "in(product.id,(PRD-1,PRD-2))"


def test_parse_kwargs_non_keyword_op():
    result = parse_kwargs({"agreement__product__id__custom": "PRD-1"})

    assert result == ["eq(agreement.product.id.custom,PRD-1)"]


@pytest.mark.parametrize(
    ("lookup", "value", "expected"),
    [
        (f"field__{constants.NULL}", True, "eq(field,null())"),
        (f"field__{constants.NULL}", False, "ne(field,null())"),
        (f"field__{constants.EMPTY}", True, "eq(field,empty())"),
        (f"field__{constants.EMPTY}", False, "ne(field,empty())"),
    ],
)
def test_parse_kwargs_null_and_empty_flags(lookup, value, expected):
    result = parse_kwargs({lookup: value})

    assert result == [expected]


def test_repr_for_expr_and_non_expr():
    q_expr = RQLQuery(id="ID")
    q_and = RQLQuery(id="ID", status__in=("a", "b"))

    assert repr(q_expr) == "<R(expr) eq(id,ID)>"
    assert repr(q_and) == "<R(and)>"
