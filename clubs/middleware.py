from django.conf import settings
from django.shortcuts import resolve_url
from urllib.parse import urlsplit

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


class MediaNoCacheMiddleware:
    """DEBUG-only `Cache-Control: no-cache` on /media/ responses.

    Media is served by django.views.static.serve with just Last-Modified,
    so browsers heuristically cache uploads and a plain reload can show a
    stale club logo/background after re-uploading. no-cache keeps the 304
    revalidation but never serves from the heuristic-fresh window. Static
    files have the same problem but are preempted by runserver's
    StaticFilesHandler before any middleware runs — the runserver command
    override in clubs/management/commands/ handles that one instead.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if settings.DEBUG and request.path.startswith(
            "/" + settings.MEDIA_URL.lstrip("/")
        ):
            response.headers["Cache-Control"] = "no-cache"
        return response


class HtmxAuthRedirectMiddleware:
    """Turns auth redirects into full-page navigations for hx-boost requests.

    Under hx-boost an ordinary 302 to the login page would be followed via
    XHR and the login layout swapped into the app shell. Answering with
    HX-Redirect makes htmx do a real browser navigation instead. Other
    redirects (post/save flows) keep their normal boosted swap behaviour.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (
            response.status_code in (301, 302)
            and request.headers.get("HX-Request") == "true"
        ):
            location = response.get("Location", "")
            login_path = urlsplit(resolve_url(settings.LOGIN_URL)).path
            if urlsplit(location).path == login_path:
                response.status_code = 200
                response["HX-Redirect"] = location
        return response
