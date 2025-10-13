from swo_aws_extension.flows.fulfillment import pipelines


def test_purchase_pipeline_steps():
    expected_step_classes = [
        "SetupPurchaseContext",
        "AssignMPA",
        "MPAPreConfiguration",
        "CreateInitialLinkedAccountStep",
        "CreateSubscription",
        "CCPOnboard",
        "CreateFinOpsMPAEntitlementStep",
        "CreateFinOpsEntitlementStep",
        "CreateUpdateKeeperTicketStep",
        "CreateOnboardTicketStep",
        "CompletePurchaseOrderStep",
    ]

    actual_step_classes = [step.__class__.__name__ for step in pipelines.purchase.queue]

    assert actual_step_classes == expected_step_classes


def test_purchase_split_billing_pipeline_steps():
    expected_step_classes = [
        "SetupPurchaseContext",
        "AssignSplitBillingMPA",
        "CreateInitialLinkedAccountStep",
        "CreateSubscription",
        "CreateFinOpsEntitlementStep",
        "CompletePurchaseOrderStep",
    ]

    actual_step_classes = [
        step.__class__.__name__ for step in pipelines.purchase_split_billing.queue
    ]

    assert actual_step_classes == expected_step_classes


def test_purchase_transfer_with_org_pipeline():
    expected_step_classes = [
        "SetupContextPurchaseTransferWithOrgStep",
        "RequestTransferWithOrgStep",
        "AwaitTransferWithOrgStep",
        "AssignTransferMPAStep",
        "MPAPreConfiguration",
        "RegisterTransferredMPAToAirtableStep",
        "CreateSubscription",
        "CCPOnboard",
        "CreateFinOpsMPAEntitlementStep",
        "CreateFinOpsEntitlementStep",
        "CreateOnboardTicketStep",
        "CompletePurchaseOrderStep",
        "SynchronizeAgreementSubscriptionsStep",
    ]

    actual_step_classes = [
        step.__class__.__name__ for step in pipelines.purchase_transfer_with_organization.queue
    ]

    assert actual_step_classes == expected_step_classes


def test_purchase_transfer_without_org_pipeline():
    expected_step_classes = [
        "ValidatePurchaseTransferWithoutOrgStep",
        "SetupContextPurchaseTransferWithoutOrgStep",
        "AssignMPA",
        "MPAPreConfiguration",
        "SendInvitationLinksStep",
        "AwaitInvitationLinksStep",
        "CreateSubscription",
        "CCPOnboard",
        "CreateFinOpsMPAEntitlementStep",
        "CreateFinOpsEntitlementStep",
        "CreateUpdateKeeperTicketStep",
        "CreateOnboardTicketStep",
        "CompletePurchaseOrderStep",
        "SynchronizeAgreementSubscriptionsStep",
    ]

    actual_step_classes = [
        step.__class__.__name__ for step in pipelines.purchase_transfer_without_organization.queue
    ]

    assert actual_step_classes == expected_step_classes


def test_change_order_pipeline_steps():
    expected_step_classes = [
        "SetupChangeContext",
        "AddLinkedAccountStep",
        "CreateChangeSubscriptionStep",
        "CreateFinOpsEntitlementStep",
        "CompleteChangeOrderStep",
        "SynchronizeAgreementSubscriptionsStep",
    ]

    actual_step_classes = [step.__class__.__name__ for step in pipelines.change_order.queue]

    assert actual_step_classes == expected_step_classes


def test_terminate_pipeline_steps():
    expected_step_classes = [
        "SetupTerminateContextStep",
        "CreateTerminationServiceRequestStep",
        "AwaitTerminationServiceRequestStep",
        "DeleteFinOpsEntitlementsStep",
        "CompleteTerminationOrderStep",
    ]

    actual_step_classes = [step.__class__.__name__ for step in pipelines.terminate.queue]

    assert actual_step_classes == expected_step_classes
