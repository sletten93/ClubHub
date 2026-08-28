from django.apps import AppConfig
from django.db.models.signals import post_delete, post_save


class ClubsConfig(AppConfig):
    name = 'clubs'

    def ready(self):
        from .models import Club
        from .utils import invalidate_theme_cache

        post_save.connect(invalidate_theme_cache, sender=Club, dispatch_uid="ch-theme-save")
        post_delete.connect(invalidate_theme_cache, sender=Club, dispatch_uid="ch-theme-delete")
