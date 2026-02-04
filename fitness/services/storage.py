from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO


class StorageBackend(ABC):
    @abstractmethod
    async def save(self, file: BinaryIO, filename: str) -> str:
        ...

    @abstractmethod
    async def delete(self, filename: str) -> bool:
        ...

    @abstractmethod
    async def get_url(self, filename: str) -> str:
        ...


class LocalStorage(StorageBackend):
    def __init__(self, base_path: Path, base_url: str):
        self.base_path = base_path
        self.base_url = base_url
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def save(self, file: BinaryIO, filename: str) -> str:
        path = self.base_path / filename
        path.write_bytes(file.read())
        return f"{self.base_url}/static/certs/{filename}"

    async def delete(self, filename: str) -> bool:
        p = self.base_path / filename
        if p.exists():
            p.unlink()
            return True
        return False

    async def get_url(self, filename: str) -> str:
        return f"{self.base_url}/static/certs/{filename}"
