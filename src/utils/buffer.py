import time
from collections import deque
from functools import reduce
from typing import Deque, Generic, Optional, Protocol, TypeVar

T = TypeVar("T")


class Buffer(Generic[T]):
    def __init__(self, max_size: int, max_life: float = 1) -> None:
        assert max_size > 0
        assert max_life > 0

        self.max_size = max_size
        self.max_life = max_life
        self.buffer: Deque[T] = deque(maxlen=max_size)
        self.buffer_timestamps: Deque[float] = deque(maxlen=max_size)

    def add(self, value: T) -> None:
        self.buffer.append(value)
        self.buffer_timestamps.append(time.time())

    def items(self) -> Deque[T]:
        while (
            len(self.buffer) > 0
            and time.time() - self.buffer_timestamps[0] > self.max_life
        ):
            self.buffer.popleft()
            self.buffer_timestamps.popleft()

        return self.buffer

    def clear(self) -> None:
        self.buffer.clear()
        self.buffer = deque(maxlen=self.max_size)

    def mode(self) -> Optional[T]:
        items = self.items()

        if len(items) == 0:
            return None
        return max(set(items), key=items.count)

    def first(self) -> Optional[T]:
        items = self.items()

        if len(items) == 0:
            return None
        return items[0]

    def last(self) -> Optional[T]:
        items = self.items()

        if len(items) == 0:
            return None
        return items[-1]

    def __str__(self) -> str:
        return str(self.items())

    def __repr__(self) -> str:
        return str(self)


U = TypeVar("U", bound="UBound")


class UBound(Protocol):
    def __add__(self: T, other: T) -> T: ...
    def __truediv__(self: T, other: int) -> T: ...


class ArithmeticBuffer(Buffer[U]):
    def __init__(self, max_size: int, max_life: float = 1) -> None:
        super().__init__(max_size, max_life)

    def average(self) -> Optional[U]:
        items = self.items()

        if len(items) == 0:
            return None
        return reduce(lambda x, y: x + y, items) / len(items)
