from django.core.management import call_command

from swo_aws_extension.flows.jobs.query_order_processor import process_query_orders


def test_order_process_aws_invitations(mocker):
    mocked_handle = mocker.patch(
        "swo_aws_extension.management.commands.order_querying_processor.process_query_orders",
        side_effect=mocker.MagicMock(spec=process_query_orders),
    )
    mocked_handle.return_value = None

    call_command("order_querying_processor")  # act

    mocked_handle.assert_called_once()
