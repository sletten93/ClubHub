from people import services

from .utils import get_theme


def club_context(request):
    person = services.get_person(request.user)
    club = person.club if person else None
    if club is None:
        return {"current_club": None, "current_person": person, "theme": None}
    return {
        "current_club": club,
        "current_person": person,
        "theme": get_theme(club),
    }
