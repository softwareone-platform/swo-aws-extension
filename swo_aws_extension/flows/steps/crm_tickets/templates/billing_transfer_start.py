"""CRM Ticket Template for the billing transfer start of migrated AWS customers."""

from swo_aws_extension.flows.steps.crm_tickets.templates.models import CRMTicketTemplate

BILLING_TRANSFER_START_TEMPLATE = CRMTicketTemplate(
    title="AWS migrated customer billing transfer started",
    additional_info="Billing transfer of an existing SWO AWS customer migrated to the Marketplace",
    summary=(
        "Dear MCoE Team,<br><br>"
        "The billing transfer of an existing SoftwareOne AWS customer migrated to the SWO "
        "Marketplace is now active. The account is invoiced through the Marketplace from the "
        "billing transfer start date.<br>"
        "Please follow up the root handover of the master payer account with the customer "
        "and the sales team.<br><br>"
        "<b>Account Details:</b><br>"
        "<ul>"
        "<li><b>Customer:</b> {customer_name}</li>"
        "<li><b>Buyer:</b> {buyer_id}</li>"
        "<li><b>SCU:</b> {buyer_external_id}</li>"
        "<li><b>Seller Country:</b> {seller_country}</li>"
        "<li><b>Order:</b> {order_id}</li>"
        "<li><b>Agreement:</b> {agreement_id}</li>"
        "<li><b>MasterPayerId:</b> {master_payer_id}</li>"
        "<li><b>CCO Contract Number:</b> {cco_contract_number}</li>"
        "<li><b>Billing Transfer Start Date:</b> {billing_transfer_start_date}</li>"
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
        "Thank you for your attention and taking all necessary steps!<br><br>"
        "Best Regards,<br>"
        "Marketplace Platform Team"
    ),
)
