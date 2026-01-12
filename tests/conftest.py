import copy
import datetime as dt
from http import HTTPStatus

import jwt
import pytest
import responses
from django.test import override_settings
from mpt_extension_sdk.runtime.djapp.conf import get_for_product

from swo_aws_extension.aws.client import AWSClient
from swo_aws_extension.aws.config import get_config
from swo_aws_extension.constants import (
    AccountTypesEnum,
    AwsTypeOfSupportEnum,
    FulfillmentParametersEnum,
    OrderParametersEnum,
    SupportTypesEnum,
)
from swo_aws_extension.swo.ccp.client import CCPClient

PARAM_COMPANY_NAME = "ACME Inc"
AWESOME_PRODUCT = "Awesome product"
CREATED_AT = "2023-12-14T18:02:16.9359"
META = "$meta"
ACCOUNT_EMAIL = "test@aws.com"
ACCOUNT_NAME = "Account Name"
SERVICE_NAME = "Marketplace service"
INVOICE_ENTITY = "Amazon Web Services EMEA SARL"
TOKEN_EXP_SECONDS = 300


@pytest.fixture
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
                                "vendor": "225989344502",
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
                                "vendor": "225989344502",
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
        "externalIds": {
            "vendor": "225989344502",
        },
        "authorization": {
            "externalIds": {
                "operations": "651706759263",
            },
        },
        "parameters": {
            "ordering": [],
            "fulfillment": [
                {"externalId": "responsibilityTransferId", "value": "rt-8lr3q6sn"},
                {"externalId": "pmAccountId", "value": "651706759263"},
            ],
        },
    }


@pytest.fixture
def agreement_factory(buyer, order_parameters_factory, fulfillment_parameters_factory, seller):
    def _agreement(
        licensee_name="My beautiful licensee",
        licensee_address=None,
        licensee_contact=None,
        subscriptions=None,
        fulfillment_parameters=None,
        ordering_parameters=None,
        lines=None,
        vendor_id="225989344502",
        pma_account_id="651706759263",
        *,
        use_buyer_address=False,
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
            "authorization": {
                "id": "AUT-1234-5678",
                "externalIds": {
                    "operations": pma_account_id,
                },
            },
            "lines": lines or [],
            "subscriptions": subscriptions,
            "parameters": {
                "ordering": ordering_parameters or order_parameters_factory(),
                "fulfillment": fulfillment_parameters_factory()
                if fulfillment_parameters is None
                else fulfillment_parameters,
            },
            "externalIds": {"vendor": vendor_id},
        }

    return _agreement


@pytest.fixture(autouse=True)
def force_test_settings():
    with override_settings(DJANGO_SETTINGS_MODULE="tests.django.settings"):
        yield


@pytest.fixture
def aws_client_factory(mocker, settings, requests_mocker):
    def factory(config, mpa_account_id, role_name):
        requests_mocker.post(
            config.ccp_oauth_url, json={"access_token": "test_access_token"}, status=HTTPStatus.OK
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

    return factory


@pytest.fixture
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


@pytest.fixture
def buyer_factory():
    def factory(buyer_id=None, name=None, email=None):
        return {
            "id": buyer_id or "BUY-1111-1111",
            "name": name or "A buyer",
            "email": email or "buyer@example.com",
        }

    return factory


@pytest.fixture
def ccp_client(mocker, config, mock_key_vault_secret_value):
    mocker.patch(
        "swo_aws_extension.swo.ccp.client.get_openid_token",
        return_value={"access_token": "test_access_token"},
    )
    mocker.patch.object(
        CCPClient,
        "get_secret_from_key_vault",
        return_value=mock_key_vault_secret_value,
    )
    return CCPClient(config)


@pytest.fixture
def ccp_client_no_secret(mocker, config):
    mocker.patch(
        "swo_aws_extension.swo.ccp.client.get_openid_token",
        return_value={"access_token": "test_access_token"},
    )
    mocker.patch.object(
        CCPClient,
        "get_secret_from_key_vault",
        return_value=None,
    )
    return CCPClient(config)


@pytest.fixture
def config():
    return get_config()


@pytest.fixture
def dummy_constraints():
    return {"hidden": True, "readonly": False, "required": False}


@pytest.fixture
def data_aws_cost_and_usage_factory():
    def factory(
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

    return factory


@pytest.fixture
def fulfillment_parameters_factory():
    def factory(
        phase="",
        responsibility_transfer_id="rt-8lr3q6sn",
        crm_onboard_ticket_id="",
        crm_new_account_ticket_id="",
        crm_customer_role_ticket_id="",
        customer_roles_deployed="no",
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
                "externalId": FulfillmentParametersEnum.RESPONSIBILITY_TRANSFER_ID.value,
                "value": responsibility_transfer_id,
            },
            {
                "externalId": FulfillmentParametersEnum.CRM_ONBOARD_TICKET_ID.value,
                "value": crm_onboard_ticket_id,
            },
            {
                "externalId": FulfillmentParametersEnum.CRM_NEW_ACCOUNT_TICKET_ID.value,
                "value": crm_new_account_ticket_id,
            },
            {
                "externalId": FulfillmentParametersEnum.CRM_CUSTOMER_ROLE_TICKET_ID.value,
                "value": crm_customer_role_ticket_id,
            },
            {
                "externalId": FulfillmentParametersEnum.CUSTOMER_ROLES_DEPLOYED.value,
                "value": customer_roles_deployed,
            },
        ]

    return factory


@pytest.fixture
def jwt_token(settings):
    now_ts = int(dt.datetime.now(tz=dt.UTC).timestamp())
    iat = now_ts
    nbf = now_ts
    exp = nbf + TOKEN_EXP_SECONDS
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


@pytest.fixture
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


@pytest.fixture
def lines_factory(agreement, deployment_id=None):
    agreement_id = agreement["id"].split("-", 1)[1]

    def factory(
        line_id=1,
        item_id=1,
        name=AWESOME_PRODUCT,
        old_quantity=0,
        quantity=170,
        external_vendor_id="USAGE",
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

    return factory


@pytest.fixture
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


@pytest.fixture
def mock_app_insights_instrumentation_key():
    return "12345678-1234-1234-1234-123456789012"


@pytest.fixture
def mock_get_secret_response(mock_key_vault_secret_value):
    return {"clientSecret": mock_key_vault_secret_value}


@pytest.fixture
def mock_key_vault_secret_value():
    return "secret-value"


@pytest.fixture
def mock_token():
    return "test-token"


@pytest.fixture
def mpt_client(settings):
    settings.MPT_API_BASE_URL = "https://localhost"
    from mpt_extension_sdk.core.utils import setup_client  # noqa: PLC0415

    return setup_client()


@pytest.fixture
def mpt_error_factory():
    def factory(
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

    return factory


@pytest.fixture
def order_parameters_factory(dummy_constraints):
    def factory(
        account_type=AccountTypesEnum.NEW_AWS_ENVIRONMENT.value,
        mpa_id="651706759263",
        constraints=None,
        support_type=SupportTypesEnum.PARTNER_LED_SUPPORT.value,
        aws_type_of_support=AwsTypeOfSupportEnum.ENTERPRISE_SUPPORT.value,
    ):
        return [
            {
                "id": "PAR-1234-5680",
                "name": "Account type",
                "externalId": OrderParametersEnum.ACCOUNT_TYPE.value,
                "type": "choice",
                "value": account_type,
            },
            {
                "id": "PAR-1234-5680",
                "name": "Master Payer Account ID",
                "externalId": OrderParametersEnum.MASTER_PAYER_ACCOUNT_ID.value,
                "type": "choice",
                "value": mpa_id,
                "constraints": constraints.copy() if constraints else dummy_constraints.copy(),
            },
            {
                "id": "PAR-1234-5680",
                "name": "Order Account Name",
                "externalId": OrderParametersEnum.ORDER_ACCOUNT_NAME.value,
                "type": "choice",
                "value": "Order Account Name",
                "constraints": constraints.copy() if constraints else dummy_constraints.copy(),
            },
            {
                "id": "PAR-1234-5680",
                "name": "Order Root Account Email",
                "externalId": OrderParametersEnum.ORDER_ACCOUNT_EMAIL.value,
                "type": "choice",
                "value": "example@example.com",
                "constraints": constraints.copy() if constraints else dummy_constraints.copy(),
            },
            {
                "id": "PAR-1234-5681",
                "name": "Support type",
                "externalId": OrderParametersEnum.SUPPORT_TYPE.value,
                "type": "choice",
                "value": support_type,
                "constraints": constraints.copy() if constraints else dummy_constraints.copy(),
            },
            {
                "id": "PAR-1234-5682",
                "name": "AWS type of support",
                "externalId": OrderParametersEnum.AWS_TYPE_OF_SUPPORT.value,
                "type": "choice",
                "value": aws_type_of_support,
                "constraints": constraints.copy() if constraints else dummy_constraints.copy(),
            },
        ]

    return factory


@pytest.fixture
def order_factory(
    agreement_factory,
    order_parameters_factory,
    fulfillment_parameters_factory,
    lines_factory,
    buyer_factory,
    seller,
    template_factory,
):
    def factory(
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
        authorization_external_id="123456789012",
    ):
        order_parameters = (
            order_parameters_factory() if order_parameters is None else order_parameters
        )
        fulfillment_parameters = (
            fulfillment_parameters_factory()
            if fulfillment_parameters is None
            else fulfillment_parameters
        )
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
                "externalIds": {
                    "operations": authorization_external_id,
                },
            },
            "type": order_type,
            "status": status or "Processing",
            "clientReferenceNumber": None,
            "notes": "First order to try",
            "lines": lines_factory(deployment_id=deployment_id) if lines is None else lines,
            "subscriptions": [] if subscriptions is None else subscriptions,
            "parameters": {
                "fulfillment": fulfillment_parameters,
                "ordering": order_parameters,
            },
            "product": {"id": "PRD-1111-1111", "name": "AWS"},
            "seller": seller,
            "buyer": buyer or buyer_factory(),
            "client": {"id": "CLI-1111-1111"},
            "licensee": {"id": "LCE-1111-2222"},
            "vendor": {"id": "VEN-1111-2222", "name": "Vendor Name"},
            "audit": {
                "created": {
                    "at": CREATED_AT,
                    "by": {"id": "USR-0000-0001"},
                },
                "updated": {
                    "at": CREATED_AT,
                    "by": {"id": "USR-0000-0001", "name": "John Doe"},
                },
            },
        }
        if external_ids:
            order["externalIds"] = external_ids

        order["template"] = template or template_factory()
        return order

    return factory


@pytest.fixture
def requests_mocker():
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture
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


@pytest.fixture
def template_factory():
    sample_content = (
        "# Sample Template\n\nUse this input box to define your message "
        "against a given order or request type. Think about how you message "
        "can be succinct but informative, think about the tone you would like "
        "to use and the information that's key for the consumer of such "
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

    def factory(
        name=None,
        template_id=None,
        content=None,  # noqa: WPS110
        template_type=None,
        product=None,
        *,
        default=False,
    ):
        return {
            "id": template_id or "TPL-1975-5250-0018",
            "name": name or "New Linked account",
            "content": content or sample_content,
            "type": template_type or "OrderCompleted",
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

    return factory


@pytest.fixture
def webhook(settings):
    return {
        "id": "WH-123-123",
        "criteria": {"product.id": settings.AWS_PRODUCT_ID},
    }


@pytest.fixture
def mock_get_webhook(mocker, webhook):
    return mocker.patch("swo_aws_extension.extension.get_webhook", return_value=webhook, spec=True)


@pytest.fixture
def extension_settings(settings):
    current_extension_config = copy.copy(settings.EXTENSION_CONFIG)
    yield settings
    settings.EXTENSION_CONFIG = current_extension_config


@pytest.fixture
def ffc_client_settings(extension_settings):
    extension_settings.EXTENSION_CONFIG["FFC_OPERATIONS_API_BASE_URL"] = "https://local.local"
    extension_settings.EXTENSION_CONFIG["FFC_SUB"] = "FKT-1234"
    extension_settings.EXTENSION_CONFIG["FFC_OPERATIONS_SECRET"] = "1234"

    return extension_settings


@pytest.fixture
def mock_update_parameters_visibility(mocker):
    return mocker.patch("swo_aws_extension.extension.update_parameters_visibility", spec=True)
