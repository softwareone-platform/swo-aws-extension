import pytest

from swo_aws_extension import parameters
from swo_aws_extension.constants import (
    AccountTypesEnum,
    MigrationOrderEnum,
    OrderParametersEnum,
)


def test_get_termination_date(order_factory, fulfillment_parameters_factory):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(termination_date="2026-12-31")
    )

    result = parameters.get_termination_date(order)

    assert result == "2026-12-31"


def test_get_termination_date_not_set():
    source = {"parameters": {"fulfillment": []}}

    result = parameters.get_termination_date(source)

    assert result is None


def test_set_termination_date(order_factory, fulfillment_parameters_factory):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(termination_date="")
    )

    result = parameters.set_termination_date(order, "2026-12-31")

    assert parameters.get_termination_date(result) == "2026-12-31"


def test_get_relationship_end_date(order_factory, fulfillment_parameters_factory):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(
            relationship_end_date="2026-10-31T23:59:59.999000+00:00"
        )
    )

    result = parameters.get_relationship_end_date(order)

    assert result == "2026-10-31T23:59:59.999000+00:00"


def test_set_relationship_end_date(order_factory, fulfillment_parameters_factory):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(relationship_end_date="")
    )

    result = parameters.set_relationship_end_date(order, "2026-10-31T23:59:59.999000+00:00")

    assert parameters.get_relationship_end_date(result) == "2026-10-31T23:59:59.999000+00:00"


def test_get_formatted_technical_contact_with_phone_object():
    source = {
        "parameters": {
            "ordering": [
                {
                    "externalId": OrderParametersEnum.CONTACT.value,
                    "value": {
                        "firstName": "John",
                        "lastName": "Doe",
                        "email": "john.doe@example.com",
                        "phone": {"prefix": "+34", "number": "600111222"},
                    },
                }
            ]
        }
    }

    result = parameters.get_formatted_technical_contact(source)

    assert result == {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "+34600111222",
    }


def test_reset_ordering_parameters_error(order_factory, order_parameters_factory):
    order = order_factory(
        order_parameters=order_parameters_factory(
            account_type=AccountTypesEnum.NEW_AWS_ENVIRONMENT.value
        )
    )

    # Set an error on a parameter
    order["parameters"]["ordering"][0]["error"] = {
        "err_id": "TEST001",
        "message": "Test error",
    }

    result = parameters.reset_ordering_parameters_error(order)

    # Verify all parameters have error set to None
    for ordering_params in result["parameters"]["ordering"]:
        assert ordering_params["error"] is None


def test_get_migration(order_factory, order_parameters_factory):
    order = order_factory(
        order_parameters=order_parameters_factory(migration=[MigrationOrderEnum.YES.value])
    )

    result = parameters.get_migration(order)

    assert result == [MigrationOrderEnum.YES.value]


def test_get_migration_not_set():
    source = {"parameters": {"ordering": []}}

    result = parameters.get_migration(source)

    assert result is None


@pytest.mark.parametrize(
    ("migration", "expected"),
    [
        ([MigrationOrderEnum.YES.value], True),
        (MigrationOrderEnum.YES.value, True),
        ([MigrationOrderEnum.NO_MIGRATION.value], False),
        (MigrationOrderEnum.NO_MIGRATION.value, False),
        ([], False),
        ("", False),
        (None, False),
    ],
)
def test_is_migration_order(order_factory, order_parameters_factory, migration, expected):
    order = order_factory(order_parameters=order_parameters_factory(migration=migration))

    result = parameters.is_migration_order(order)

    assert result is expected


def test_is_migration_order_not_set():
    source = {"parameters": {"ordering": []}}

    result = parameters.is_migration_order(source)

    assert result is False


def test_get_crm_migration_ticket_id(order_factory, fulfillment_parameters_factory):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(crm_migration_ticket_id="CS0001234")
    )

    result = parameters.get_crm_migration_ticket_id(order)

    assert result == "CS0001234"


def test_get_crm_migration_ticket_id_not_set():
    source = {"parameters": {"fulfillment": []}}

    result = parameters.get_crm_migration_ticket_id(source)

    assert result is None


def test_set_crm_migration_ticket_id(order_factory, fulfillment_parameters_factory):
    order = order_factory(
        fulfillment_parameters=fulfillment_parameters_factory(crm_migration_ticket_id="")
    )

    result = parameters.set_crm_migration_ticket_id(order, "CS0001234")

    assert parameters.get_crm_migration_ticket_id(result) == "CS0001234"
