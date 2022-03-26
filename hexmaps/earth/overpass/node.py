from typing import Tuple, Union

import overpy
from hexmaps.earth.overpass.base import OverpassFeature
from hexmaps.earth.spatial.geometry import validate_wgs84_coordinates
from shapely.geometry import Point

NodeCoordinatesType = Tuple[float, float]
NodeGeometryType = Point


def get_node_coordinates(
    element: Union[overpy.Node, overpy.RelationNode],
    resolve_missing: bool = False,
) -> NodeCoordinatesType:
    if isinstance(element, overpy.RelationNode):
        try:
            return validate_wgs84_coordinates(
                element.attributes.get("lon"),
                element.attributes.get("lat"),
            )
        except ValueError:
            element: overpy.Node = element.resolve(resolve_missing=resolve_missing)
    return validate_wgs84_coordinates(element.lon, element.lat)


def build_node_geometry(
    element: Union[overpy.Node, overpy.RelationNode],
    resolve_missing: bool = False,
) -> NodeGeometryType:
    lon, lat = get_node_coordinates(element=element, resolve_missing=resolve_missing)
    return Point(lon, lat)


class NodeFeature(OverpassFeature):
    @classmethod
    def _validate_element(cls, element: overpy.Node) -> overpy.Node:
        if not isinstance(element, overpy.Node):
            raise ValueError("element must be a node")
        return element

    @classmethod
    def _validate_geometry(cls, geometry: NodeGeometryType) -> NodeGeometryType:
        if not isinstance(geometry, Point):
            raise ValueError("invalid geometry type")
        return geometry

    @classmethod
    def from_element(
        cls,
        element: overpy.Element,
        resolve_missing: bool = False,
    ) -> "NodeFeature":
        geometry = build_node_geometry(element=element, resolve_missing=resolve_missing)
        return cls(element=element, geometry=geometry)
