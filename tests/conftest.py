import copy
import json
import signal
from datetime import UTC, datetime

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
    AccountTypesEnum,
    PhasesEnum,
    SupportTypesEnum,
    TerminationParameterChoices,
)
from swo_aws_extension.parameters import FulfillmentParametersEnum, OrderParametersEnum

PARAM_COMPANY_NAME = "ACME Inc"
AWESOME_PRODUCT = "Awesome product"
CREATED_AT = "2023-12-14T18:02:16.9359"
META = "$meta"
ACCOUNT_EMAIL = "test@aws.com"


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
        account_type=AccountTypesEnum.NEW_ACCOUNT,
        account_id="account_id",
        termination_type=TerminationParameterChoices.CLOSE_ACCOUNT,
        support_type=SupportTypesEnum.PARTNER_LED_SUPPORT,
        transfer_type=None,
    ):
        return [
            {
                "id": "PAR-1234-5678",
                "name": "AWS account email",
                "externalId": OrderParametersEnum.ROOT_ACCOUNT_EMAIL,
                "type": "SingleLineText",
                "value": account_email,
                "constraints": constraints,
            },
            {
                "id": "PAR-1234-5679",
                "name": "Account Name",
                "externalId": OrderParametersEnum.ACCOUNT_NAME,
                "type": "SingleLineText",
                "value": account_name,
                "constraints": constraints,
            },
            {
                "id": "PAR-1234-5680",
                "name": "Account type",
                "externalId": OrderParametersEnum.ACCOUNT_TYPE,
                "type": "choice",
                "value": account_type,
                "constraints": constraints,
            },
            {
                "id": "PAR-1234-5681",
                "name": "Account ID",
                "externalId": OrderParametersEnum.ACCOUNT_ID,
                "type": "SingleLineText",
                "value": account_id,
                "constraints": constraints,
            },
            {
                "id": "PAR-1234-5678",
                "name": "Account Termination Type",
                "externalId": OrderParametersEnum.TERMINATION,
                "type": "Choice",
                "value": termination_type,
            },
            {
                "id": "PAR-1234-5679",
                "name": "Support Type",
                "externalId": OrderParametersEnum.SUPPORT_TYPE,
                "type": "Chice",
                "value": support_type,
            },
            {
                "id": "PAR-1234-5680",
                "name": "Transfer Type",
                "externalId": OrderParametersEnum.TRANSFER_TYPE,
                "type": "Choice",
                "value": transfer_type,
            },
        ]

    return _order_parameters


@pytest.fixture()
def fulfillment_parameters_factory():
    def _fulfillment_parameters(
        mpa_account_id="123456789012", phase="", account_request_id="", crm_ticket_id=""
    ):
        return [
            {
                "id": "PAR-1234-5677",
                "name": "MPA account ID",
                "externalId": FulfillmentParametersEnum.MPA_ACCOUNT_ID,
                "type": "SingleLineText",
                "value": mpa_account_id,
            },
            {
                "id": "PAR-1234-5678",
                "name": "Phase",
                "externalId": FulfillmentParametersEnum.PHASE,
                "type": "Dropdown",
                "value": phase,
            },
            {
                "id": "PAR-1234-5679",
                "name": "Account Request ID",
                "externalId": FulfillmentParametersEnum.ACCOUNT_REQUEST_ID,
                "type": "SingleLineText",
                "value": account_request_id,
            },
            {
                "id": "PAR-1234-5678",
                "name": "CRM Ticket ID",
                "externalId": FulfillmentParametersEnum.CRM_TICKET_ID,
                "type": "SingleLineText",
                "value": crm_ticket_id,
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
        external_vendor_id="65304578CA",
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
        lines = lines_factory() if lines is None else lines
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
def order_factory(
    agreement,
    order_parameters_factory,
    fulfillment_parameters_factory,
    lines_factory,
    status="Processing",
    deployment_id="",
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
        status=status,
        template=None,
        deployment_id=deployment_id,
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

        order = {
            "id": order_id,
            "error": None,
            "href": "/commerce/orders/ORD-0792-5000-2253-4210",
            "agreement": agreement,
            "authorization": {
                "id": "AUT-1234-4567",
            },
            "type": order_type,
            "status": status,
            "clientReferenceNumber": None,
            "notes": "First order to try",
            "lines": lines,
            "subscriptions": subscriptions,
            "parameters": {
                "fulfillment": fulfillment_parameters,
                "ordering": order_parameters,
            },
            "product": {"id": "PRD-1111-1111", "name": "AWS"},
            "seller": {"id": "SEL-1111-1111"},
            "buyer": {"id": "BUY-1111-1111"},
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
        if template:
            order["template"] = template
        return order

    return _order


@pytest.fixture()
def order(order_factory):
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
    return _ReprHighlighter.highlights + [
        rf"(?P<mpt_id>(?:{'|'.join(mock_logging_all_prefixes)})(?:-\d{{4}})*)"
    ]


@pytest.fixture()
def mock_settings_product_ids():
    return ",".join(settings.MPT_PRODUCTS_IDS)


@pytest.fixture()
def mock_ext_expected_environment_values(
    mock_env_webhook_secret,
    mock_email_notification_sender,
):
    return {
        "WEBHOOKS_SECRETS": json.loads(mock_env_webhook_secret),
        "EMAIL_NOTIFICATION_SENDER": mock_email_notification_sender,
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
def mock_email_notification_sender():
    return "email_sender"


@pytest.fixture()
def mock_valid_env_values(
    mock_env_webhook_secret,
    mock_email_notification_sender,
):
    return {
        "EXT_WEBHOOKS_SECRETS": mock_env_webhook_secret,
        "EXT_EMAIL_NOTIFICATION_SENDER": mock_email_notification_sender,
    }


@pytest.fixture()
def mock_worker_initialize(mocker):
    return mocker.patch("swo.mpt.extensions.runtime.workers.initialize")


@pytest.fixture()
def mock_worker_call_command(mocker):
    return mocker.patch("swo.mpt.extensions.runtime.workers.call_command")


@pytest.fixture()
def mock_get_order_for_producer(order, order_factory):
    return {
        "data": [order],
        META: {
            "pagination": {
                "offset": 0,
                "limit": 10,
                "total": 1,
            },
        },
    }


@pytest.fixture()
def aws_client_factory(mocker, requests_mocker):
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
        name="Subscription for account_id",
        account_email=ACCOUNT_EMAIL,
        account_name="account_name",
        vendor_id="account_id",
    ):
        return {
            "id": "SUB-1000-2000-3000",
            "name": name,
            "parameters": {
                "fulfillment": [
                    {"externalId": "accountEmail", "value": account_email},
                    {"externalId": "accountName", "value": account_name},
                ]
            },
            "externalIds": {"vendor": vendor_id},
            "lines": [{"id": "ALI-2119-4550-8674-5962-0001"}],
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
def order_close_account(
    order_factory,
    order_parameters_factory,
    fulfillment_parameters_factory,
    subscriptions_factory,
):
    order = order_factory(
        order_type=ORDER_TYPE_TERMINATION,
        order_parameters=order_parameters_factory(
            account_email=ACCOUNT_EMAIL,
            account_id="1234-5678",
            termination_type=TerminationParameterChoices.CLOSE_ACCOUNT,
        ),
        fulfillment_parameters=fulfillment_parameters_factory(phase=PhasesEnum.COMPLETED),
        subscriptions=subscriptions_factory(
            vendor_id="1234-5678",
            status="Terminating",
        ),
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
def mpa_pool(mocker):
    mpa_pool = mocker.MagicMock()
    mpa_pool.account_id = "Account Id"
    mpa_pool.account_email = "test@email.com"
    mpa_pool.account_name = "Account Name"
    mpa_pool.pls_enabled = True
    mpa_pool.status = "Ready"
    mpa_pool.agreement_id = ""
    mpa_pool.client_id = ""
    mpa_pool.scu = ""

    return mpa_pool


@pytest.fixture()
def pool_notification(mocker):
    pool_notification = mocker.MagicMock()
    pool_notification.notification_id = 1
    pool_notification.notification_type = NotificationTypeEnum.WARNING
    pool_notification.pls_enabled = True
    pool_notification.ticket_id = "Ticket Id"
    pool_notification.ticket_status = "Ticket Status"
    pool_notification.status = NotificationStatusEnum.IN_PROGRESS

    return pool_notification
