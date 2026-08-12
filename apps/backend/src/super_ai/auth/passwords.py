"""可注入的密码哈希边界。"""

from typing import Final, Protocol

from pwdlib import PasswordHash

DUMMY_PASSWORD_HASH: Final[str] = (
    "$argon2id$v=19$m=65536,t=3,p=4$XJseKrkE3JqQhOaWm6V8Fw$"
    "v+Xr2BhL+67jzO94CzfoF2YVZSoL63Uq4krPC6/CJeg"
)


class PasswordManager(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...


class PwdlibPasswordManager:
    """使用 pwdlib 推荐 Argon2 配置，不在 import 时计算 hash。"""

    def __init__(self) -> None:
        self._password_hash = PasswordHash.recommended()

    def hash(self, password: str) -> str:
        return self._password_hash.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        return self._password_hash.verify(password, password_hash)
