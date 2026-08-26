from django import template

from clubs.translations import translate

register = template.Library()


@register.simple_tag
def tr(key, area="Allmän"):
    return translate(str(key), area)
