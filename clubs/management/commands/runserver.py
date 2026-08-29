from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.contrib.staticfiles.management.commands.runserver import (
    Command as StaticfilesRunserverCommand,
)


class NoCacheStaticFilesHandler(StaticFilesHandler):
    """StaticFilesHandler that makes the browser always revalidate.

    The stock handler sends only Last-Modified, so browsers heuristically
    cache assets for up to ~10% of their age and a plain reload serves
    stale CSS/JS while developing. `no-cache` keeps the cheap 304
    revalidation but never serves from the heuristic-fresh window. This
    mirrors what whitenoise sends (max-age=0) whenever it serves in dev
    itself (e.g. `runserver --nostatic`).
    """

    def serve(self, request):
        response = super().serve(request)
        response.headers["Cache-Control"] = "no-cache"
        return response


class Command(StaticfilesRunserverCommand):
    """runserver with always-fresh static responses during development.

    On plain runserver the StaticFilesHandler wraps the whole WSGI app and
    preempts every piece of middleware, so static responses can't be
    stamped anywhere else — hence this override. Media files go through
    URL resolution and are handled by MediaNoCacheMiddleware instead.
    """

    def get_handler(self, *args, **options):
        handler = super().get_handler(*args, **options)
        if isinstance(handler, StaticFilesHandler):
            return NoCacheStaticFilesHandler(handler.application)
        return handler
