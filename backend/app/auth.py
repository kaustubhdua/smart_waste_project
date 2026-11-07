import base64
import hashlib
import hmac
import secrets

PASSWORD_ITERATIONS = 310_000
PASSWORD_SCHEME = 'pbkdf2_sha256'

def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode('ascii').rstrip('=')

def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, PASSWORD_ITERATIONS)
    return '{}${}${}${}'.format(PASSWORD_SCHEME, PASSWORD_ITERATIONS, _b64encode(salt), _b64encode(digest))

def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations_text, salt_text, digest_text = encoded.split('$', 3)
        iterations = int(iterations_text)
        if scheme != PASSWORD_SCHEME or not 100_000 <= iterations <= 2_000_000:
            return False
        expected = _b64decode(digest_text)
        actual = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), _b64decode(salt_text), iterations)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, UnicodeError):
        return False

def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()
