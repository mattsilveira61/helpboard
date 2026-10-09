import bcrypt


def hash_password(password: str) -> str:
    """Gera o hash bcrypt da senha (com salt aleatório embutido)."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())
