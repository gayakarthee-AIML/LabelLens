"""
Authoritative role-based access control.

The frontend's login screen lets a user pick "Inspector", "Senior Inspector",
etc. as a UX convenience — that choice is NEVER trusted here. Every protected
endpoint depends on `require_roles(...)`, which reads the role out of the
verified JWT (itself derived from the database record at login time, see
app/api/routers/auth.py), not from anything the client sent in the request body.
"""
from enum import Enum

from fastapi import Depends, HTTPException, status

from app.api.deps import get_current_user
from app.db.models import User


class Role(str, Enum):
    INSPECTOR = "INSPECTOR"
    SENIOR_INSPECTOR = "SENIOR_INSPECTOR"
    ADMINISTRATOR = "ADMINISTRATOR"
    REGULATOR = "REGULATOR"


# Central capability table — mirrors src/context/AuthContext.tsx PERMISSIONS on
# the frontend, but this copy is the one that actually gets enforced.
PERMISSIONS: dict[str, set[Role]] = {
    "CREATE_INSPECTION": {Role.INSPECTOR, Role.SENIOR_INSPECTOR},
    "APPROVE_INSPECTION": {Role.SENIOR_INSPECTOR},
    "MANAGE_RULES": {Role.ADMINISTRATOR},
    "MANAGE_USERS": {Role.ADMINISTRATOR},
    "VIEW_AUDIT_LOG": {Role.ADMINISTRATOR},
    "VIEW_ENFORCEMENT_DASHBOARD": {Role.SENIOR_INSPECTOR, Role.REGULATOR, Role.ADMINISTRATOR},
    "VIEW_ANALYTICS": {Role.SENIOR_INSPECTOR, Role.REGULATOR, Role.ADMINISTRATOR},
}


def require_roles(*roles: Role):
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if Role(current_user.role) not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {current_user.role} is not permitted to perform this action.",
            )
        return current_user

    return dependency


def require_permission(permission: str):
    allowed_roles = PERMISSIONS[permission]

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if Role(current_user.role) not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {permission}",
            )
        return current_user

    return dependency
