"""CRM Ticket Template for migrated AWS customers."""

from swo_aws_extension.flows.steps.crm_tickets.templates.models import CRMTicketTemplate

MIGRATION_TEMPLATE = CRMTicketTemplate(
    title="New AWS migrated customer in Marketplace",
    additional_info="Existing SWO AWS customer migrated to the Marketplace via billing transfer",
    summary=(
        "Dear MCoE Team,<br><br>"
        "An existing SoftwareOne AWS customer has been migrated to the SWO Marketplace.<br>"
        "The billing transfer invitation has been accepted and the agreement keeps the existing "
        "CCO. Please check the order details and follow up the migration with the sales team "
        "and the customer primary contact.<br><br>"
        "<b>Order Details:</b><br>"
        "<ul>"
        "<li><b>Customer:</b> {customer_name}</li>"
        "<li><b>Buyer:</b> {buyer_id}</li>"
        "<li><b>SCU:</b> {buyer_external_id}</li>"
        "<li><b>Seller Country:</b> {seller_country}</li>"
        "<li><b>PMA:</b> {pm_account_id}</li>"
        "<li><b>Order:</b> {order_id}</li>"
        "<li><b>Agreement:</b> {agreement_id}</li>"
        "<li><b>MasterPayerId:</b> {master_payer_id}</li>"
        "<li><b>CCO Contract Number:</b> {cco_contract_number}</li>"
        "<li><b>Handshake Approved:</b> {handshake_approved}</li>"
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
