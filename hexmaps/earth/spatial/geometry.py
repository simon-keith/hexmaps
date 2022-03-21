from typing import Iterable, Iterator, List, Tuple, Type, Union

from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.geometry.base import BaseGeometry, BaseMultipartGeometry
from shapely.ops import polygonize_full


def extract_base_geometries(
    geom: Union[BaseGeometry, BaseMultipartGeometry]
) -> Iterator[BaseGeometry]:
    if isinstance(geom, BaseMultipartGeometry):
        for g in geom.geoms:
            yield from extract_base_geometries(g)
    elif isinstance(geom, BaseGeometry):
        yield geom


def extract_geometry_type(
    geom: Union[BaseGeometry, BaseMultipartGeometry],
    geom_type: Type[BaseGeometry],
    raise_invalid_type: bool = True,
) -> Iterator[BaseGeometry]:
    for g in extract_base_geometries(geom):
        if isinstance(g, geom_type):
            yield g
        elif raise_invalid_type:
            error = f"expected {geom_type.__name__} but got {type(g).__name__}"
            raise ValueError(error)


def polygonize(
    lines: Iterable[Union[LineString, MultiLineString]],
    allow_dangles: bool = False,
    allow_invalids: bool = False,
) -> Tuple[List[Polygon], List[LineString]]:
    # TODO: try to fix dangles and invalids
    polygons, dangles, cuts, invalids = polygonize_full(lines)
    polygon_list = list(extract_geometry_type(polygons, Polygon))
    line_list = list(extract_geometry_type(cuts, LineString))
    if allow_dangles:
        line_list.extend(extract_geometry_type(dangles, LineString))
    elif len(dangles.geoms) > 0:
        raise ValueError("detected dangling lines")
    if allow_invalids:
        line_list.extend(extract_geometry_type(invalids, LineString))
    elif len(invalids.geoms) > 0:
        raise ValueError("detected invalid lines")
    return polygon_list, line_list


def validate_wgs84_coordinates(lon: float, lat: float) -> Tuple[float, float]:
    if lon is None or not -180 <= lon <= 180:
        raise ValueError("invalid longitude")
    if lat is None or not -90 <= lat <= 90:
        raise ValueError("invalid latitude")
    return lon, lat
