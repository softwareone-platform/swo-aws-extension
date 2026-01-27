"""Email Template for deploying services feature notification."""

from swo_aws_extension.swo.notifications.templates.models import EmailNotificationTemplate

DEPLOY_SERVICES_FEATURE_TEMPLATE = EmailNotificationTemplate(
    subject="New AWS account is pending services feature deployment",
    body=(
        "Dear Services Team,<br><br>"
        "Good News!! A new customer for AWS is being onboarded in the SWO Marketplace.<br>"
        "Please check the order details and deploy the features manually.<br><br>"
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
        "Thank you for your attention.<br><br>"
        "Best Regards,<br>"
        "Marketplace Platform Team"
    ),
)
