"""CRM Ticket Template for Deploy Roles."""

from swo_aws_extension.flows.steps.crm_tickets.templates.models import CRMTicketTemplate

DEPLOY_ROLES_TEMPLATE = CRMTicketTemplate(
    title="Action Required: Roles not deployed yet",
    additional_info="New customer joining SWO but no service roles deployed",
    summary=(
        "Dear MCoE Team,<br><br>"
        "Please get in touch with the customer as we have noticed that the required service roles "
        "for AWS essentials have not been deployed yet.<br><br>"
        "<b>Transfer Details:</b><br>"
        "<ul>"
        "<li><b>Customer:</b> {customer_name}</li>"
        "<li><b>Buyer:</b> {buyer_id}</li>"
        "<li><b>SCU:</b> {buyer_external_id}</li>"
        "<li><b>Seller Country:</b> {seller_country}</li>"
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
        "Thank you for your attention.<br><br>"
        "Best Regards,<br>"
        "Marketplace Platform Team"
    ),
)
