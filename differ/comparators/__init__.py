from typing import Callable

from ..core import COMPARATOR_TYPE_REGISTRY, Comparator


def register(id: str) -> Callable[[type[Comparator]], type[Comparator]]:
    def wrapper(cls: type[Comparator]) -> type[Comparator]:
        cls.id = id
        COMPARATOR_TYPE_REGISTRY[id] = cls
        return cls

    return wrapper


def load_comparators() -> list[type[Comparator]]:
    from . import primitives  # noqa: F401

    return list(COMPARATOR_TYPE_REGISTRY.values())
