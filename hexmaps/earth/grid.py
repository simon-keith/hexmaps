import random
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from itertools import count
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, Type, Union

from h3.api import basic_int, memview_int
from hexmaps.earth.spatial.geojson import BaseCollection, BaseFeature
from hexmaps.earth.spatial.geometry import validate_wgs84_coordinates
from hexmaps.earth.spatial.proj import WGS84_GEOD
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon as ShapelyPolygon

H3IndexType = int


@dataclass(frozen=True)
class Point(BaseFeature):
    longitude: float
    latitude: float

    def __post_init__(self):
        validate_wgs84_coordinates(self.longitude, self.latitude)

    def get_index(self, resolution: int) -> H3IndexType:
        return memview_int.geo_to_h3(self.latitude, self.longitude, resolution)

    def get_geometry(self) -> ShapelyPoint:
        return ShapelyPoint(self.longitude, self.latitude)

    def get_properties(self) -> Dict[str, Any]:
        return {}


@dataclass(frozen=True)
class Cell(BaseFeature):
    index: H3IndexType
    point: Point = field(init=False, repr=False)

    def __post_init__(self):
        lat, lng = memview_int.h3_to_geo(self.index)
        object.__setattr__(self, "point", Point(latitude=lat, longitude=lng))

    def __eq__(self, other: "Cell") -> bool:
        if not isinstance(other, Cell):
            return NotImplemented
        return self.index == other.index

    def __hash__(self) -> int:
        return hash(self.index)

    @classmethod
    def from_point(cls: Type["Cell"], point: Point, resolution: int) -> "Cell":
        return cls(index=point.get_index(resolution))

    @property
    def is_pentagon(self) -> bool:
        return memview_int.h3_is_pentagon(self.index)

    def get_bearing(self, other: "Cell") -> float:
        fwd, _, _ = WGS84_GEOD.inv(
            self.point.longitude,
            self.point.latitude,
            other.point.longitude,
            other.point.latitude,
        )
        return fwd

    def get_distance(self, other: "Cell") -> float:
        _, _, dist = WGS84_GEOD.inv(
            self.point.longitude,
            self.point.latitude,
            other.point.longitude,
            other.point.latitude,
        )
        return dist

    def get_neighbor_map(self, bearing: float = 0.0) -> Dict[int, "Neighbor"]:
        it = map(Cell, memview_int.hex_ring(self.index, 1))
        angle_it = (((self.get_bearing(n) - bearing) % 360.0, n) for n in it)
        sorted_it = enumerate(sorted(angle_it, key=lambda x: x[0]))
        return {i: Neighbor(cell=n, position=i, angle=a) for i, (a, n) in sorted_it}

    def get_walker(
        self,
        selector: Callable[["Cell", Dict[int, "Neighbor"]], "Neighbor"],
        bearing: float = 0.0,
        iterations: Optional[int] = None,
    ) -> Iterator["Neighbor"]:
        it = range(iterations) if iterations is not None else count()
        cell = self
        for _ in it:
            neighbor = selector(cell, cell.get_neighbor_map(bearing=bearing))
            cell = neighbor.cell
            yield neighbor

    def get_random_walker(
        self,
        iterations: Optional[int] = None,
    ) -> Iterator["Neighbor"]:
        def selector(cell, neighbor_map):
            position = random.randrange(5 if cell.is_pentagon else 6)
            return neighbor_map[position]

        return self.get_walker(selector=selector, iterations=iterations)

    def get_straight_walker(
        self,
        bearing: float = 0.0,
        iterations: Optional[int] = None,
    ) -> Iterator["Neighbor"]:
        def selector(_, neighbor_map):
            return neighbor_map[0]

        return self.get_walker(
            selector=selector,
            bearing=bearing,
            iterations=iterations,
        )

    def get_geometry(self) -> ShapelyPolygon:
        ((shell, *holes),) = basic_int.h3_set_to_multi_polygon(
            [self.index],
            geo_json=True,
        )
        return ShapelyPolygon(shell=shell, holes=holes)

    def get_properties(self) -> Dict[str, Any]:
        return {"index": self.index}


@dataclass(frozen=True)
class Neighbor(BaseFeature):
    cell: Cell
    position: int
    angle: float

    def __post_init__(self):
        assert 0 <= self.position <= 5, "invalid position"
        assert 0 <= self.angle < 360, "invalid angle"

    def __eq__(self, other: "Neighbor") -> bool:
        if not isinstance(other, Neighbor):
            return NotImplemented
        return self.cell == other.cell

    def __hash__(self) -> int:
        return hash(self.cell)

    def get_geometry(self) -> ShapelyPolygon:
        return self.cell.get_geometry()

    def get_properties(self) -> Dict[str, Any]:
        return {
            **self.cell.get_properties(),
            "position": self.position,
            "angle": self.angle,
        }


@dataclass(frozen=True)
class GridCell(BaseFeature):
    cell: Cell
    key: int
    coordinates: Tuple[int, int]

    def get_geometry(self) -> ShapelyPolygon:
        return self.cell.get_geometry()

    def get_properties(self) -> Dict[str, Any]:
        return {
            **self.cell.get_properties(),
            "key": self.key,
            "coordinates": self.coordinates,
        }


class Grid(Mapping, BaseCollection):
    _SHIFT_NEIGHBOR_J = {0: 1, 1: 0, 2: -1, 3: -1, 4: 0, 5: 1}
    _SHIFT_NEIGHBOR_I_EVEN = {0: 0, 1: 1, 2: 0, 3: -1, 4: -1, 5: -1}
    _SHIFT_NEIGHBOR_I_ODD = {0: 1, 1: 1, 2: 1, 3: 0, 4: -1, 5: 0}

    def __init__(self, height: int, width: int, bearing: float = 0.0) -> None:
        if not (height > 0 and width > 0):
            raise ValueError("map dimensions must be positive")
        self._height = height
        self._width = width
        self._bearing = bearing
        self._cell_map: Dict[int, GridCell] = {}

    @property
    def height(self):
        return self._height

    @property
    def width(self):
        return self._width

    def __getitem__(self, key: Union[int, Tuple[int, int]]) -> GridCell:
        if isinstance(key, tuple) and len(key) == 2:
            key = self.coordinates_to_key(key)
        elif not isinstance(key, int):
            raise KeyError("key type must be Union[int, Tuple[int, int]]")
        return self._cell_map[key]

    def __len__(self) -> int:
        return len(self._cell_map)

    def __iter__(self) -> Iterator[Tuple[int, int]]:
        return iter(self._cell_map)

    def coordinates_to_key(self, coordinates: Tuple[int, int]) -> int:
        i, j = coordinates
        return i + self._width * j

    def key_to_coordinates(self, key: int) -> Tuple[int, int]:
        i = key % self._width
        j = key // self._width
        return i, j

    def expand_from_cell(self, init_cell: Cell) -> "Grid":
        self._cell_map.clear()
        init_cell_coordinates = self._width // 2, self._height // 2
        queue = deque([(init_cell_coordinates, init_cell)])
        visited = set([init_cell])
        while len(queue) > 0:
            coordinates, cell = queue.pop()
            if cell.is_pentagon:
                raise ValueError("cannot build grid with pentagons")
            key = self.coordinates_to_key(coordinates)
            self._cell_map[key] = GridCell(cell=cell, key=key, coordinates=coordinates)
            for position, neighbor in cell.get_neighbor_map(self._bearing).items():
                if neighbor.cell not in visited:
                    visited.add(neighbor.cell)
                    i, j = coordinates
                    neighbor_i = i + (
                        self._SHIFT_NEIGHBOR_I_EVEN[position]
                        if j % 2 == 0
                        else self._SHIFT_NEIGHBOR_I_ODD[position]
                    )
                    neighbor_j = j + self._SHIFT_NEIGHBOR_J[position]
                    if 0 <= neighbor_i < self._width and 0 <= neighbor_j < self._height:
                        queue.appendleft(((neighbor_i, neighbor_j), neighbor.cell))
        return self

    def expand_from_point(self, point: Point, resolution: int) -> "Grid":
        cell = Cell.from_point(point, resolution)
        return self.expand_from_cell(cell)

    def get_features(self) -> List[Dict[str, Any]]:
        return list(f.__geo_interface__ for f in self._cell_map.values())
