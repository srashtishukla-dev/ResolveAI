from rest_framework.permissions import BasePermission


class IsStaffForWrite(BasePermission):
    message = 'Only staff users can access knowledge documents.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )
