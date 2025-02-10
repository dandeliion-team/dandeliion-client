class DandeliionInterfaceException(Exception):
    pass


class DandeliionAPIException(Exception):
    """
    Raised whenever the API returns an error. The exception will contain the
    raw error message from the API.
    """
    pass
