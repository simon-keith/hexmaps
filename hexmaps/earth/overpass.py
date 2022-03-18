import itertools
import math
import re
from abc import abstractmethod
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import overpy
from hexmaps.earth.geo import PYPROJ_CRS, BaseFeature
from hexmaps.utilities import nwise
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPolygon,
    Point,
    Polygon,
)
from shapely.geometry.base import BaseGeometry


def build_node_geometry(
    element: Union[overpy.Node, overpy.RelationNode],
    resolve_missing: bool = False,
) -> Point:
    if isinstance(element, overpy.RelationNode):
        try:
            return Point(element.attributes.get("lon"), element.attributes.get("lat"))
        except TypeError:
            element: overpy.Node = element.resolve(resolve_missing=resolve_missing)
    try:
        return Point(element.lon, element.lat)
    except TypeError as e:
        raise ValueError("missing geometry") from e


def _get_way_points(
    element: Union[overpy.Way, overpy.RelationWay],
    resolve_missing: bool,
) -> List[Point]:
    if isinstance(element, overpy.RelationWay):
        try:
            return [Point(g.lon, g.lat) for g in element.geometry]
        except TypeError:
            element: overpy.Way = element.resolve(resolve_missing=resolve_missing)
    try:
        return [Point(g["lon"], g["lat"]) for g in element.attributes.get("geometry")]
    except TypeError:
        return [
            build_node_geometry(element=n, resolve_missing=resolve_missing)
            for n in element.get_nodes(resolve_missing=resolve_missing)
        ]


def _get_ring_area(points: List[Point]) -> float:
    if len(points) < 3:
        return 0
    radius = PYPROJ_CRS.ellipsoid.semi_major_metre
    area = sum(
        (math.radians(p3.x) - math.radians(p1.x)) * math.sin(math.radians(p2.y))
        for p1, p2, p3 in nwise(points, n=3, cycle=True)
    )
    area *= radius**2 / 2
    return area


def _rewind_ring(points: List[Point], clockwise: bool) -> List[Point]:
    is_clockwise = _get_ring_area(points) >= 0
    if is_clockwise == clockwise:
        return points
    return points[::-1]


def build_way_geometry(
    element: Union[overpy.Way, overpy.RelationWay],
    resolve_missing: bool = False,
    clockwise: bool = False,
) -> Union[LineString, Polygon]:
    points = _get_way_points(element, resolve_missing)
    if points[0] == points[-1]:
        return Polygon(_rewind_ring(points, clockwise=clockwise))
    return LineString(points)


def build_relation_geometry(
    element: Union[overpy.Relation, overpy.RelationRelation],
    resolve_missing: bool = False,
) -> GeometryCollection:
    if isinstance(element, overpy.RelationRelation):
        element = element.resolve(resolve_missing=resolve_missing)
    members: List[overpy.RelationMember] = element.members
    node_list, way_list, relation_list = [], [], []
    for m in members:
        if isinstance(m, overpy.RelationNode):
            node_list.append(build_node_geometry(m, resolve_missing))
        elif isinstance(m, overpy.RelationWay):
            way_list.append(build_way_geometry(m, resolve_missing))
        elif isinstance(m, overpy.RelationRelation):
            relation_list.append(build_relation_geometry(m, resolve_missing))
        else:
            raise ValueError(f"unsupported relation type '{type(m).__name__}'")
    return GeometryCollection(
        node_list
        + way_list
        + list(itertools.chain.from_iterable(r.geoms for r in relation_list))
    )


class OverpassFeature(BaseFeature):
    _REPR_PATTERN = re.compile(r"overpy\.\w+")

    def __init__(self, element: overpy.Element, resolve_missing: bool = False) -> None:
        self._element = self._validate_element(element)
        self._geometry = self._parse_geometry(resolve_missing=resolve_missing)

    @property
    def element(self):
        return self._element

    @property
    def type(self) -> str:
        return type(self._element).__name__

    @abstractmethod
    def _validate_element(self, element: overpy.Element) -> overpy.Element:
        return element

    @abstractmethod
    def _parse_geometry(self, resolve_missing: bool) -> BaseGeometry:
        pass

    def get_properties(self) -> Dict[str, Any]:
        return {
            "element": self.type,
            "id": self._element.id,
            **self._element.tags,
        }

    def get_geometry(self) -> BaseGeometry:
        return self._geometry

    def __repr__(self) -> str:
        return self._REPR_PATTERN.sub(type(self).__name__, super().__repr__())


class NodeFeature(OverpassFeature):
    def _validate_element(self, element: overpy.Element) -> overpy.Node:
        assert isinstance(element, overpy.Node), "element must be a node"
        return super()._validate_element(element)

    def _parse_geometry(self, resolve_missing: bool) -> Point:
        return build_node_geometry(self._element, resolve_missing=resolve_missing)

    def get_geometry(self) -> Point:
        return super().get_geometry()


class WayFeature(OverpassFeature):
    def _validate_element(self, element: overpy.Element) -> overpy.Way:
        assert isinstance(element, overpy.Way), "element must be a way"
        return super()._validate_element(element)

    def _parse_geometry(self, resolve_missing: bool) -> Union[LineString, Polygon]:
        return build_way_geometry(self._element, resolve_missing=resolve_missing)

    def get_geometry(self) -> Union[LineString, Polygon]:
        return super().get_geometry()


class RelationFeature(OverpassFeature):
    def _validate_element(self, element: overpy.Element) -> overpy.Relation:
        assert isinstance(element, overpy.Relation), "element must be a relation"
        return super()._validate_element(element)

    def _parse_geometry(
        self,
        resolve_missing: bool,
    ) -> Union[MultiLineString, MultiPolygon, GeometryCollection]:
        return build_relation_geometry(self._element, resolve_missing=resolve_missing)

    def get_geometry(self) -> GeometryCollection:
        return super().get_geometry()


@dataclass
class BBox:
    west: float
    south: float
    east: float
    north: float


class Recurse(Enum):
    NONE = ""
    DOWN = ">;"
    DOWN_RELATIONS = ">>;"
    UP = "<;"
    UP_RELATIONS = "<<;"


def build_union_query(
    union_block: str,
    bbox: Optional[BBox] = None,
    recurse: Recurse = Recurse.NONE,
    timeout: timedelta = timedelta(minutes=1),
    maxsize: int = 536870912,
) -> str:
    union_block = union_block.strip()
    if not union_block.startswith("(") and not union_block.endswith(");"):
        raise ValueError("argument is not a Union block statement")
    query_parts = [
        "[out:json]",
        f"[timeout:{math.floor(timeout.total_seconds())}]",
        f"[maxsize:{maxsize}]",
    ]
    if bbox:
        query_parts.append(f"[bbox:{bbox.south},{bbox.west},{bbox.north},{bbox.east}]")
    query_parts.append(";")
    query_parts.append(union_block)
    if recurse != Recurse.NONE:
        query_parts.append(f"(._; {recurse.value});")
    query_parts.append("out geom;")
    query = "\n".join(query_parts)
    return query


def get_elements(
    result: overpy.Result,
) -> Tuple[List[overpy.Node], List[overpy.Way], List[overpy.Relation]]:
    return (
        result.get_nodes(),
        result.get_ways(),
        result.get_relations(),
    )


def get_features(
    result: overpy.Result,
    resolve_missing: bool = False,
) -> Tuple[List[NodeFeature], List[WayFeature], List[RelationFeature]]:
    nodes, ways, relations = get_elements(result)
    node_features = [NodeFeature(n, resolve_missing) for n in nodes]
    way_features = [WayFeature(w, resolve_missing) for w in ways]
    relation_features = [RelationFeature(r, resolve_missing) for r in relations]
    return node_features, way_features, relation_features


class Overpass(overpy.Overpass):
    _OUT_PARAMS_PATTERN = re.compile(r"out\s*;|out\s+([\w\s]+);")
    _ID_FILTER_PATTERN = re.compile(
        r"(relation|rel|way|node)\s?\(\s?(id\s?:)?([\s\d\,]+)\)\s?;"
    )
    default_url = "https://overpass.kumi.systems/api/interpreter"

    def __init__(
        self,
        *args,
        default_output_geometries: bool = True,
        default_recurse_id_filters: bool = True,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.default_output_geometries = default_output_geometries
        self.default_recurse_id_filters = default_recurse_id_filters

    @staticmethod
    def _sub_output_params(match: re.Match) -> str:
        (out_params,) = match.groups()
        out_param_set = {"geom"}
        if out_params is not None:
            out_param_set.update(out_params.split())
        return f'out {" ".join(out_param_set)};'

    @staticmethod
    def _sub_id_filter(match: re.Match) -> str:
        start, end = match.start(), match.end()
        substring = match.string[start:end]
        return f"({substring} {Recurse.DOWN.value});"

    def format_query(
        self,
        query: str,
        *,
        output_geometries: Optional[bool] = None,
        recurse_id_filters: Optional[bool] = None,
    ) -> str:
        # get arguments
        output_geometries = (
            self.default_output_geometries
            if output_geometries is None
            else output_geometries
        )
        recurse_id_filters = (
            self.default_recurse_id_filters
            if recurse_id_filters is None
            else recurse_id_filters
        )
        # stip whitespace
        query = "\n".join(line.rstrip() for line in query.split("\n")).strip()
        # optionally add recurse operator to id filters
        if recurse_id_filters:
            query = self._ID_FILTER_PATTERN.sub(self._sub_id_filter, query)
        # optionally add geom to output format params
        if output_geometries:
            query = self._OUT_PARAMS_PATTERN.sub(self._sub_output_params, query)
        return query

    def query(
        self,
        query: str,
        *,
        output_geometries: Optional[bool] = None,
        recurse_id_filters: Optional[bool] = None,
    ) -> overpy.Result:
        query = self.format_query(
            query,
            output_geometries=output_geometries,
            recurse_id_filters=recurse_id_filters,
        )
        return super().query(query)

    def query_raw(self, query: str) -> overpy.Result:
        return super().query(query)

    def query_elements(
        self,
        query: str,
        *,
        output_geometries: Optional[bool] = None,
        recurse_id_filters: Optional[bool] = None,
    ) -> Tuple[List[overpy.Node], List[overpy.Way], List[overpy.Relation]]:
        result = self.query(
            query=query,
            output_geometries=output_geometries,
            recurse_id_filters=recurse_id_filters,
        )
        return get_elements(result=result)

    def query_features(
        self,
        query: str,
        resolve_missing: bool = False,
        *,
        output_geometries: Optional[bool] = None,
        recurse_id_filters: Optional[bool] = None,
    ) -> Tuple[List[NodeFeature], List[WayFeature], List[RelationFeature]]:
        result = self.query(query=query)
        return get_features(
            result=result,
            output_geometries=output_geometries,
            recurse_id_filters=recurse_id_filters,
            resolve_missing=resolve_missing,
        )
