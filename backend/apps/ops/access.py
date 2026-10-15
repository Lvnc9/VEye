def can_manage_backups(user) -> bool:
    """The مدیر عامل (or a superuser) and the developer account — the people who answer for the data."""
    from apps.leave.access import is_top

    return bool(getattr(user, "is_authenticated", False)) and (user.is_developer or is_top(user))
