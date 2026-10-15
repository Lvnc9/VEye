def can_view_coverage(request, document) -> bool:
    """Who read it and who has not: the people who may write the document (its authors — they answer for
    it) and anyone with `view_reports`."""
    from apps.accounts.models import Capability
    from apps.documents import authority

    user = request.user
    return user.has_capability(Capability.VIEW_REPORTS) or authority.for_request(request).can_author(document)
