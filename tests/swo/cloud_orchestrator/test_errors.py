from http import HTTPStatus

import pytest

from swo_aws_extension.swo.cloud_orchestrator.errors import (
    FACTS_RESPONSE_LIMIT,
    MESSAGE_RESPONSE_LIMIT,
    CloudOrchestratorConnectionError,
    CloudOrchestratorError,
    CloudOrchestratorHttpError,
)


@pytest.fixture
def request_context():
    return {
        "operation": "upgrade",
        "method": "POST",
        "endpoint": "api/v1/marketplace/upgrade",
        "payload": {"scu": "DM-SCU-000000", "master_payer_id": "104688972956"},
    }


def test_title_names_the_operation(request_context):
    error = CloudOrchestratorError("request not completed", **request_context)

    result = error.title

    assert result == "Cloud Orchestrator upgrade failed"


def test_message_holds_reason_request_status_and_response(cloud_orchestrator_error):
    result = cloud_orchestrator_error.message

    assert result == (
        "Cloud Orchestrator upgrade failed: response has an empty 'executions' list "
        '(POST api/v1/marketplace/upgrade, HTTP 200, response: {"executions": []})'
    )


def test_message_without_response(request_context):
    error = CloudOrchestratorConnectionError("request not completed: timeout", **request_context)

    result = error.message

    assert result == (
        "Cloud Orchestrator upgrade failed: request not completed: timeout "
        "(POST api/v1/marketplace/upgrade)"
    )


def test_message_cuts_long_response(request_context):
    kept_response = "x" * MESSAGE_RESPONSE_LIMIT
    error = CloudOrchestratorHttpError(
        "error status returned",
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        response_body=f"{kept_response}y",
        **request_context,
    )

    result = error.message

    assert result.endswith(f"response: {kept_response}... (truncated))")


def test_str_is_message(cloud_orchestrator_error):
    result = str(cloud_orchestrator_error)

    assert result == cloud_orchestrator_error.message


def test_facts_hold_request_and_response(cloud_orchestrator_error):
    result = cloud_orchestrator_error.facts

    assert result == {
        "Operation": "upgrade",
        "Request": "POST api/v1/marketplace/upgrade",
        "Payload": '{"scu": "DM-SCU-000000", "master_payer_id": "104688972956"}',
        "HTTP status": "200",
        "Response": '{"executions": []}',
    }


def test_facts_mark_missing_values():
    error = CloudOrchestratorConnectionError(
        "request not completed",
        operation="deployment status check",
        method="GET",
        endpoint="api/v1/deployments/execution-arn/arn",
    )

    result = error.facts

    assert result == {
        "Operation": "deployment status check",
        "Request": "GET api/v1/deployments/execution-arn/arn",
        "Payload": "-",
        "HTTP status": "-",
        "Response": "-",
    }


def test_facts_cut_long_response(request_context):
    kept_response = "x" * FACTS_RESPONSE_LIMIT
    error = CloudOrchestratorHttpError(
        "error status returned",
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        response_body=f"{kept_response}y",
        **request_context,
    )

    result = error.facts["Response"]

    assert result == f"{kept_response}... (truncated)"


def test_http_error_keeps_status_code_and_response_content(request_context):
    error = CloudOrchestratorHttpError(
        "error status returned",
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        response_body="boom",
        **request_context,
    )

    result = (error.status_code, error.response_content)

    assert result == (HTTPStatus.INTERNAL_SERVER_ERROR, "boom")
