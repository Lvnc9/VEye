from rest_framework.permissions import SAFE_METHODS, BasePermission


class HasCapability(BasePermission):
    """Checks a domain capability (apps.accounts.models.Capability) granted by
    the user's access roll.

    Usage — a capability required for every method:

        required_capability = Capability.MANAGE_PERSONNEL
        permission_classes = [IsAuthenticated, HasCapability]

    Or one required only for writes, leaving reads open to any authenticated
    user:

        write_capability = Capability.MANAGE_PERSONNEL

    If a view sets neither attribute this permission is a no-op, so it is safe
    to include in a shared base class.
    """

    message = "شما دسترسی لازم برای این عملیات را ندارید."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        required = getattr(view, "required_capability", None)
        if required is None and request.method not in SAFE_METHODS:
            required = getattr(view, "write_capability", None)

        if required is None:
            return True

        return request.user.has_capability(required)
