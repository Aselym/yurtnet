"""Dashboard için form tabanlı oturum yönetimi.

Tarayıcının kendi parola kutusu (HTTP Basic) yerine gerçek bir giriş sayfası
kullanılıyor: daha derli toplu görünüyor ve "çıkış yap" imkânı veriyor.

Oturum çerezi HMAC ile imzalanır ve son kullanma zamanı taşır. Sunucu tarafında
oturum listesi tutulmadığı için uygulama yeniden başladığında kimse düşmez;
imza anahtarı diskte kalıcıdır.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import time
from pathlib import Path

log = logging.getLogger(__name__)

COOKIE_NAME = "yurtnet_session"


def load_or_create_secret(path: str | Path) -> bytes:
    """İmza anahtarını diskten okur, yoksa üretir.

    Anahtar kalıcı olduğu için uygulama yeniden başlatıldığında açık oturumlar
    geçerliliğini korur.
    """
    secret_path = Path(path)
    if secret_path.exists():
        data = secret_path.read_bytes().strip()
        if len(data) >= 32:
            return data

    data = secrets.token_bytes(48)
    secret_path.write_bytes(data)
    try:
        secret_path.chmod(0o600)  # Windows'ta etkisiz, Linux'ta önemli
    except OSError:
        pass
    log.info("Yeni oturum imza anahtarı üretildi: %s", secret_path)
    return data


def issue(secret: bytes, username: str, lifetime_seconds: int) -> str:
    """Kullanıcı için imzalı oturum çerezi değeri üretir."""
    expires = int(time.time()) + lifetime_seconds
    payload = f"{username}|{expires}"
    signature = _sign(secret, payload)
    return base64.urlsafe_b64encode(f"{payload}|{signature}".encode()).decode()


def verify(secret: bytes, cookie_value: str) -> str | None:
    """Geçerliyse kullanıcı adını, değilse None döner."""
    if not cookie_value:
        return None
    try:
        raw = base64.urlsafe_b64decode(cookie_value.encode()).decode()
        username, expires, signature = raw.rsplit("|", 2)
    except Exception:
        return None

    if not hmac.compare_digest(signature, _sign(secret, f"{username}|{expires}")):
        return None
    try:
        if int(expires) < time.time():
            return None
    except ValueError:
        return None
    return username


def check_password(expected_user: str, expected_password: str, user: str, password: str) -> bool:
    """Kullanıcı adı ve parolayı sabit sürede karşılaştırır.

    İki karşılaştırma da her koşulda çalıştırılır; erken çıkış yapılsaydı
    yanıt süresi 'kullanıcı adı doğru mu' bilgisini sızdırabilirdi.

    Kullanıcı adı büyük/küçük harf duyarsız ve baştaki/sondaki boşluklardan
    arındırılmış karşılaştırılır: telefon klavyeleri ilk harfi büyütüyor ve
    doğru parolayla bile giriş reddediliyordu. Parola aynen karşılaştırılır.
    """
    user_ok = hmac.compare_digest(
        user.strip().casefold().encode(), expected_user.strip().casefold().encode()
    )
    password_ok = hmac.compare_digest(password.encode(), expected_password.encode())
    return user_ok and password_ok


def _sign(secret: bytes, payload: str) -> str:
    return hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
