from rest_framework.permissions import IsAuthenticated


class IsTutor(IsAuthenticated):
    def has_permission(self, request, view):
        if bool(request.user and request.user.is_authenticated):
            return request.user.app_level_role == 'tutor'
        return False

    

class IsTutorOrAdmin(IsAuthenticated):
    def has_permission(self, request, view):
        if bool(request.user and request.user.is_authenticated):
            return request.user.app_level_role in ['tutor','admin']
        return False

    

class IsSchoolAdmin(IsAuthenticated):
    def has_permission(self, request, view):
        if bool(request.user and request.user.is_authenticated):
            return request.user.app_level_role in ['admin']
        return False

    