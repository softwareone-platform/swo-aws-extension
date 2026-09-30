# AWS SES

Delivers customer-facing emails from a verified SoftwareOne sender address. Used for order-related notifications and feature deployment alerts where direct email delivery is required.

## Authentication

AWS access key credentials passed directly to the `boto3` SES client. No OAuth flow is involved.

## Configuration

| Environment Variable | Description |
| --- | --- |
| `EXT_AWS_SES_CREDENTIALS` | Credentials in `AccessKey:SecretKey` format |
| `EXT_AWS_SES_REGION` | AWS region where SES is configured (e.g., `eu-west-1`) |
| `EXT_EMAIL_NOTIFICATIONS_ENABLED` | Feature toggle: `1` enables sending, `0` skips silently |
| `EXT_EMAIL_NOTIFICATIONS_SENDER` | Verified sender address shown in the `From` field |
| `EXT_DEPLOY_SERVICES_FEATURE_RECIPIENTS` | Comma-separated recipient list for deploy-services notifications |

The `EXT_AWS_SES_CREDENTIALS` value is split on `:` at runtime: the first segment becomes `aws_access_key_id` and the second `aws_secret_access_key`.

## Operations

| Operation | boto3 Call | Description |
| --- | --- | --- |
| Send Email | `ses.send_email(Source, Destination, Message)` | Sends an HTML email to one or more recipients; returns `False` on any boto3 error |

`EmailNotificationManager.send_email()` returns `True` on success and `False` on failure. When `EXT_EMAIL_NOTIFICATIONS_ENABLED` is `0`, it returns `False` immediately without making any API call.

## Code Reference

Client: [`swo_aws_extension/swo/notifications/email.py`](../../swo_aws_extension/swo/notifications/email.py)
