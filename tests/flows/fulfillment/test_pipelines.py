from swo_aws_extension.flows.fulfillment import pipelines


def test_purchase_new_steps():
    expected_step_classes = ["SetupPurchaseContext", "AssignPMA"]

    result = [step.__class__.__name__ for step in pipelines.purchase_new_aws_environment.queue]

    assert result == expected_step_classes


def test_purchase_existing_steps():
    expected_step_classes = ["SetupPurchaseContext", "AssignPMA"]

    result = [step.__class__.__name__ for step in pipelines.purchase_new_aws_environment.queue]

    assert result == expected_step_classes
