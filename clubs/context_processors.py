from people import services

from .utils import build_theme


def club_context(request):
    person = services.get_person(request.user)
    club = person.club if person else None
    if club is None:
        return {"current_club": None, "theme": None}
    return {"current_club": club, "theme": build_theme(club)}
