from typing import Callable, TypeVar

from ..core import COMPARATOR_TYPE_REGISTRY, Comparator

T = TypeVar('T', bound=Comparator)


def register(id: str) -> Callable[[type[T]], type[T]]:
    def wrapper(cls: type[T]) -> type[T]:
        cls.id = id
        COMPARATOR_TYPE_REGISTRY[id] = cls
        return cls

    return wrapper


def load_comparators() -> list[type[Comparator]]:
    from . import files  # noqa: F401
    from . import pcap  # noqa: F401
    from . import primitives  # noqa: F401

    return list(COMPARATOR_TYPE_REGISTRY.values())
