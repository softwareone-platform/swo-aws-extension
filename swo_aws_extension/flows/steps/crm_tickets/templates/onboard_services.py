"""CRM Ticket Template for Onboard Services."""

from swo_aws_extension.flows.steps.crm_tickets.templates.models import CRMTicketTemplate

ONBOARD_SERVICES_TEMPLATE = CRMTicketTemplate(
    title="New AWS on-boarding in Marketplace existing AWS customer",
    additional_info="New customer joining SWO through billing transfer",
    summary=(
        "Dear MCoE Team,<br><br>"
        "Good News!! A new customer for AWS is being onboarded in the SWO Marketplace.<br>"
        "Please check the order details and get in touch with the sales team and customer "
        "primary contact for the next steps.<br><br>"
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
        "<span style='color: red;'><b>CALL TO ACTION:</b></span> Please reach out the account "
        "manager to contact the customer regarding additional services.!!<br><br>"
        "Thank you for your attention.<br><br>"
        "Best Regards,<br>"
        "Marketplace Platform Team"
    ),
)
