from typing import Callable

from ..core import VARIABLE_TYPE_REGISTRY, FuzzVariable


def register(id: str) -> Callable[[type[FuzzVariable]], type[FuzzVariable]]:
    def wrapper(cls: type[FuzzVariable]) -> type[FuzzVariable]:
        cls.id = id
        VARIABLE_TYPE_REGISTRY[id] = cls
        return cls

    return wrapper


def load_variables() -> list[type[FuzzVariable]]:
    from . import primitives  # noqa: F401

    return list(VARIABLE_TYPE_REGISTRY.values())
