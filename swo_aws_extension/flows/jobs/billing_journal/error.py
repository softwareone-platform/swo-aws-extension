class AWSBillingException(Exception):
    def __init__(self, message: str, payload: dict) -> None:
        super().__init__(message)
        self.payload: dict = payload
        self.service_name: str = payload["service_name"]
        self.amount: float = payload["amount"]
        self.message: str = message

    def __str__(self) -> str:
        return self.message
