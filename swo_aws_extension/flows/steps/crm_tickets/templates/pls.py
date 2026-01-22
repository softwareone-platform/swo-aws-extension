"""CRM Ticket Template for Partner Led Support (PLS)."""

from swo_aws_extension.flows.steps.crm_tickets.templates.models import CRMTicketTemplate

PLS_TEMPLATE = CRMTicketTemplate(
    title="Action Required: PLS Support Ticket",
    additional_info="New customers for PLES need to be enabled manually for PLES",
    summary=(
        "Dear MCoE Team,<br><br>"
        "A new PLES customer needs to be configured for PLES :<br>"
        "Please check the order details and get in touch with the sales team and customer "
        "primary contact for the next steps.<br><br>"
        "<b>Order Details:</b><br>"
        "<ul>"
        "<li><b>Customer:</b> {customer_name}</li>"
        "<li><b>Buyer:</b> {buyer_id}</li>"
        "<li><b>SCU:</b> {buyer_external_id}</li>"
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
        "Thank you for your attention and taking all necessary steps!<br><br>"
        "Best Regards,<br>"
        "Marketplace Platform Team"
    ),
)
