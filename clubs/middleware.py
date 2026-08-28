from . import translations


class CurrentRequestMiddleware:
    """Binds the active request to a contextvar for the duration of the
    request cycle so request-less helpers — currently
    clubs.translations.get_language() — can resolve the signed-in user."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = translations.current_request.set(request)
        try:
            return self.get_response(request)
        finally:
            translations.current_request.reset(token)
