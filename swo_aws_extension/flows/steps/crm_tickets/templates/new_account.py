"""CRM Ticket Template for New Account creation."""

from swo_aws_extension.flows.steps.crm_tickets.templates.models import CRMTicketTemplate

NEW_ACCOUNT_TEMPLATE = CRMTicketTemplate(
    title="New AWS Onboarding in Marketplace",
    additional_info="AWS New AWS linked account created",
    summary=(
        "Dear MCoE Team,<br><br>"
        "Good News!! New customer for AWS is being onboarded in Marketplace.<br><br>"
        "Please check the order details and get in touch with the sales team and customer "
        "primary contact for the next steps.<br><br>"
        "<b>Order Details:</b><br>"
        "<ul>"
        "<li><b>Customer:</b> {customer_name}</li>"
        "<li><b>Buyer:</b> {buyer_id}</li>"
        "<li><b>SCU:</b> {buyer_external_id}</li>"
        "<li><b>Order:</b> {order_id}</li>"
        "<li><b>New Account Name:</b> {order_account_name}</li>"
        "<li><b>New Account E-mail:</b> {order_account_email}</li>"
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
        "Thank you, team, for your attention and taking all necessary steps!<br><br>"
        "Best Regards,<br>"
        "Marketplace Platform Team"
    ),
)
