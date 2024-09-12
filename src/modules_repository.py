from abc import ABC
from typing import Dict, Optional, Type, TypeVar, cast

T = TypeVar("T", bound="Module")


class ModulesRepository:
    __instance: Optional["ModulesRepository"] = None

    def __new__(cls) -> "ModulesRepository":
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self) -> None:
        self.__services: Dict[Type["Module"], "Module"] = dict()

    def register(self, instance: "Module") -> None:
        self.__services[type(instance)] = instance

    def get(self, cls: Type[T]) -> T:
        service = self.__services.get(cls)
        if service is None:
            raise ValueError(f"Module {cls} not registered.")
        return cast(T, service)

    def __getitem__(self, cls: Type[T]) -> T:
        return self.get(cls)

    def __setitem__(self, cls: Type[T], instance: T) -> None:
        self.register(instance)

    def __contains__(self, cls: Type[T]) -> bool:
        return cls in self.__services


repository = ModulesRepository()


class Module(ABC):
    def __init__(self) -> None:
        self._repository = repository
        self._repository.register(self)


__all__ = ["Module", "repository"]
