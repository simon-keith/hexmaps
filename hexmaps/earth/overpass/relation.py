from typing import List, Sequence, Tuple, Union, get_args

import overpy
from hexmaps.earth.overpass import node, way
from hexmaps.earth.overpass.base import OverpassFeature
from hexmaps.earth.spatial.geometry import polygonize
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)
from shapely.geometry.polygon import orient

RelationCoordinatesType = Tuple[
    Tuple[node.NodeCoordinatesType, ...], Tuple[way.WayCoordinatesType, ...]
]
RelationGeometryType = Union[
    GeometryCollection,
    MultiPolygon,
    MultiLineString,
    MultiPoint,
    Polygon,
    LineString,
    Point,
]


def _recurse_relation(
    element: Union[overpy.Relation, overpy.RelationRelation],
    resolve_missing: bool,
    node_member_list: List[overpy.RelationNode],
    way_member_list: List[overpy.RelationWay],
):
    # TODO: keep nested relations grouped
    if isinstance(element, overpy.RelationRelation):
        element = element.resolve(resolve_missing=resolve_missing)
    for m in element.members:
        if isinstance(m, overpy.RelationNode):
            node_member_list.append(m)
        elif isinstance(m, overpy.RelationWay):
            way_member_list.append(m)
        elif isinstance(m, overpy.RelationRelation):
            _recurse_relation(
                element=m,
                resolve_missing=resolve_missing,
                node_member_list=node_member_list,
                way_member_list=way_member_list,
            )
        else:
            raise ValueError(f"unsupported relation type '{type(m).__name__}'")


def _get_node_and_way_members(
    element: Union[overpy.Relation, overpy.RelationRelation],
    resolve_missing: bool,
) -> Tuple[List[overpy.RelationNode], List[overpy.RelationWay]]:
    node_member_list, way_member_list = [], []
    _recurse_relation(
        element=element,
        resolve_missing=resolve_missing,
        node_member_list=node_member_list,
        way_member_list=way_member_list,
    )
    return node_member_list, way_member_list


def get_relation_coordinates(
    element: Union[overpy.Way, overpy.RelationWay],
    resolve_missing: bool = False,
) -> RelationCoordinatesType:
    node_member_list, way_member_list = _get_node_and_way_members(
        element=element,
        resolve_missing=resolve_missing,
    )
    node_coordinates_tuple = tuple(
        node.get_node_coordinates(
            element=n,
            resolve_missing=resolve_missing,
        )
        for n in node_member_list
    )
    way_coordinates_tuple = tuple(
        way.get_way_coordinates(
            element=w,
            resolve_missing=resolve_missing,
        )
        for w in way_member_list
    )
    return node_coordinates_tuple, way_coordinates_tuple


def _merge_polygons(polygons: Sequence[Polygon]) -> MultiPolygon:
    # TODO: identify exteriors and interiors and merge
    return MultiPolygon(orient(p) for p in polygons)


def _build_relation_geometries(
    element: Union[overpy.Relation, overpy.RelationRelation],
    resolve_missing: bool,
) -> Tuple[MultiPolygon, MultiLineString, MultiPoint]:
    # get nodes and ways
    node_member_list, way_member_list = _get_node_and_way_members(
        element=element,
        resolve_missing=resolve_missing,
    )
    # generate point, line and polygon geometries
    point_list = [
        node.build_node_geometry(element=n, resolve_missing=resolve_missing)
        for n in node_member_list
    ]
    polygon_list, line_list = polygonize(
        # TODO: fix dangles and invalids rather than allowing them
        lines=(
            way.build_way_geometry(
                element=w,
                resolve_missing=resolve_missing,
                polygonize=False,
            )
            for w in way_member_list
        ),
        allow_dangles=True,
        allow_invalids=True,
    )
    # create collections
    multi_point = MultiPoint(point_list)
    multi_line = MultiLineString(line_list)
    multi_polygon = _merge_polygons(polygon_list)
    # return collections
    return (multi_polygon, multi_line, multi_point)


def build_relation_geometry(
    element: Union[overpy.Relation, overpy.RelationRelation],
    resolve_missing: bool = False,
) -> RelationGeometryType:
    geometry_list = [
        g.geoms[0] if len(g.geoms) == 1 else g
        for g in _build_relation_geometries(
            element=element,
            resolve_missing=resolve_missing,
        )
        if len(g.geoms) > 0
    ]
    if len(geometry_list) == 1:
        return geometry_list[0]
    return GeometryCollection(geometry_list)


class RelationFeature(OverpassFeature):
    @classmethod
    def _validate_element(cls, element: overpy.Relation) -> overpy.Relation:
        if not isinstance(element, overpy.Relation):
            raise ValueError("element must be a relation")
        return element

    @classmethod
    def _validate_geometry(cls, geometry: RelationGeometryType) -> RelationGeometryType:
        if not isinstance(geometry, get_args(RelationGeometryType)):
            raise ValueError("invalid geometry type")
        return geometry

    @classmethod
    def from_element(
        cls,
        element: overpy.Element,
        resolve_missing: bool = True,
    ) -> "RelationFeature":
        geometry = build_relation_geometry(
            element=element,
            resolve_missing=resolve_missing,
        )
        return cls(element=element, geometry=geometry)

    @classmethod
    def split_element(
        cls,
        element: overpy.Element,
        resolve_missing: bool = True,
    ) -> Tuple["RelationFeature", ...]:
        geometry = build_relation_geometry(
            element=element,
            resolve_missing=resolve_missing,
        )
        if not isinstance(geometry, GeometryCollection):
            return (cls(element=element, geometry=geometry),)
        return tuple(cls(element=element, geometry=g) for g in geometry.geoms)
