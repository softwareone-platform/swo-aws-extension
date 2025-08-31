from ninja import Schema


class Error(Schema):
    """"MPT API Error message."""
    id: str
    message: str
