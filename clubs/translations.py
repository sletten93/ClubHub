import contextvars
import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

LOCALES_DIR = Path(settings.BASE_DIR) / "locales"
DEFAULT_LANGUAGE = "sv-SE"

# Native names, used for the language choice on the user settings page.
LANGUAGE_NAMES = {
    "sv-SE": "Svenska",
    "en-GB": "English",
    "nb-NO": "Norsk bokmål",
    "da-DK": "Dansk",
    "fi-FI": "Suomi",
    "is-IS": "Íslenska",
}

# Set per request by clubs.middleware.CurrentRequestMiddleware so that
# get_language() can resolve the signed-in user's preference without
# threading the request through every translate() call.
current_request = contextvars.ContextVar("clubhub_request", default=None)


@lru_cache(maxsize=None)
def load_locale(language):
    path = LOCALES_DIR / f"{language}.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=None)
def available_languages():
    return tuple(sorted(path.stem for path in LOCALES_DIR.glob("*.json")))


def get_user_language(user):
    """The user's saved language preference, or None when unset/unknown."""
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    try:
        language = user.profile.language
    except (AttributeError, ObjectDoesNotExist):
        return None
    return language if language in available_languages() else None


def get_language():
    request = current_request.get()
    if request is None:
        return getattr(settings, "CLUBHUB_LANGUAGE", DEFAULT_LANGUAGE)
    language = getattr(request, "_clubhub_language", None)
    if language is None:
        language = get_user_language(getattr(request, "user", None)) or getattr(
            settings, "CLUBHUB_LANGUAGE", DEFAULT_LANGUAGE
        )
        setattr(request, "_clubhub_language", language)
    return language


def reset_language_cache(request):
    """Forget the language resolved for this request (call after the user's
    preference changes mid-request, so flash messages use the new one)."""
    if hasattr(request, "_clubhub_language"):
        delattr(request, "_clubhub_language")


def translate(key, area="Allmän", language=None):
    language = language or get_language()
    for locale in (load_locale(language), load_locale(DEFAULT_LANGUAGE)):
        value = locale.get(area, {}).get(key)
        if value is not None:
            return value
    return key
