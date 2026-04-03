# Contract: Gmail Client Service

**Module**: `addons/etsy_integration/services/gmail_client.py`
**Type**: Gmail API wrapper with OAuth2 (depends on google-api-python-client)

## Interface

### Configuration

Read from Odoo's `ir.config_parameter`:
- `etsy_integration.gmail_client_id`
- `etsy_integration.gmail_client_secret`
- `etsy_integration.gmail_refresh_token`
- `etsy_integration.gmail_label`

### Functions

```python
class GmailClient:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str):
        """Initialize with OAuth2 credentials."""

    def authenticate(self) -> bool:
        """
        Build Gmail API service using refresh token.
        Auto-refreshes access token if expired.
        Returns True if authentication succeeds.
        """

    def test_connection(self) -> tuple[bool, str]:
        """
        Test Gmail API connectivity.
        Returns (success: bool, message: str).
        """

    def fetch_labeled_emails(self, label: str) -> list[RawEmail]:
        """
        Fetch all emails with the given label.
        Decodes base64 body parts (text/plain and text/html).
        Handles pagination (nextPageToken).
        Returns list of RawEmail dataclass instances.
        """

    def remove_label(self, message_ids: list[str], label: str) -> None:
        """
        Remove the given label from all specified messages.
        Uses batchModify API for efficiency.
        """

    def get_label_id(self, label_name: str) -> str | None:
        """
        Resolve label name to label ID.
        Returns None if label not found.
        """
```

## Behavior

1. Authentication uses OAuth2 refresh token flow (no browser-based consent)
2. Initial consent flow (first-time setup) is handled separately via a controller
3. All API errors are caught and returned as structured error objects, never raised
4. Pagination: continues fetching until no `nextPageToken`
5. Email body decoding: handles both single-part and multi-part MIME structures
6. Label removal is done in a single batch call after all emails in a cycle are processed
