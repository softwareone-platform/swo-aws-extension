# MS Teams

Sends operational notifications to internal engineering channels. Used throughout the extension to report errors, warnings, and successes during order processing, secret rotation, and integration failures.

## Authentication

No authentication. Uses a Workflow Webhook URL that posts directly to a specific Teams channel via a Power Automate Workflow. The webhook URL itself acts as the secret.

## Configuration

| Environment Variable | Description |
| --- | --- |
| `EXT_MSTEAMS_WEBHOOK_URL` | Workflow Webhook URL for the target Teams channel |

## Operations

The `TeamsNotificationManager` sends Adaptive Card messages via `requests.post`. All methods accept `title`, `text`, an optional `Button`, and an optional `FactsSection`.

| Method | Style | Prefix | Use Case |
| --- | --- | --- | --- |
| `send_warning(...)` | Warning | ☢ | Non-critical issues that need attention |
| `send_success(...)` | Good | ✅ | Successful completions |
| `send_error(...)` | Attention | 💣 | Recoverable errors |
| `send_exception(...)` | Attention | 🔥 | Unhandled exceptions |

The `notify_one_time_error()` helper ensures a given `(title, message)` pair is sent at most once per process lifetime.

## Code Reference

Client: [`swo_aws_extension/swo/notifications/teams.py`](../../swo_aws_extension/swo/notifications/teams.py)
