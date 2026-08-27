"""Reusable mixins for class-based views."""

PER_PAGE_OPTIONS = (40, 60, 100)


class TablePaginationMixin:
    """Adds table pagination with a page-size selector to a ListView.

    Reads ``?per_page`` (whitelisted values, defaults to the first of
    ``per_page_options``) and lets Django's ``?page`` handling do the rest.
    ``get_context_data`` gains the pieces needed by
    ``templates/shared/table_header.html`` / ``table_footer.html``:

    - ``per_page`` / ``per_page_options``: active size + a URL per size
      (resetting to page 1, preserving all other query params).
    - ``prev_page_url`` / ``next_page_url``: page links (``None`` at edges).
    - ``entries_start`` / ``entries_end`` / ``entries_total``: the
      "1-40 av 250" counter.
    """

    per_page_options = PER_PAGE_OPTIONS
    default_per_page = PER_PAGE_OPTIONS[0]

    def get_paginate_by(self, queryset):
        """Called by Django while building the context; parse ?per_page here."""
        raw = self.request.GET.get("per_page")
        try:
            per_page = int(raw)
        except (TypeError, ValueError):
            per_page = self.default_per_page
        if per_page not in self.per_page_options:
            per_page = self.default_per_page
        self._per_page = per_page
        return per_page

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        paginator = context.get("paginator")
        page_obj = context.get("page_obj")
        if paginator is None or page_obj is None:
            return context

        base_params = self.request.GET.copy()

        def build_url(**overrides):
            params = base_params.copy()
            for key, value in overrides.items():
                if value is None:
                    params.pop(key, None)
                else:
                    params[key] = str(value)
            return f"?{params.urlencode()}"

        per_page_urls = []
        for option in self.per_page_options:
            params = base_params.copy()
            params["per_page"] = str(option)
            params.pop("page", None)  # changing page size resets to page 1
            per_page_urls.append(
                {
                    "value": option,
                    "url": f"?{params.urlencode()}",
                    "active": option == self._per_page,
                }
            )

        total = paginator.count
        current = page_obj.number
        if total:
            entries_start = (current - 1) * self._per_page + 1
            entries_end = min(current * self._per_page, total)
        else:
            entries_start = entries_end = 0

        context.update(
            {
                "per_page": self._per_page,
                "per_page_options": per_page_urls,
                "prev_page_url": build_url(page=current - 1)
                if page_obj.has_previous()
                else None,
                "next_page_url": build_url(page=current + 1)
                if page_obj.has_next()
                else None,
                "entries_start": entries_start,
                "entries_end": entries_end,
                "entries_total": total,
            }
        )
        return context
