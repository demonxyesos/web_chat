from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    if hashed_password.startswith("$2"):
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            return False
    # Legacy monolith stored plaintext passwords.
    return plain_password == hashed_password


def is_bcrypt_hash(hashed_password: str) -> bool:
    return bool(hashed_password) and hashed_password.startswith("$2")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
