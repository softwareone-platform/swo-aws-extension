import copy
import json
import signal
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import jwt
import pytest
import responses
from django.conf import settings
from mpt_extension_sdk.core.events.dataclasses import Event
from mpt_extension_sdk.flows.context import ORDER_TYPE_TERMINATION
from rich.highlighter import ReprHighlighter as _ReprHighlighter
from swo.mpt.extensions.runtime.djapp.conf import get_for_product

from swo_aws_extension.airtable.models import (
    AirTableBaseInfo,
    NotificationStatusEnum,
    NotificationTypeEnum,
)
from swo_aws_extension.aws.client import AccountCreationStatus, AWSClient
from swo_aws_extension.aws.config import get_config
from swo_aws_extension.constants import (
    AWS_ITEMS_SKUS,
    AccountTypesEnum,
    AWSRecordTypeEnum,
    AWSServiceEnum,
    PhasesEnum,
    SupportTypesEnum,
    TerminationParameterChoices,
    UsageMetricTypeEnum,
)
from swo_aws_extension.flows.jobs.billing_journal.billing_journal_generator import (
    BillingJournalGenerator,
)
from swo_aws_extension.flows.jobs.billing_journal.item_journal_line import get_journal_processors
from swo_aws_extension.flows.jobs.billing_journal.models import (
    Description,
    ExternalIds,
    JournalLine,
    Period,
    Price,
    Search,
    SearchItem,
    SearchSubscription,
)
from swo_aws_extension.parameters import (
    ChangeOrderParametersEnum,
    FulfillmentParametersEnum,
    OrderParametersEnum,
)
from swo_ccp_client.client import CCPClient
from swo_crm_service_client import CRMServiceClient

PARAM_COMPANY_NAME = "ACME Inc"
AWESOME_PRODUCT = "Awesome product"
CREATED_AT = "2023-12-14T18:02:16.9359"
META = "$meta"
ACCOUNT_EMAIL = "test@aws.com"
ACCOUNT_NAME = "Account Name"
SERVICE_NAME = "Marketplace service"
INVOICE_ENTITY = "Amazon Web Services EMEA SARL"


@pytest.fixture()
def requests_mocker():
    """
    Allow mocking of http calls made with requests.
    """
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture()
def constraints():
    return {"hidden": True, "readonly": False, "required": False}


@pytest.fixture()
def order_parameters_factory(constraints):
    def _order_parameters(
        account_email=ACCOUNT_EMAIL,
        account_name="account_name",
        account_type=AccountTypesEnum.NEW_ACCOUNT.value,
        account_id="account_id",
        termination_type=TerminationParameterChoices.CLOSE_ACCOUNT,
        support_type=SupportTypesEnum.PARTNER_LED_SUPPORT.value,
        transfer_type=None,
        master_payer_id=None,
        change_order_email=ACCOUNT_EMAIL,
        change_order_name="account_name",
        crm_termination_ticket_id="",
    ):
        return [
            {
                "id": "PAR-1234-5678",
                "name": "AWS account email",
                "externalId": OrderParametersEnum.ROOT_ACCOUNT_EMAIL.value,
                "type": "SingleLineText",
                "value": account_email,
                "constraints": constraints,
            },
            {
                "id": "PAR-1234-5679",
                "name": ACCOUNT_NAME,
                "externalId": OrderParametersEnum.ACCOUNT_NAME.value,
                "type": "SingleLineText",
                "value": account_name,
                "constraints": constraints,
            },
            {
                "id": "PAR-1234-5680",
                "name": "Account type",
                "externalId": OrderParametersEnum.ACCOUNT_TYPE.value,
                "type": "choice",
                "value": account_type,
                "constraints": constraints,
            },
            {
                "id": "PAR-1234-5681",
                "name": "Account ID",
                "externalId": OrderParametersEnum.ACCOUNT_ID.value,
                "type": "SingleLineText",
                "value": account_id,
                "constraints": constraints,
            },
            {
                "id": "PAR-1234-5678",
                "name": "Account Termination Type",
                "externalId": OrderParametersEnum.TERMINATION.value,
                "type": "Choice",
                "value": termination_type,
            },
            {
                "id": "PAR-1234-5679",
                "name": "Support Type",
                "externalId": OrderParametersEnum.SUPPORT_TYPE.value,
                "type": "Choice",
                "value": support_type,
            },
            {
                "id": "PAR-1234-5680",
                "name": "Transfer Type",
                "externalId": OrderParametersEnum.TRANSFER_TYPE.value,
                "type": "Choice",
                "value": transfer_type,
            },
            {
                "id": "PAR-1234-5681",
                "name": "Master Payer ID",
                "externalId": OrderParametersEnum.MASTER_PAYER_ID.value,
                "type": "SingleLineText",
                "value": master_payer_id,
            },
            {
                "id": "PAR-1234-5655",
                "name": "AWS account email",
                "externalId": ChangeOrderParametersEnum.ROOT_ACCOUNT_EMAIL.value,
                "type": "SingleLineText",
                "value": change_order_email,
                "constraints": constraints,
            },
            {
                "id": "PAR-1234-5656",
                "name": ACCOUNT_NAME,
                "externalId": ChangeOrderParametersEnum.ACCOUNT_NAME.value,
                "type": "SingleLineText",
                "value": change_order_name,
                "constraints": constraints,
            },
            {
                "id": "PAR-1234-1678",
                "name": "Service-Now Ticket Termination",
                "externalId": OrderParametersEnum.CRM_TERMINATION_TICKET_ID.value,
                "type": "SingleLineText",
                "value": crm_termination_ticket_id,
            },
        ]

    return _order_parameters


@pytest.fixture()
def fulfillment_parameters_factory():
    def _fulfillment_parameters(
        phase="",
        account_request_id="",
        crm_onboard_ticket_id="",
        crm_keeper_ticket_id="",
        crm_ccp_ticket_id="",
        crm_transfer_organization_ticket_id="",
        ccp_engagement_id="",
        mpa_email="",
    ):
        return [
            {
                "id": "PAR-1234-5678",
                "name": "Phase",
                "externalId": FulfillmentParametersEnum.PHASE.value,
                "type": "Dropdown",
                "value": phase,
            },
            {
                "id": "PAR-1234-5679",
                "name": "Account Request ID",
                "externalId": FulfillmentParametersEnum.ACCOUNT_REQUEST_ID.value,
                "type": "SingleLineText",
                "value": account_request_id,
            },
            {
                "id": "PAR-1234-1678",
                "name": "Service-Now Ticket CCP",
                "externalId": FulfillmentParametersEnum.CRM_CCP_TICKET_ID.value,
                "type": "SingleLineText",
                "value": crm_ccp_ticket_id,
            },
            {
                "id": "PAR-1234-1678",
                "name": "Service-Now Ticket Keeper",
                "externalId": FulfillmentParametersEnum.CRM_KEEPER_TICKET_ID.value,
                "type": "SingleLineText",
                "value": crm_keeper_ticket_id,
            },
            {
                "id": "PAR-1234-1678",
                "name": "Service-Now Ticket Onboarding",
                "externalId": FulfillmentParametersEnum.CRM_ONBOARD_TICKET_ID.value,
                "type": "SingleLineText",
                "value": crm_onboard_ticket_id,
            },
            {
                "id": "PAR-1234-1678",
                "name": "Service-Now Ticket Transfer Organization",
                "externalId": FulfillmentParametersEnum.CRM_TRANSFER_ORGANIZATION_TICKET_ID.value,
                "type": "SingleLineText",
                "value": crm_transfer_organization_ticket_id,
            },
            {
                "id": "PAR-1234-5679",
                "name": "CCP Engagement ID",
                "externalId": FulfillmentParametersEnum.CCP_ENGAGEMENT_ID.value,
                "type": "SingleLineText",
                "value": ccp_engagement_id,
            },
            {
                "id": "PAR-1234-5680",
                "name": "CCP Engagement ID",
                "externalId": FulfillmentParametersEnum.MPA_EMAIL.value,
                "type": "Email",
                "value": mpa_email,
            },
        ]

    return _fulfillment_parameters


@pytest.fixture()
def items_factory():
    def _items(
        item_id=1,
        name=AWESOME_PRODUCT,
        external_vendor_id="65304578CA",
    ):
        return [
            {
                "id": f"ITM-1234-1234-1234-{item_id:04d}",
                "name": name,
                "externalIds": {
                    "vendor": external_vendor_id,
                },
            },
        ]

    return _items


@pytest.fixture()
def pricelist_items_factory():
    def _items(
        item_id=1,
        external_vendor_id="65304578CA",
        unit_purchase_price=1234.55,
    ):
        return [
            {
                "id": f"PRI-1234-1234-1234-{item_id:04d}",
                "item": {
                    "id": f"ITM-1234-1234-1234-{item_id:04d}",
                    "externalIds": {
                        "vendor": external_vendor_id,
                    },
                },
                "unitPP": unit_purchase_price,
            },
        ]

    return _items


@pytest.fixture()
def lines_factory(agreement, deployment_id: str = None):
    agreement_id = agreement["id"].split("-", 1)[1]

    def _items(
        line_id=1,
        item_id=1,
        name=AWESOME_PRODUCT,
        old_quantity=0,
        quantity=170,
        external_vendor_id=AWS_ITEMS_SKUS[0],
        unit_purchase_price=1234.55,
        deployment_id=deployment_id,
    ):
        line = {
            "item": {
                "id": f"ITM-1234-1234-1234-{item_id:04d}",
                "name": name,
                "externalIds": {
                    "vendor": external_vendor_id,
                },
            },
            "oldQuantity": old_quantity,
            "quantity": quantity,
            "price": {
                "unitPP": unit_purchase_price,
            },
        }
        if line_id:
            line["id"] = f"ALI-{agreement_id}-{line_id:04d}"
        if deployment_id:
            line["deploymentId"] = deployment_id
        return [line]

    return _items


@pytest.fixture()
def subscriptions_factory(lines_factory):
    def _subscriptions(
        subscription_id="SUB-1000-2000-3000",
        product_name=AWESOME_PRODUCT,
        vendor_id="123-456-789",
        start_date=None,
        commitment_date=None,
        lines=None,
        status="Terminating",
    ):
        start_date = start_date.isoformat() if start_date else datetime.now(UTC).isoformat()
        if lines is None:
            lines = []
            for sku in AWS_ITEMS_SKUS:
                lines.extend(lines_factory(external_vendor_id=sku, name=sku, quantity=1))
        return [
            {
                "id": subscription_id,
                "name": f"Subscription for {product_name}",
                "parameters": {"fulfillment": [{}]},
                "externalIds": {
                    "vendor": vendor_id,
                },
                "lines": lines,
                "startDate": start_date,
                "commitmentDate": commitment_date,
                "status": status,
            }
        ]

    return _subscriptions


@pytest.fixture()
def agreement_factory(buyer, order_parameters_factory, fulfillment_parameters_factory, seller):
    def _agreement(
        licensee_name="My beautiful licensee",
        licensee_address=None,
        licensee_contact=None,
        use_buyer_address=False,
        subscriptions=None,
        fulfillment_parameters=None,
        ordering_parameters=None,
        lines=None,
        vendor_id="",
    ):
        if not subscriptions:
            subscriptions = [
                {
                    "id": "SUB-1000-2000-3000",
                    "status": "Active",
                    "item": {
                        "id": "ITM-0000-0001-0001",
                    },
                },
                {
                    "id": "SUB-1234-5678",
                    "status": "Terminated",
                    "item": {
                        "id": "ITM-0000-0001-0002",
                    },
                },
            ]

        licensee = {
            "name": licensee_name,
            "address": licensee_address,
            "useBuyerAddress": use_buyer_address,
        }
        if licensee_contact:
            licensee["contact"] = licensee_contact

        return {
            "id": "AGR-2119-4550-8674-5962",
            "href": "/commerce/agreements/AGR-2119-4550-8674-5962",
            "icon": None,
            "name": "Product Name 1",
            "audit": {
                "created": {
                    "at": CREATED_AT,
                    "by": {"id": "USR-0000-0001"},
                },
                "updated": None,
            },
            "listing": {
                "id": "LST-9401-9279",
                "href": "/listing/LST-9401-9279",
                "priceList": {
                    "id": "PRC-9457-4272-3691",
                    "href": "/v1/price-lists/PRC-9457-4272-3691",
                    "currency": "USD",
                },
            },
            "licensee": licensee,
            "buyer": buyer,
            "seller": {
                "id": seller["id"],
                "href": seller["href"],
                "name": seller["name"],
                "icon": seller["icon"],
                "address": {
                    "country": "US",
                },
            },
            "client": {
                "id": "ACC-9121-8944",
                "href": "/accounts/sellers/ACC-9121-8944",
                "name": "Software LN",
                "icon": "/static/ACC-9121-8944/icon.png",
            },
            "product": {
                "id": "PRD-1111-1111",
            },
            "authorization": {"id": "AUT-1234-5678"},
            "lines": lines or [],
            "subscriptions": subscriptions,
            "parameters": {
                "ordering": ordering_parameters or order_parameters_factory(),
                "fulfillment": fulfillment_parameters or fulfillment_parameters_factory(),
            },
            "externalIds": {"vendor": vendor_id},
        }

    return _agreement


@pytest.fixture()
def licensee(buyer):
    return {
        "id": "LCE-1111-2222-3333",
        "name": "FF Buyer good enough",
        "useBuyerAddress": True,
        "address": buyer["address"],
        "contact": buyer["contact"],
        "buyer": buyer,
        "account": {
            "id": "ACC-1234-1234",
            "name": "Client Account",
        },
    }


@pytest.fixture()
def listing(buyer):
    return {
        "id": "LST-9401-9279",
        "href": "/listing/LST-9401-9279",
        "priceList": {
            "id": "PRC-9457-4272-3691",
            "href": "/v1/price-lists/PRC-9457-4272-3691",
            "currency": "USD",
        },
        "product": {
            "id": "PRD-1234-1234",
            "name": "Product Name",
        },
        "vendor": {
            "id": "ACC-1234-vendor-id",
            "name": "Vendor Name",
        },
    }


@pytest.fixture()
def template():
    return {
        "id": "TPL-1234-1234-4321",
        "name": "Default Template",
    }


@pytest.fixture()
def agreement(buyer, licensee, listing, seller):
    return {
        "id": "AGR-2119-4550-8674-5962",
        "href": "/commerce/agreements/AGR-2119-4550-8674-5962",
        "icon": None,
        "name": "Product Name 1",
        "audit": {
            "created": {
                "at": CREATED_AT,
                "by": {"id": "USR-0000-0001"},
            },
            "updated": None,
        },
        "subscriptions": [
            {
                "id": "SUB-1000-2000-3000",
                "status": "Active",
                "lines": [
                    {
                        "id": "ALI-0010",
                        "item": {
                            "id": "ITM-1234-1234-1234-0010",
                            "name": "Item 0010",
                            "externalIds": {
                                "vendor": "external-id1",
                            },
                        },
                        "quantity": 10,
                    }
                ],
            },
            {
                "id": "SUB-1234-5678",
                "status": "Terminated",
                "lines": [
                    {
                        "id": "ALI-0011",
                        "item": {
                            "id": "ITM-1234-1234-1234-0011",
                            "name": "Item 0011",
                            "externalIds": {
                                "vendor": "external-id2",
                            },
                        },
                        "quantity": 4,
                    }
                ],
            },
        ],
        "listing": listing,
        "licensee": licensee,
        "buyer": buyer,
        "seller": {
            "id": seller["id"],
            "href": seller["href"],
            "name": seller["name"],
            "icon": seller["icon"],
            "address": {
                "country": "US",
            },
        },
        "product": {
            "id": "PRD-1111-1111",
        },
    }


@pytest.fixture()
def buyer_factory():
    def _factory(id=None, name=None, email=None):
        return {
            "id": id or "BUY-1111-1111",
            "name": name or "A buyer",
            "email": email or "buyer@example.com",
        }

    return _factory


@pytest.fixture()
def order_factory(
    agreement_factory,
    order_parameters_factory,
    fulfillment_parameters_factory,
    lines_factory,
    buyer_factory,
    seller,
    template_factory,
):
    """
    Marketplace platform order for tests.
    """

    def _order(
        order_id="ORD-0792-5000-2253-4210",
        order_type="Purchase",
        order_parameters=None,
        fulfillment_parameters=None,
        lines=None,
        subscriptions=None,
        external_ids=None,
        status=None,
        template=None,
        deployment_id="",
        agreement=None,
        buyer=None,
    ):
        order_parameters = (
            order_parameters_factory() if order_parameters is None else order_parameters
        )
        fulfillment_parameters = (
            fulfillment_parameters_factory()
            if fulfillment_parameters is None
            else fulfillment_parameters
        )
        lines = lines_factory(deployment_id=deployment_id) if lines is None else lines
        subscriptions = [] if subscriptions is None else subscriptions
        agreement = (
            agreement_factory(
                fulfillment_parameters=fulfillment_parameters,
            )
            if agreement is None
            else agreement
        )
        order = {
            "id": order_id,
            "error": None,
            "href": "/commerce/orders/ORD-0792-5000-2253-4210",
            "agreement": agreement,
            "authorization": {
                "id": "AUT-1234-4567",
            },
            "type": order_type,
            "status": status or "Processing",
            "clientReferenceNumber": None,
            "notes": "First order to try",
            "lines": lines,
            "subscriptions": subscriptions,
            "parameters": {
                "fulfillment": fulfillment_parameters,
                "ordering": order_parameters,
            },
            "product": {"id": "PRD-1111-1111", "name": "AWS"},
            "seller": seller,
            "buyer": buyer or buyer_factory(),
            "client": {"id": "CLI-1111-1111"},
            "audit": {
                "created": {
                    "at": CREATED_AT,
                    "by": {"id": "USR-0000-0001"},
                },
                "updated": None,
            },
        }
        if external_ids:
            order["externalIds"] = external_ids

        order["template"] = template or template_factory()
        return order

    return _order


@pytest.fixture()
def mock_order(order_factory):
    return order_factory()


@pytest.fixture()
def buyer():
    return {
        "id": "BUY-3731-7971",
        "href": "/accounts/buyers/BUY-3731-7971",
        "name": "A buyer",
        "icon": "/static/BUY-3731-7971/icon.png",
        "address": {
            "country": "US",
            "state": "CA",
            "city": "San Jose",
            "addressLine1": "3601 Lyon St",
            "addressLine2": "",
            "postCode": "94123",
        },
        "externalIds": {
            "erpCompanyContact": "US-CON-111111",
            "erpCustomer": "US-SCU-111111",
            "accountExternalId": "US-999999",
        },
        "contact": {
            "firstName": "Cic",
            "lastName": "Faraone",
            "email": "francesco.faraone@softwareone.com",
            "phone": {
                "prefix": "+1",
                "number": "4082954078",
            },
        },
    }


@pytest.fixture()
def seller():
    return {
        "id": "SEL-9121-8944",
        "href": "/accounts/sellers/SEL-9121-8944",
        "name": "SWO US",
        "icon": "/static/SEL-9121-8944/icon.png",
        "address": {
            "country": "US",
            "region": "CA",
            "city": "San Jose",
            "addressLine1": "3601 Lyon St",
            "addressLine2": "",
            "postCode": "94123",
        },
        "contact": {
            "firstName": "Francesco",
            "lastName": "Faraone",
            "email": "francesco.faraone@softwareone.com",
            "phone": {
                "prefix": "+1",
                "number": "4082954078",
            },
        },
    }


@pytest.fixture()
def webhook(settings):
    return {
        "id": "WH-123-123",
        "criteria": {"product.id": settings.MPT_PRODUCTS_IDS[0]},
    }


@pytest.fixture()
def mpt_client(settings):
    """
    Create an instance of the MPT client used by the extension.
    """
    settings.MPT_API_BASE_URL = "https://localhost"
    from mpt_extension_sdk.core.utils import setup_client

    return setup_client()


@pytest.fixture()
def mpt_error_factory():
    """
    Generate an error message returned by the Marketplace platform.
    """

    def _mpt_error(
        status,
        title,
        detail,
        trace_id="00-27cdbfa231ecb356ab32c11b22fd5f3c-721db10d009dfa2a-00",
        errors=None,
    ):
        error = {
            "status": status,
            "title": title,
            "detail": detail,
            "traceId": trace_id,
        }
        if errors:
            error["errors"] = errors

        return error

    return _mpt_error


@pytest.fixture()
def airtable_error_factory():
    """
    Generate an error message returned by the Airtable API.
    """

    def _airtable_error(
        message,
        error_type="INVALID_REQUEST_UNKNOWN",
    ):
        error = {
            "error": {
                "type": error_type,
                "message": message,
            }
        }

        return error

    return _airtable_error


@pytest.fixture()
def mpt_list_response():
    def _wrap_response(objects_list):
        return {
            "data": objects_list,
        }

    return _wrap_response


@pytest.fixture()
def jwt_token(settings):
    iat = nbf = int(datetime.now().timestamp())
    exp = nbf + 300
    return jwt.encode(
        {
            "iss": "mpt",
            "aud": "aws.ext.s1.com",
            "iat": iat,
            "nbf": nbf,
            "exp": exp,
            "webhook_id": "WH-123-123",
        },
        get_for_product(settings, "WEBHOOKS_SECRETS", "PRD-1111-1111"),
        algorithm="HS256",
    )


@pytest.fixture()
def config():
    return get_config()


@pytest.fixture()
def extension_settings(settings):
    current_extension_config = copy.copy(settings.EXTENSION_CONFIG)
    yield settings
    settings.EXTENSION_CONFIG = current_extension_config


@pytest.fixture()
def mocked_setup_master_signal_handler():
    signal_handler = signal.getsignal(signal.SIGINT)

    def handler(signum, frame):
        print("Signal handler called with signal", signum)
        signal.signal(signal.SIGINT, signal_handler)

    signal.signal(signal.SIGINT, handler)


@pytest.fixture()
def mock_gradient_result():
    return [
        "#00C9CD",
        "#07B7D2",
        "#0FA5D8",
        "#1794DD",
        "#1F82E3",
        "#2770E8",
        "#2F5FEE",
        "#374DF3",
        "#3F3BF9",
        "#472AFF",
    ]


@pytest.fixture()
def mock_runtime_master_options():
    return {
        "color": True,
        "debug": False,
        "reload": True,
        "component": "all",
    }


@pytest.fixture()
def mock_swoext_commands():
    return (
        "swo.mpt.extensions.runtime.commands.run.run",
        "swo.mpt.extensions.runtime.commands.django.django",
    )


@pytest.fixture()
def mock_dispatcher_event():
    return {
        "type": "event",
        "id": "event-id",
    }


@pytest.fixture()
def mock_workers_options():
    return {
        "color": False,
        "debug": False,
        "reload": False,
        "component": "all",
    }


@pytest.fixture()
def mock_gunicorn_logging_config():
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {
                "format": "{asctime} {name} {levelname} (pid: {process}) {message}",
                "style": "{",
            },
            "rich": {
                "format": "%(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "verbose",
            },
            "rich": {
                "class": "rich.logging.RichHandler",
                "formatter": "rich",
                "log_time_format": lambda x: x.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "rich_tracebacks": True,
            },
        },
        "root": {
            "handlers": ["rich"],
            "level": "INFO",
        },
        "loggers": {
            "gunicorn.access": {
                "handlers": ["rich"],
                "level": "INFO",
                "propagate": False,
            },
            "gunicorn.error": {
                "handlers": ["rich"],
                "level": "INFO",
                "propagate": False,
            },
            "swo.mpt": {},
        },
    }


@pytest.fixture()
def mock_wrap_event():
    return Event("evt-id", "orders", {"id": "ORD-1111-1111-1111"})


@pytest.fixture()
def mock_meta_with_pagination_has_more_pages():
    return {
        META: {
            "pagination": {
                "offset": 0,
                "limit": 10,
                "total": 12,
            },
        },
    }


@pytest.fixture()
def mock_meta_with_pagination_has_no_more_pages():
    return {
        META: {
            "pagination": {
                "offset": 0,
                "limit": 10,
                "total": 4,
            },
        },
    }


@pytest.fixture()
def mock_logging_account_prefixes():
    return ("ACC", "BUY", "LCE", "MOD", "SEL", "USR", "AUSR", "UGR")


@pytest.fixture()
def mock_logging_catalog_prefixes():
    return (
        "PRD",
        "ITM",
        "IGR",
        "PGR",
        "MED",
        "DOC",
        "TCS",
        "TPL",
        "WHO",
        "PRC",
        "LST",
        "AUT",
        "UNT",
    )


@pytest.fixture()
def mock_logging_commerce_prefixes():
    return ("AGR", "ORD", "SUB", "REQ")


@pytest.fixture()
def mock_logging_aux_prefixes():
    return ("FIL", "MSG")


@pytest.fixture()
def mock_logging_all_prefixes(
    mock_logging_account_prefixes,
    mock_logging_catalog_prefixes,
    mock_logging_commerce_prefixes,
    mock_logging_aux_prefixes,
):
    return (
        *mock_logging_account_prefixes,
        *mock_logging_catalog_prefixes,
        *mock_logging_commerce_prefixes,
        *mock_logging_aux_prefixes,
    )


@pytest.fixture()
def mock_highlights(mock_logging_all_prefixes):
    return [
        *_ReprHighlighter.highlights,
        rf"(?P<mpt_id>(?:{'|'.join(mock_logging_all_prefixes)})(?:-\d{{4}})*)",
    ]


@pytest.fixture()
def mock_settings_product_ids():
    return ",".join(settings.MPT_PRODUCTS_IDS)


@pytest.fixture()
def mock_ext_expected_environment_values(
    mock_env_webhook_secret,
):
    return {
        "WEBHOOKS_SECRETS": json.loads(mock_env_webhook_secret),
    }


@pytest.fixture()
def mock_env_webhook_secret():
    return '{ "webhook_secret": "WEBHOOK_SECRET" }'


@pytest.fixture()
def mock_json_ext_variables():
    return {
        "EXT_WEBHOOKS_SECRETS",
    }


@pytest.fixture()
def mock_valid_env_values(
    mock_env_webhook_secret,
):
    return {
        "EXT_WEBHOOKS_SECRETS": mock_env_webhook_secret,
    }


@pytest.fixture()
def mock_worker_initialize(mocker):
    return mocker.patch("swo.mpt.extensions.runtime.workers.initialize")


@pytest.fixture()
def mock_worker_call_command(mocker):
    return mocker.patch("swo.mpt.extensions.runtime.workers.call_command")


@pytest.fixture()
def mock_get_order_for_producer(mock_order, order_factory):
    return {
        "data": [mock_order],
        META: {
            "pagination": {
                "offset": 0,
                "limit": 10,
                "total": 1,
            },
        },
    }


@pytest.fixture()
def aws_client_factory(mocker, settings, requests_mocker):
    def _aws_client(config, mpa_account_id, role_name):
        requests_mocker.post(
            config.ccp_oauth_url, json={"access_token": "test_access_token"}, status=200
        )

        mock_boto3_client = mocker.patch("boto3.client")
        mock_client = mock_boto3_client.return_value
        credentials = {
            "AccessKeyId": "test_access_key",
            "SecretAccessKey": "test_secret_key",
            "SessionToken": "test_session_token",
        }
        mock_client.assume_role_with_web_identity.return_value = {"Credentials": credentials}
        mocker.patch.object(
            CCPClient,
            "get_secret_from_key_vault",
            return_value="client_secret",
        )
        return AWSClient(config, mpa_account_id, role_name), mock_client

    return _aws_client


@pytest.fixture()
def create_account_status(account_creation_status_factory):
    def _create_account(state="IN_PROGRESS", failure_reason="EMAIL_ALREADY_EXISTS"):
        return {
            "CreateAccountStatus": {
                "Id": "account_request_id",
                "AccountName": "account_name",
                "State": state,
                "AccountId": "account_id",
                "FailureReason": failure_reason,
            }
        }

    return _create_account


@pytest.fixture()
def subscription_factory(lines_factory):
    def _subscription(
        name="Subscription for account_name (account_id)",
        account_email=ACCOUNT_EMAIL,
        account_name="account_name",
        vendor_id="account_id",
        status="Active",
        agreement_id="AGR-2119-4550-8674-5962",
        lines=None,
    ):
        if lines is None:
            lines = []
            for sku in AWS_ITEMS_SKUS:
                lines.extend(lines_factory(external_vendor_id=sku, name=sku, quantity=1))
        return {
            "id": "SUB-1000-2000-3000",
            "status": status,
            "name": name,
            "autoRenew": True,
            "agreement": {
                "id": agreement_id,
                "status": "Active",
                "name": "Amazon Web Services",
            },
            "parameters": {
                "fulfillment": [
                    {"externalId": "accountEmail", "value": account_email},
                    {"externalId": "accountName", "value": account_name},
                ]
            },
            "externalIds": {"vendor": vendor_id},
            "lines": lines,
        }

    return _subscription


@pytest.fixture()
def account_creation_status_factory(lines_factory):
    def _account_creation_status(
        account_request_id="account_request_id",
        status="IN_PROGRESS",
        account_name="account_name",
        failure_reason=None,
        account_id=None,
    ):
        return AccountCreationStatus(
            account_id=account_id,
            account_name=account_name,
            account_request_id=account_request_id,
            status=status,
            failure_reason=failure_reason,
        )

    return _account_creation_status


@pytest.fixture()
def data_aws_account_factory():
    def create_aws_account(
        status="ACTIVE",
        id="1234-1234-1234",
        arn="arn",
        email="test@example.com",
        join_method="CREATED",
        name="test_account_name",
    ):
        """
        Factory for AWS account data.

        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/organizations/client/list_accounts.html
        :param status: 'ACTIVE' | 'SUSPENDED' | 'PENDING_CLOSURE'
        :param join_method: 'INVITED' | 'CREATED'
        :param account_id:
        :param arn:
        :param email:
        :return:
        """
        return {
            "Id": id,
            "Arn": arn,
            "Email": email,
            "Name": name,
            "Status": status,
            "JoinedMethod": join_method,
            "JoinedTimestamp": datetime(2015, 1, 1),
        }

    return create_aws_account


@pytest.fixture()
def data_aws_invoice_summary_factory():
    def create_invoice_summary(
        account_id="1234-1234-1234",
        billing_period_month=4,
        billing_period_year=2025,
        total_amount="0.00",
        invoice_entity=INVOICE_ENTITY,
        payment_currency="USD",
        rate="0.88",
        invoice_id="EUINGB25-2163550",
    ):
        return {
            "AccountId": account_id,
            "InvoiceId": invoice_id,
            "Entity": {"InvoicingEntity": invoice_entity},
            "BillingPeriod": {"Month": billing_period_month, "Year": billing_period_year},
            "InvoiceType": "INVOICE",
            "BaseCurrencyAmount": {
                "TotalAmount": total_amount,
                "TotalAmountBeforeTax": "0.00",
                "CurrencyCode": "USD",
            },
            "TaxCurrencyAmount": {
                "TotalAmount": "0.00",
                "TotalAmountBeforeTax": "0.00",
                "CurrencyCode": "GBP",
                "CurrencyExchangeDetails": {
                    "SourceCurrencyCode": "USD",
                    "TargetCurrencyCode": "GBP",
                    "Rate": "0.74897",
                },
            },
            "PaymentCurrencyAmount": {
                "TotalAmount": "0.00",
                "TotalAmountBeforeTax": "0.00",
                "CurrencyCode": payment_currency,
                "CurrencyExchangeDetails": {
                    "SourceCurrencyCode": "USD",
                    "TargetCurrencyCode": payment_currency,
                    "Rate": rate,
                },
            },
        }

    return create_invoice_summary


@pytest.fixture()
def data_aws_cost_and_usage_factory():
    def create_usage_report(
        account_id="1234-1234-1234",
    ):
        return {
            "GroupDefinitions": [
                {"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"},
                {"Type": "DIMENSION", "Key": "INVOICING_ENTITY"},
            ],
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2025-06-01", "End": "2025-07-01"},
                    "Total": {},
                    "Groups": [
                        {
                            "Keys": [account_id, "Amazon Web Services, Inc."],
                            "Metrics": {
                                "UnblendedCost": {"Amount": "31.6706587062", "Unit": "USD"}
                            },
                        },
                        {
                            "Keys": ["123456789012", "Amazon AWS Services Brasil Ltda."],
                            "Metrics": {"UnblendedCost": {"Amount": "0.1471776427", "Unit": "USD"}},
                        },
                    ],
                    "Estimated": False,
                }
            ],
            "DimensionValueAttributes": [
                {"Value": account_id, "Attributes": {"description": "test"}},
                {"Value": "123456789012", "Attributes": {"description": "aws-mpt-0006-0002"}},
            ],
        }

    return create_usage_report


@pytest.fixture()
def order_close_account(
    order_factory,
    order_parameters_factory,
    fulfillment_parameters_factory,
    subscriptions_factory,
    agreement_factory,
):
    order = order_factory(
        order_type=ORDER_TYPE_TERMINATION,
        order_parameters=order_parameters_factory(
            account_email=ACCOUNT_EMAIL,
            account_id="1234-5678",
            termination_type=TerminationParameterChoices.CLOSE_ACCOUNT,
        ),
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.COMPLETED.value),
        subscriptions=subscriptions_factory(
            vendor_id="1234-5678",
            status="Terminating",
        ),
        agreement=agreement_factory(vendor_id="123456789012"),
    )
    return order


@pytest.fixture()
def order_unlink_account(order_factory, order_parameters_factory, subscriptions_factory):
    order = order_factory(
        order_type=ORDER_TYPE_TERMINATION,
        order_parameters=order_parameters_factory(
            account_email=ACCOUNT_EMAIL,
            account_id="1234-5678",
            termination_type=TerminationParameterChoices.UNLINK_ACCOUNT,
        ),
        subscriptions=subscriptions_factory(
            vendor_id="1234-5678",
            status="Terminating",
        ),
    )
    return order


@pytest.fixture()
def order_terminate_without_type(order_factory, order_parameters_factory, subscriptions_factory):
    order = order_factory(
        order_type=ORDER_TYPE_TERMINATION,
        order_parameters=order_parameters_factory(
            account_email=ACCOUNT_EMAIL,
            account_id="1234-5678",
            termination_type="",
        ),
        subscriptions=subscriptions_factory(
            vendor_id="1234-5678",
            status="Terminating",
        ),
    )
    return order


@pytest.fixture()
def order_terminate_with_invalid_terminate_type(
    order_factory, order_parameters_factory, subscriptions_factory
):
    order = order_factory(
        order_type=ORDER_TYPE_TERMINATION,
        order_parameters=order_parameters_factory(
            account_email=ACCOUNT_EMAIL,
            account_id="1234-5678",
            termination_type="invalid_type",
        ),
        subscriptions=subscriptions_factory(
            vendor_id="1234-5678",
            status="Terminating",
        ),
    )
    return order


@pytest.fixture()
def service_request_ticket_factory():
    def create_service_request_ticket(
        ticket_id="CS0000001",
        state="New",
        email="user_email@example.com",
        summary="Ignore this ticket",
        title="MPT - AWS Extension - Test ticket",
        service_type="MarketPlaceServiceActivation",
        sub_service="Service Activation",
        requester="Supplier.Portal",
    ):
        return {
            "id": ticket_id,
            "title": title,
            "requester": requester,
            "serviceType": service_type,
            "summary": summary,
            "externalUserEmail": email,
            "externalUsername": email,
            "state": state,
            "_links": [
                {
                    "href": f"/servicerequests/{ticket_id}",
                    "rel": "self",
                    "method": "GET",
                }
            ],
            "subService": sub_service,
            "globalacademicExtUserId": "notapplicable",
            "additionalInfo": "additionalInfo",
        }

    return create_service_request_ticket


@pytest.fixture()
def order_termination_close_account_multiple(order_close_account, subscriptions_factory):
    order_close_account["subscriptions"] = []
    order_close_account["subscriptions"].append(
        subscriptions_factory(
            subscription_id="SUB-1000-2000-3001",
            vendor_id="000000001",
            status="Terminating",
        )[0],
    )
    order_close_account["subscriptions"].append(
        subscriptions_factory(
            subscription_id="SUB-1000-2000-3002",
            vendor_id="000000002",
            status="Terminating",
        )[0],
    )
    order_close_account["subscriptions"].append(
        subscriptions_factory(
            subscription_id="SUB-1000-2000-3003",
            vendor_id="000000003",
            status="Terminating",
        )[0],
    )
    order_close_account["subscriptions"].append(
        subscriptions_factory(
            subscription_id="SUB-1000-2000-3004",
            vendor_id="000000004",
            status="Active",
        )[0],
    )
    order_close_account["subscriptions"].append(
        subscriptions_factory(
            subscription_id="SUB-1000-2000-3005",
            vendor_id="000000005",
            status="Terminated",
        )[0],
    )
    return order_close_account


@pytest.fixture()
def base_info():
    return AirTableBaseInfo(api_key="api_key", base_id="base_id")


@pytest.fixture()
def mpa_pool_factory(mocker):
    def _mpa_pool(
        account_id="Account Id",
        account_email="test@email.com",
        account_name=ACCOUNT_NAME,
        pls_enabled=True,
        status="Ready",
        agreement_id="",
        client_id="client_id",
        scu="XX-SCU-200500",
        buyer_id="",
        country="US",
    ):
        mpa_pool = mocker.MagicMock()
        mpa_pool.account_id = account_id
        mpa_pool.account_email = account_email
        mpa_pool.account_name = account_name
        mpa_pool.pls_enabled = pls_enabled
        mpa_pool.status = status
        mpa_pool.agreement_id = agreement_id
        mpa_pool.client_id = client_id
        mpa_pool.scu = scu
        mpa_pool.buyer_id = buyer_id
        mpa_pool.country = country

        return mpa_pool

    return _mpa_pool


@pytest.fixture()
def pool_notification_factory(mocker):
    def _pool_notification(
        notification_id=1,
        notification_type=NotificationTypeEnum.WARNING.value,
        pls_enabled=True,
        ticket_id="Ticket Id",
        ticket_state="New",
        status=NotificationStatusEnum.PENDING.value,
        country="US",
    ):
        pool_notification = mocker.MagicMock()
        pool_notification.notification_id = notification_id
        pool_notification.notification_type = notification_type
        pool_notification.pls_enabled = pls_enabled
        pool_notification.ticket_id = ticket_id
        pool_notification.ticket_state = ticket_state
        pool_notification.status = status
        pool_notification.country = country

        return pool_notification

    return _pool_notification


@pytest.fixture()
def service_client(mocker):
    service_client_mock = mocker.Mock(spec=CRMServiceClient)
    mocker.patch(
        "swo_aws_extension.flows.steps.service_crm_steps.get_service_client",
        return_value=service_client_mock,
    )
    return service_client_mock


@pytest.fixture()
def ccp_client(mocker, config, mock_key_vault_secret_value):
    mocker.patch(
        "swo_ccp_client.client.get_openid_token", return_value={"access_token": "test_access_token"}
    )
    mocker.patch.object(
        CCPClient,
        "get_secret_from_key_vault",
        return_value=mock_key_vault_secret_value,
    )
    return CCPClient(config)


@pytest.fixture()
def ccp_client_no_secret(mocker, config):
    mocker.patch(
        "swo_ccp_client.client.get_openid_token", return_value={"access_token": "test_access_token"}
    )
    mocker.patch.object(
        CCPClient,
        "get_secret_from_key_vault",
        return_value=None,
    )
    return CCPClient(config)


@pytest.fixture()
def mock_onboard_customer_response():
    return [
        {
            "id": "73ae391e-69de-472c-8d05-2f7feb173207",
            "link": {
                "href": "https://api-dev.softwareone.cloud/services/aws-essentials/customer/XX-SCU-200500/account/626581064822?api-version=v2"
            },
        },
        {
            "id": "73ae391e-69de-472c-8d05-2f7feb173207",
            "engagement": {
                "href": "https://api-dev.softwareone.cloud/services/aws-essentials/customer/engagement/73ae391e-69de-472c-8d05-2f7feb173207?api-version=v2"
            },
        },
    ]


@pytest.fixture()
def onboard_customer_factory():
    def _onboard_customer(
        feature_pls="enabled",
    ):
        return {
            "customerName": ACCOUNT_NAME,
            "customerSCU": "XX-SCU-200500",
            "accountId": "123456789012",
            "services": {"isManaged": True, "isSamlEnabled": True, "isBillingEnabled": True},
            "featurePLS": feature_pls,
        }

    return _onboard_customer


@pytest.fixture()
def onboard_customer_status_factory():
    def _onboard_customer_status(
        engagement_state="Running",
    ):
        return {
            "engagementId": "73ae391e-69de-472c-8d05-2f7feb173207",
            "numberOfEvents": 1,
            "events": [
                {
                    "eventId": "241d3696-dbde-4877-91ce-0412d8c15ce4",
                    "eventName": "AWS Essentials Onboarding",
                    "numberOfTasks": 11,
                    "tasks": [
                        {
                            "taskId": "b5b7900c-51ad-47b1-a44d-55ee0093aa2a",
                            "taskName": "Notify CDE api",
                            "taskState": "Succeeded",
                            "message": "",
                            "startedAt": 1743768528,
                            "endedAt": 1743768528,
                        },
                        {
                            "taskId": "fe26123f-4e27-4884-b658-b8e5ca880047",
                            "taskName": "Write customer data into database",
                            "taskState": "Succeeded",
                            "message": "",
                            "startedAt": 1743768528,
                            "endedAt": 1743768528,
                        },
                        {
                            "taskId": "fc5047c4-82ad-4292-b0fe-3740d58c2771",
                            "taskName": "Create EntraID Enterprise Application",
                            "taskState": "Succeeded",
                            "message": "",
                            "startedAt": 1743768528,
                            "endedAt": 1743768528,
                        },
                        {
                            "taskId": "59d8ffa7-4a6b-41fd-afc5-6bdb99fa7539",
                            "taskName": "Create EntraID customer groups",
                            "taskState": "Succeeded",
                            "message": "",
                            "startedAt": 1743768528,
                            "endedAt": 1743768528,
                        },
                        {
                            "taskId": "382ef3e4-8067-4e30-b85e-53f91a091e8b",
                            "taskName": "Configure Enterprise Application for SAML federation",
                            "taskState": "Succeeded",
                            "message": "",
                            "startedAt": 1743768557,
                            "endedAt": 1743768557,
                        },
                        {
                            "taskId": "2bcf8889-52b1-4f53-9917-4bd78cb0103c",
                            "taskName": "Probe SAML credentials",
                            "taskState": "Succeeded",
                            "message": "",
                            "startedAt": 1743772412,
                            "endedAt": 1743772412,
                        },
                        {
                            "taskId": "cc1edf34-a5b3-4d30-ade6-2e581d0893aa",
                            "taskName": "Trigger Enterprise Application provisioning job",
                            "taskState": "Succeeded",
                            "message": "",
                            "startedAt": 1743772412,
                            "endedAt": 1743772412,
                        },
                        {
                            "taskId": "8d7db215-ef1e-4570-ac88-d21e9bdfe02b",
                            "taskName": "Create Provisioning job for SAML federation",
                            "taskState": "Succeeded",
                            "message": "",
                            "startedAt": 1743772416,
                            "endedAt": 1743772416,
                        },
                        {
                            "taskId": "b91de185-3a9f-4763-870f-f7ebcd5d78cc",
                            "taskName": "Save AWS Credentials",
                            "taskState": "succeeded",
                            "message": "",
                            "startedAt": 1743772453,
                            "endedAt": 1743772453,
                        },
                        {
                            "taskId": "ec3e7626-036b-4b3d-b31e-39262b779bbc",
                            "taskName": "Assign SAML roles to customer groups",
                            "taskState": "Succeeded",
                            "message": "",
                            "startedAt": 1743772827,
                            "endedAt": 1743772827,
                        },
                        {
                            "taskId": "08db11d3-ef3f-48ed-b068-5838e4b5f8c3",
                            "taskName": "Execute AWS stacks",
                            "taskState": "Succeeded",
                            "message": "Instance 1b0a2452-b2b9-4777-9dfd-9548dbbd3aa7 was"
                            " successfully created",
                            "startedAt": 1743773642,
                            "endedAt": 1743773642,
                        },
                    ],
                    "eventState": "Succeeded",
                    "startedAt": 1743768528,
                    "endedAt": 1743773642,
                }
            ],
            "engagementState": engagement_state,
            "startedAt": 1743768528,
            "endedAt": 1743773642,
        }

    return _onboard_customer_status


@pytest.fixture()
def mock_key_vault_secret_value():
    return "secret-value"


@pytest.fixture()
def mock_mpt_key_vault_name():
    return "test-key-vault-name"


@pytest.fixture()
def mock_valid_access_token_response():
    return {"access_token": "access-token"}


@pytest.fixture()
def mock_oauth_post_url():
    return "https://example.com/oauth2/token"


@pytest.fixture()
def mock_get_secret_response(mock_key_vault_secret_value):
    return {"clientSecret": mock_key_vault_secret_value}


@pytest.fixture()
def mock_token():
    return "test-token"


@pytest.fixture()
def roots_factory():
    def _roots(
        policy_types=None,
    ):
        policy_types = policy_types or []
        return {
            "Roots": [
                {
                    "Id": "root_id",
                    "Arn": "arn:aws:organizations::111111111111:root/o-8ityo3gjdv/root_id",
                    "Name": "Root",
                    "PolicyTypes": policy_types,
                }
            ]
        }

    return _roots


@pytest.fixture()
def handshake_data_factory():
    def _factory(account_id, state):
        return {
            "Id": f"h-{account_id}",
            "Arn": f"arn:aws:organizations::123456789012:handshake/h-{account_id}",
            "Parties": [{"Id": account_id, "Type": "ACCOUNT"}],
            "State": state,
            "RequestedTimestamp": datetime.now(),
            "ExpirationTimestamp": datetime.now() + timedelta(days=15),
            "Action": "INVITE",
            "Resources": [
                {"Type": "MASTER_EMAIL", "Value": "diego@example.com"},
                {"Type": "MASTER_NAME", "Value": "Org Management account"},
                {"Type": "ORGANIZATION_FEATURE_SET", "Value": "FULL"},
            ],
        }

    return _factory


@pytest.fixture()
def aws_accounts_factory():
    def _account(account_id="123456789012", status="ACTIVE", accounts=None):
        if accounts:
            return {"Accounts": accounts}
        return {
            "Accounts": [
                {
                    "Id": account_id,
                    "Name": "Test Account",
                    "Email": "test@example.com",
                    "Status": status,
                }
            ]
        }

    return _account


@pytest.fixture()
def product_items(lines_factory):
    return [
        {
            "id": "ITM-1234-1234-1234-0001",
            "name": sku,
            "externalIds": {
                "vendor": sku,
            },
        }
        for sku in AWS_ITEMS_SKUS
    ]


@pytest.fixture()
def mock_switch_order_status_to_complete(mocker):
    return mocker.patch(
        "swo_aws_extension.flows.order.InitialAWSContext.switch_order_status_to_complete"
    )


@pytest.fixture()
def mock_switch_order_status_to_query(mocker):
    return mocker.patch(
        "swo_aws_extension.flows.order.InitialAWSContext.switch_order_status_to_query"
    )


@pytest.fixture()
def mock_switch_order_status_to_process(mocker):
    return mocker.patch(
        "swo_aws_extension.flows.order.InitialAWSContext.switch_order_status_to_process"
    )


@pytest.fixture()
def mock_update_processing_template(mocker):
    return mocker.patch(
        "swo_aws_extension.flows.order.InitialAWSContext.update_processing_template"
    )


@pytest.fixture()
def template_factory():
    sample_content = (
        "# Sample Template\n\nUse this input box to define your message "
        "against a given order or request type. Think about how you message "
        "can be succinct but informative, think about the tone you would like "
        "to use and the information that’s key for the consumer of such "
        "information in the given context.\n\n## Formatting\n\nMarkdown allows "
        "you to control various aspects of formatting such as:\n\n* Bullets and"
        " numbering\n* Italics and Bold\n* Titles\n* Link embedding\n\n"
        ""
        "## Images or Videos\n\nYou can embed images or videos to these templates "
        "to share richer visual information by inserting the image or video URL."
        ""
        "\n\n## Template Variables\n\nUse the template variables to identify"
        " parameters you wish to embed in this template so for every recipient "
        "of this message the parameter will be used in the given context."
    )

    def _template(
        name=None,
        id=None,
        content=None,
        type=None,
        default=False,
        product=None,
    ):
        return {
            "id": id or "TPL-1975-5250-0018",
            "name": name or "New Linked account",
            "content": content or sample_content,
            "type": type or "OrderCompleted",
            "default": default,
            "product": product
            or {
                "id": "PRD-1975-5250",
                "name": "Amazon Web Services",
                "externalIds": {},
                "icon": "/v1/catalog/products/PRD-1975-5250/icon",
                "status": "Published",
            },
            "audit": {
                "created": {
                    "at": "2025-05-08T16:52:07.136Z",
                    "by": {"id": "USR-2037-8556", "name": "Sandra Tejerina"},
                }
            },
        }

    return _template


@pytest.fixture()
def update_order_side_effect_factory():
    def _factory(base_order):
        def update_order_side_effect(_client, _order_id, **kwargs):
            new_order = copy.deepcopy(base_order)
            new_order.update(kwargs)
            return new_order

        return update_order_side_effect

    return _factory


@pytest.fixture()
def ffc_client_settings(extension_settings):
    extension_settings.EXTENSION_CONFIG["FFC_OPERATIONS_API_BASE_URL"] = "https://local.local"
    extension_settings.EXTENSION_CONFIG["FFC_SUB"] = "FKT-1234"
    extension_settings.EXTENSION_CONFIG["FFC_OPERATIONS_SECRET"] = "1234"

    return extension_settings


@pytest.fixture()
def mock_jwt_encoder(ffc_client_settings):
    def wrapper(now):
        return jwt.encode(
            {
                "sub": ffc_client_settings.EXTENSION_CONFIG["FFC_SUB"],
                "exp": now + timedelta(minutes=5),
                "nbf": now,
                "iat": now,
            },
            ffc_client_settings.EXTENSION_CONFIG["FFC_OPERATIONS_SECRET"],
            algorithm="HS256",
        )

    return wrapper


@pytest.fixture()
def ffc_client(mocker):
    return mocker.Mock()


@pytest.fixture()
def mock_settings(settings):
    settings.EXTENSION_CONFIG = {
        "CRM_API_BASE_URL": "https://api.example.com",
        "CRM_OAUTH_URL": "https://auth.example.com",
        "CRM_CLIENT_ID": "client_id",
        "CRM_CLIENT_SECRET": "client_secret",
        "CRM_AUDIENCE": "audience",
    }
    return settings


@pytest.fixture()
def mock_marketplace_report_group_factory():
    def _marketplace_report_group(
        account_id="1234-1234-1234",
        service_name=SERVICE_NAME,
    ):
        return [
            {
                "Keys": [
                    account_id,
                    service_name,
                ],
                "Metrics": {"UnblendedCost": {"Amount": "100", "Unit": "USD"}},
            },
            {
                "Keys": [account_id, "Tax"],
                "Metrics": {"UnblendedCost": {"Amount": "0", "Unit": "USD"}},
            },
        ]

    return _marketplace_report_group


@pytest.fixture()
def mock_marketplace_report_factory(mock_marketplace_report_group_factory):
    def _marketplace_report(groups=None):
        groups = groups if groups is not None else mock_marketplace_report_group_factory()
        return {
            "GroupDefinitions": [
                {"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"},
                {"Type": "DIMENSION", "Key": "SERVICE"},
            ],
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2025-04-01", "End": "2025-05-01"},
                    "Total": {},
                    "Groups": groups,
                    "Estimated": False,
                }
            ],
        }

    return _marketplace_report


@pytest.fixture()
def mock_invoice_by_service_report_group_factory():
    def _invoice_by_service_report_group(
        service_name="AWS service name", invoice_entity=INVOICE_ENTITY
    ):
        return [
            {
                "Keys": [
                    service_name,
                    invoice_entity,
                ],
                "Metrics": {"UnblendedCost": {"Amount": "718.461", "Unit": "USD"}},
            }
        ]

    return _invoice_by_service_report_group


@pytest.fixture()
def mock_invoice_by_service_report_factory(mock_invoice_by_service_report_group_factory):
    def _invoice_by_service_report(groups=None):
        groups = groups or mock_invoice_by_service_report_group_factory()
        return {
            "GroupDefinitions": [
                {"Type": "DIMENSION", "Key": "SERVICE"},
                {"Type": "DIMENSION", "Key": "INVOICING_ENTITY"},
            ],
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2025-04-01", "End": "2025-05-01"},
                    "Total": {},
                    "Groups": groups,
                    "Estimated": False,
                }
            ],
        }

    return _invoice_by_service_report


@pytest.fixture()
def mock_report_type_and_usage_report_group_factory():
    def _report_type_and_usage_report_group(
        record_type="Usage",
        service_name="AWS service name",
        service_amount="100",
        provider_discount_amount="7",
    ):
        return [
            {
                "Keys": [
                    record_type,
                    service_name,
                ],
                "Metrics": {"UnblendedCost": {"Amount": service_amount, "Unit": "USD"}},
            },
            {
                "Keys": [AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT.value, service_name],
                "Metrics": {"UnblendedCost": {"Amount": provider_discount_amount, "Unit": "USD"}},
            },
        ]

    return _report_type_and_usage_report_group


@pytest.fixture()
def mock_report_type_and_usage_report_factory(mock_report_type_and_usage_report_group_factory):
    def _report_type_and_usage_report(groups=None):
        groups = groups if groups is not None else mock_report_type_and_usage_report_group_factory()
        return {
            "GroupDefinitions": [
                {"Type": "DIMENSION", "Key": "RECORD_TYPE"},
                {"Type": "DIMENSION", "Key": "SERVICE"},
            ],
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2025-04-01", "End": "2025-05-01"},
                    "Total": {},
                    "Groups": groups,
                    "Estimated": False,
                }
            ],
        }

    return _report_type_and_usage_report


def build_usage_metrics(generator, report):
    return {
        UsageMetricTypeEnum.USAGE.value: generator._get_metrics_by_key(
            report, AWSRecordTypeEnum.USAGE.value
        ),
        UsageMetricTypeEnum.SAVING_PLANS.value: generator._get_metrics_by_key(
            report, AWSRecordTypeEnum.SAVING_PLAN_RECURRING_FEE.value
        ),
        UsageMetricTypeEnum.PROVIDER_DISCOUNT.value: generator._get_metrics_by_key(
            report, AWSRecordTypeEnum.SOLUTION_PROVIDER_PROGRAM_DISCOUNT.value
        ),
        UsageMetricTypeEnum.REFUND.value: generator._get_metrics_by_key(
            report, AWSRecordTypeEnum.REFUND.value
        ),
        UsageMetricTypeEnum.SUPPORT.value: generator._get_metrics_by_key(
            report, AWSRecordTypeEnum.SUPPORT.value
        ),
        UsageMetricTypeEnum.RECURRING.value: generator._get_metrics_by_key(
            report, AWSRecordTypeEnum.RECURRING.value
        ),
    }


def get_usage_data(
    generator,
    report_factory,
    group_factory,
    mock_invoice_by_service_report_group_factory,
):
    group_params = [
        {
            "service_name": "Usage service",
            "record_type": AWSRecordTypeEnum.USAGE.value,
            "service_amount": "100",
            "provider_discount_amount": "7",
        },
        {
            "service_name": "Usage service incentivate",
            "record_type": AWSRecordTypeEnum.USAGE.value,
            "service_amount": "100",
            "provider_discount_amount": "12",
        },
        {
            "service_name": "Saving plan service",
            "record_type": AWSRecordTypeEnum.SAVING_PLAN_RECURRING_FEE.value,
            "service_amount": "100",
            "provider_discount_amount": "7",
        },
        {
            "service_name": "Saving plan service incentivate",
            "record_type": AWSRecordTypeEnum.SAVING_PLAN_RECURRING_FEE.value,
            "service_amount": "100",
            "provider_discount_amount": "12",
        },
        {
            "service_name": "Other AWS services",
            "record_type": AWSRecordTypeEnum.USAGE.value,
            "service_amount": "100",
            "provider_discount_amount": "0",
        },
        {
            "service_name": "free_aws-services",
            "record_type": AWSRecordTypeEnum.USAGE.value,
            "service_amount": "0",
            "provider_discount_amount": "0",
        },
        {
            "service_name": "Refund service business",
            "record_type": AWSRecordTypeEnum.REFUND.value,
            "service_amount": "7",
            "provider_discount_amount": "0",
        },
        {
            "service_name": "Refund service enterprise",
            "record_type": AWSRecordTypeEnum.REFUND.value,
            "service_amount": "35",
            "provider_discount_amount": "0",
        },
        {
            "service_name": "AWS Support (Business)",
            "record_type": AWSRecordTypeEnum.SUPPORT.value,
            "service_amount": "100",
            "provider_discount_amount": "7",
        },
        {
            "service_name": "AWS Support (Development)",
            "record_type": AWSRecordTypeEnum.SUPPORT.value,
            "service_amount": "100",
            "provider_discount_amount": "0",
        },
        {
            "service_name": "AWS Support (Enterprise)",
            "record_type": AWSRecordTypeEnum.SUPPORT.value,
            "service_amount": "100",
            "provider_discount_amount": "35",
        },
        {
            "service_name": AWSServiceEnum.TAX.value,
            "record_type": AWSRecordTypeEnum.USAGE.value,
            "service_amount": "100",
            "provider_discount_amount": "0",
        },
        {
            "service_name": "Upfront service",
            "record_type": AWSRecordTypeEnum.RECURRING.value,
            "service_amount": "100",
            "provider_discount_amount": "7",
        },
        {
            "service_name": "Upfront service incentivate",
            "record_type": AWSRecordTypeEnum.RECURRING.value,
            "service_amount": "100",
            "provider_discount_amount": "12",
        },
    ]
    all_groups = []
    usage_invoice_groups = []
    for params in group_params:
        all_groups += group_factory(**params)
        usage_invoice_groups.extend(
            mock_invoice_by_service_report_group_factory(params["service_name"])
        )
    report = report_factory(groups=all_groups)["ResultsByTime"]
    usage_metrics = build_usage_metrics(generator, report)
    return usage_metrics, usage_invoice_groups


@pytest.fixture()
def mock_journal_args(
    mpt_client,
    config,
    mock_report_type_and_usage_report_group_factory,
    mock_report_type_and_usage_report_factory,
    mock_marketplace_report_group_factory,
    mock_marketplace_report_factory,
    mock_invoice_by_service_report_group_factory,
    mock_invoice_by_service_report_factory,
):
    def _journal_args(item_external_id):
        account_id = "1234567890"
        generator = BillingJournalGenerator(
            mpt_client,
            config,
            2024,
            5,
            ["prod1"],
            billing_journal_processor=get_journal_processors(config),
            authorizations=["AUTH-1"],
        )
        account_metrics, usage_invoice_report = get_usage_data(
            generator,
            mock_report_type_and_usage_report_factory,
            mock_report_type_and_usage_report_group_factory,
            mock_invoice_by_service_report_group_factory,
        )

        groups = mock_marketplace_report_group_factory(
            account_id=account_id, service_name="Marketplace service"
        )
        report = mock_marketplace_report_factory(groups=groups)["ResultsByTime"]
        account_metrics[UsageMetricTypeEnum.MARKETPLACE.value] = generator._get_metrics_by_key(
            report, account_id
        )
        marketplace_invoice_report = mock_invoice_by_service_report_group_factory(SERVICE_NAME)

        service_invoice_entity = mock_invoice_by_service_report_factory(
            marketplace_invoice_report + usage_invoice_report
        )["ResultsByTime"]

        account_metrics[UsageMetricTypeEnum.SERVICE_INVOICE_ENTITY.value] = (
            generator._get_invoice_entity_by_service(service_invoice_entity)
        )
        return {
            "account_id": account_id,
            "item_external_id": item_external_id,
            "account_metrics": account_metrics,
            "journal_details": {
                "agreement_id": "AGR-2119-4550-8674-5962",
                "mpa_id": "mpa_id",
                "start_date": "2025-01-01",
                "end_date": "2025-02-01",
            },
            "account_invoices": {
                "base_total_amount": Decimal("11.34"),
                "base_total_amount_before_tax": Decimal("10.49"),
                "invoice_entities": {
                    INVOICE_ENTITY: {
                        "base_currency_code": "USD",
                        "exchange_rate": Decimal("0.0"),
                        "invoice_id": "EUINGB25-2163550",
                        "payment_currency_code": "USD",
                    }
                },
                "payment_currency_total_amount": Decimal("11.34"),
                "payment_currency_total_amount_before_tax": Decimal("10.49"),
            },
        }

    return _journal_args


@pytest.fixture()
def mock_journal_line_factory():
    def _journal_line(
        service_name="service name",
        account_id="1234567890",
        invoice_entity=INVOICE_ENTITY,
        invoice_id="EUINGB25-2163550",
        item_external_id="",
        error=None,
        price=Decimal(100),
    ):
        return JournalLine(
            description=Description(
                value1=service_name,
                value2=f"{account_id}/{invoice_entity}",
            ),
            external_ids=ExternalIds(
                invoice=invoice_id,
                reference="AGR-2119-4550-8674-5962",
                vendor="mpa_id",
            ),
            period=Period(
                start="2025-01-01",
                end="2025-02-01",
            ),
            price=Price(
                pp_x1=price,
                unit_pp=price,
            ),
            quantity=1,
            search=Search(
                item=SearchItem(
                    criteria="item.externalIds.vendor",
                    value=item_external_id,
                ),
                subscription=SearchSubscription(
                    criteria="subscription.externalIds.vendor",
                    value=account_id,
                ),
            ),
            segment="COM",
            error=error,
        )

    return _journal_line
