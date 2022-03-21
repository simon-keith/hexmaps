from typing import Tuple, Union, get_args

import overpy
from hexmaps.earth.overpass import node
from hexmaps.earth.overpass.base import OverpassFeature
from hexmaps.earth.spatial.geometry import polygonize as _polygonize
from hexmaps.earth.spatial.geometry import validate_wgs84_coordinates
from shapely.geometry import LineString, Polygon
from shapely.geometry.polygon import orient

WayCoordinatesType = Tuple[node.NodeCoordinatesType, ...]
WayGeometryType = Union[LineString, Polygon]


def get_way_coordinates(
    element: Union[overpy.Way, overpy.RelationWay],
    resolve_missing: bool = False,
) -> WayCoordinatesType:
    if isinstance(element, overpy.RelationWay):
        try:
            return tuple(
                validate_wgs84_coordinates(g.lon, g.lat) for g in element.geometry
            )
        except (TypeError, ValueError):
            # element.geometry is None or invalid coordinates
            element: overpy.Way = element.resolve(resolve_missing=resolve_missing)
    try:
        return tuple(
            validate_wgs84_coordinates(g["lon"], g["lat"])
            for g in element.attributes.get("geometry")
        )
    except (TypeError, ValueError):
        # element.attributes.get("geometry") is None or invalid coordinates
        return tuple(
            node.get_node_coordinates(element=n, resolve_missing=resolve_missing)
            for n in element.get_nodes(resolve_missing=resolve_missing)
        )


def build_way_geometry(
    element: Union[overpy.Way, overpy.RelationWay],
    resolve_missing: bool = False,
    polygonize: bool = True,
) -> WayGeometryType:
    line = LineString(
        get_way_coordinates(
            element=element,
            resolve_missing=resolve_missing,
        )
    )
    if not polygonize:
        return line
    polygon_tuple, line_tuple = _polygonize(line)
    polygon_len, line_len = len(polygon_tuple), len(line_tuple)
    if polygon_len == 1 and line_len == 0:
        return orient(polygon_tuple[0])
    if polygon_len == 0 and line_len == 1:
        return line_tuple[0]
    raise ValueError("polygonize generated unexpected geometries")


class WayFeature(OverpassFeature):
    @classmethod
    def _validate_element(cls, element: overpy.Way) -> overpy.Way:
        if not isinstance(element, overpy.Way):
            raise ValueError("element must be a way")
        return element

    @classmethod
    def _validate_geometry(cls, geometry: WayGeometryType) -> WayGeometryType:
        if not isinstance(geometry, get_args(WayGeometryType)):
            raise ValueError("invalid geometry type")
        return geometry

    @classmethod
    def from_element(
        cls,
        element: overpy.Element,
        resolve_missing: bool = True,
        polygonize: bool = True,
    ) -> "WayFeature":
        geometry = build_way_geometry(
            element=element,
            resolve_missing=resolve_missing,
            polygonize=polygonize,
        )
        return cls(element=element, geometry=geometry)
