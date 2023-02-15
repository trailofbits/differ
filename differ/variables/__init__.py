from typing import Callable, TypeVar

from ..core import VARIABLE_TYPE_REGISTRY, FuzzVariable

T = TypeVar('T', bound=FuzzVariable)


def register(id: str) -> Callable[[type[T]], type[T]]:
    def wrapper(cls: type[T]) -> type[T]:
        cls.id = id
        VARIABLE_TYPE_REGISTRY[id] = cls
        return cls

    return wrapper


def load_variables() -> list[type[FuzzVariable]]:
    from . import primitives  # noqa: F401
    from . import radamsa  # noqa: F401

    return list(VARIABLE_TYPE_REGISTRY.values())
