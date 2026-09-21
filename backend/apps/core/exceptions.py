import logging

from django.http import Http404
from rest_framework.exceptions import APIException, NotFound
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger("veye")


NOT_FOUND_MESSAGE = "مورد درخواستی یافت نشد."


class ConflictError(APIException):
    """HTTP 409: the request is well-formed but conflicts with the current
    state of the data (a duplicate title, revising a superseded document...).

    The response body is `{"detail": <Persian message>, "code": <machine
    code>, **extra}`. `extra` keeps its JSON types — DRF's own APIException
    would coerce every value in a dict `detail` to a string, turning an id like
    `1` into `"1"`, so the body is carried separately in `payload` and swapped
    in by `veye_exception_handler`.
    """

    status_code = 409
    default_detail = "درخواست با وضعیت فعلی داده‌ها سازگار نیست."
    default_code = "conflict"

    def __init__(self, message: str | None = None, code: str | None = None, **extra):
        message = message or self.default_detail
        code = code or self.default_code
        super().__init__(message, code)
        self.payload = {"detail": message, "code": code, **extra}


def veye_exception_handler(exc, context):
    """Wraps DRF's default exception handler: keeps ConflictError payloads
    typed, answers Http404 in Persian, and logs unhandled exceptions with request context before falling
    back to DRF's response (or Django's 500 handler when DRF can't handle it)."""
    if isinstance(exc, Http404):
        # get_object_or_404 raises Http404("No Project matches the given query."), and DRF carries that
        # English message into the response. A missing (or invisible) object is answered in Persian.
        exc = NotFound(NOT_FOUND_MESSAGE)
    response = drf_exception_handler(exc, context)
    if response is None:
        request = context.get("request")
        logger.exception("Unhandled exception on %s", getattr(request, "path", "?"))
    elif isinstance(exc, ConflictError):
        response.data = exc.payload
    return response
