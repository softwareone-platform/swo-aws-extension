"""CRM Ticket Template for Order Termination."""

from swo_aws_extension.flows.steps.crm_tickets.templates.models import CRMTicketTemplate

TRANSFER_END_SCHEDULED_TEMPLATE = CRMTicketTemplate(
    title="Action Required : Agreement Termination",
    additional_info="Customer has scheduled the end of the AWS billing transfer",
    summary=(
        "Dear MCoE Team,<br><br>"
        "The customer has scheduled the end of the AWS responsibility transfer.<br><br>"
        "Termination date: <b>{end_date}</b><br><br>"
        "<b>Details:</b><br>"
        "<ul>"
        "<li><b>Agreement:</b> {agreement_id}</li>"
        "<li><b>MasterPayerId:</b> {master_payer_id}</li>"
        "<li><b>PMA:</b> {pma_account_id}</li>"
        "</ul>"
        "The agreement will be terminated after that date and AWS offboarding must be"
        " handled manually."
        "<br>Thank you for your attention and taking all necessary steps!<br><br>"
        "Best Regards,<br>"
        "Marketplace Platform Team"
    ),
)

ORDER_TERMINATION_TEMPLATE = CRMTicketTemplate(
    title="AWS - Action Required : Agreement Termination",
    additional_info="Customer wants to terminate their current active AWS agreement",
    summary=(
        "Dear MCoE Team,<br><br>"
        "A notification has been generated on the Marketplace Platform for termination of an AWS"
        " account.<br><br>"
        "Termination date (end of minimum notice period): <b>{end_date}</b><br><br>"
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
