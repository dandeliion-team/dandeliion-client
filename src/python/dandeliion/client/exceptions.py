class DandeliionInterfaceException(Exception):
    pass


class DandeliionAPIException(Exception):
    """
    Raised whenever the API returns an error. The exception will contain the
    raw error message from the API.
    """
    pass


class DandeliionTokenValidationError(DandeliionAPIException):
    """Raised when the API rejects a simulation submission's token."""

    def __init__(self, message, validation):
        super().__init__(message)
        self.validation = validation
