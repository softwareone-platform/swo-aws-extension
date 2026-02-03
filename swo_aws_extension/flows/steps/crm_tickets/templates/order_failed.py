"""CRM Ticket Template for Order Failed."""

from swo_aws_extension.flows.steps.crm_tickets.templates.models import CRMTicketTemplate

ORDER_FAILED_TEMPLATE = CRMTicketTemplate(
    title="Action Required: Order Failed Ticket",
    additional_info="Customer order failed and we need removal of all invites and fail the order",
    summary=(
        "Dear MCoE Team,<br><br>"
        "The following order has been flagged to fail on the marketplace.<br><br>"
        "<b>Order Details:</b><br>"
        "<ul>"
        "<li><b>Customer:</b> {customer_name}</li>"
        "<li><b>Buyer:</b> {buyer_id}</li>"
        "<li><b>SCU:</b> {buyer_external_id}</li>"
        "<li><b>Seller Country:</b> {seller_country}</li>"
        "<li><b>PMA:</b> {pm_account_id}</li>"
        "<li><b>Order:</b> {order_id}</li>"
        "<li><b>MasterPayerId:</b> {master_payer_id}</li>"
        "<li><b>Handshake Approved:</b> {handshake_approved}</li>"
        "<li><b>Customer Roles Deployed:</b> {customer_roles_deployed}</li>"
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
