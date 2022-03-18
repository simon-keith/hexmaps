import itertools
from typing import Iterable, Iterator, Tuple, TypeVar

_T = TypeVar("_T")


def nwise(it: Iterable[_T], n: int, cycle: bool = False) -> Iterator[Tuple[_T, ...]]:
    if n < 1:
        raise ValueError("n must be at least 1")
    iterators = list(itertools.tee(it, n))
    for i in range(1, n):
        if cycle:
            iterators[i] = itertools.cycle(iterators[i])
        iterators[i] = itertools.islice(iterators[i], i, None)
    return zip(*iterators)
