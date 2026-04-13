"""CRM Ticket Template for Deploy Services Error."""

from swo_aws_extension.flows.steps.crm_tickets.templates.models import CRMTicketTemplate

DEPLOY_SERVICES_ERROR_TEMPLATE = CRMTicketTemplate(
    title="Action Required: Deploy Services Error",
    additional_info="An error occurred during the deploy services process",
    summary=(
        "Dear MCoE Team,<br><br>"
        "An error occurred during the deploy services process (feature version) "
        "for the following order.<br><br>"
        "<b>Order Details:</b><br>"
        "<ul>"
        "<li><b>Customer:</b> {customer_name}</li>"
        "<li><b>Buyer:</b> {buyer_id}</li>"
        "<li><b>SCU:</b> {buyer_external_id}</li>"
        "<li><b>PMA:</b> {pm_account_id}</li>"
        "<li><b>Order:</b> {order_id}</li>"
        "<li><b>MasterPayerId:</b> {master_payer_id}</li>"
        "</ul>"
        "<b>Technical Point of Contact:</b><br>"
        "<ul>"
        "<li><b>Name:</b> {technical_contact_name}</li>"
        "<li><b>Email:</b> {technical_contact_email}</li>"
        "<li><b>Phone:</b> {technical_contact_phone}</li>"
        "</ul>"
        "<b>Support Information:</b><br>"
        "<ul>"
        "<li><b>Support Type:</b> {support_type}</li>"
        "</ul>"
        "<b>Additional Services:</b><br>"
        "<ul>"
        "<li><b>SWO Additional Services:</b> {supplementary_services}</li>"
        "</ul>"
        "<b>Error Details:</b><br>"
        "<ul>"
        "<li>{error_message}</li>"
        "</ul>"
        "Please investigate and take the necessary action.<br><br>"
        "Best Regards,<br>"
        "Marketplace Platform Team"
    ),
)
