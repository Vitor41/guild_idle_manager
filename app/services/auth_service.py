from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import (
    create_user,
    get_user_by_email,
    get_user_by_username,
)


class RegistrationError(ValueError):
    pass


def register_user(
    db: Session,
    username: str,
    email: str | None,
    password: str,
    confirm_password: str,
) -> User:
    username = username.strip()
    email = email.strip().lower() if email else None

    if not username:
        raise RegistrationError("Nome de usuario e obrigatorio.")
    if not password:
        raise RegistrationError("Senha e obrigatoria.")
    if password != confirm_password:
        raise RegistrationError("Senha e confirmacao devem ser iguais.")
    if get_user_by_username(db, username):
        raise RegistrationError("Este usuario ja existe.")
    if email and get_user_by_email(db, email):
        raise RegistrationError("Este e-mail ja esta em uso.")

    return create_user(db, username=username, email=email, password_hash=hash_password(password))


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = get_user_by_username(db, username.strip())
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user

