from abc import ABC, abstractmethod
from typing import Any


class IcebergCatalogConnector(ABC):
    @abstractmethod
    def list_namespaces(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def list_tables(self, namespace: str) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def load_table_metadata(self, table_name: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def list_snapshots(self, table_name: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def list_refs(self, table_name: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_table_schema(self, table_name: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_table_properties(self, table_name: str) -> dict[str, Any]:
        raise NotImplementedError
