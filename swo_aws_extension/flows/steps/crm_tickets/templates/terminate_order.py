"""CRM Ticket Template for Order Termination."""

from swo_aws_extension.flows.steps.crm_tickets.templates.models import CRMTicketTemplate

ORDER_TERMINATION_TEMPLATE = CRMTicketTemplate(
    title="Action Required : Agreement Termination",
    additional_info="Customer wants to terminate their current active AWS agreement",
    summary=(
        "Dear MCoE Team,<br><br>"
        "A notification has been generated on the Marketplace Platform for termination of an AWS"
        " account.<br><br>"
        "Billing transfer relationship end date: <b>{end_date}</b><br><br>"
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
        "Please make sure to verify successful cancellation of any AWS connection with this"
        " customer."
        "<br>Thank you for your attention and taking all necessary steps!<br><br>"
        "Best Regards,<br>"
        "Marketplace Platform Team"
    ),
)
