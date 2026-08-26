import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings

LOCALES_DIR = Path(settings.BASE_DIR) / "locales"
DEFAULT_LANGUAGE = "sv-SE"


@lru_cache(maxsize=None)
def load_locale(language):
    path = LOCALES_DIR / f"{language}.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def get_language():
    return getattr(settings, "CLUBHUB_LANGUAGE", DEFAULT_LANGUAGE)


def translate(key, area="Allmän", language=None):
    language = language or get_language()
    for locale in (load_locale(language), load_locale(DEFAULT_LANGUAGE)):
        value = locale.get(area, {}).get(key)
        if value is not None:
            return value
    return key
