import math
from functools import _CacheInfo, lru_cache
from typing import Iterable, Optional, Sequence, Tuple

import pyproj
from h3.api import basic_int

WGS84_CRS = pyproj.CRS("OGC:CRS84")
WGS84_GEOD = WGS84_CRS.get_geod()


CoordinatesType = Tuple[float, float]
CoordinatesSequenceType = Sequence[CoordinatesType]


class TransformerLRUCache:
    def __init__(self, maxsize: int = 128):
        @lru_cache(maxsize=maxsize, typed=True)
        def get_transformer(
            crs_from: pyproj.CRS = WGS84_CRS,
            crs_to: pyproj.CRS = WGS84_CRS,
            always_xy: bool = False,
        ):
            return pyproj.Transformer.from_crs(
                crs_from=crs_from,
                crs_to=crs_to,
                always_xy=always_xy,
            )

        self._get_transformer_from_cache = get_transformer

    def cache_info(self) -> _CacheInfo:
        return self._get_transformer_from_cache.cache_info()

    def get_transformer(
        self,
        crs_from: pyproj.CRS = WGS84_CRS,
        crs_to: pyproj.CRS = WGS84_CRS,
        always_xy: bool = False,
    ) -> pyproj.Transformer:
        return self._get_transformer_from_cache(
            crs_from=crs_from,
            crs_to=crs_to,
            always_xy=always_xy,
        )


_WGS84_CACHE = TransformerLRUCache()


def get_wgs84_transformer(crs: pyproj.CRS = WGS84_CRS) -> pyproj.Transformer:
    return _WGS84_CACHE.get_transformer(crs_to=crs)


def _mean(seq: Iterable[float]) -> float:
    count = 0
    total = 0
    for x in seq:
        count += 1
        total += x
    return total / count if count > 0 else math.nan


def get_geographic_centroid(coords: CoordinatesSequenceType) -> CoordinatesType:
    lon_rad, lat_rad = zip(
        *((math.radians(lon), math.radians(lat)) for lon, lat in coords)
    )
    lat_cos = tuple(math.cos(y) for y in lat_rad)
    lon_cos = tuple(math.cos(x) for x in lon_rad)
    lat_sin = tuple(math.sin(y) for y in lat_rad)
    lon_sin = tuple(math.sin(x) for x in lon_rad)
    x = _mean(a * b for a, b in zip(lat_cos, lon_cos))
    y = _mean(a * b for a, b in zip(lat_cos, lon_sin))
    z = _mean(lat_sin)
    return (
        math.degrees(math.atan2(y, x)),
        math.degrees(math.atan2(z, math.sqrt(x**2 + y**2))),
    )


def _h3_align(coords: CoordinatesType, h3_resolution: int) -> CoordinatesType:
    lon, lat = coords
    h3_index = basic_int.geo_to_h3(lat, lon, h3_resolution)
    lat, lon = basic_int.h3_to_geo(h3_index)
    return lon, lat


def get_azimuthal_equidistant_crs(
    coords: CoordinatesSequenceType,
    h3_resolution: Optional[int] = None,
) -> pyproj.CRS:
    lon_0, lat_0 = get_geographic_centroid(coords)
    if h3_resolution is not None:
        lon_0, lat_0 = _h3_align((lon_0, lat_0), h3_resolution)
    return pyproj.CRS(projparams=dict(proj="aeqd", lat_0=lat_0, lon_0=lon_0))


def get_azimuthal_conformal_crs(
    coords: CoordinatesSequenceType,
    h3_resolution: Optional[int] = None,
) -> pyproj.CRS:
    lon_0, lat_0 = get_geographic_centroid(coords)
    if h3_resolution is not None:
        lon_0, lat_0 = _h3_align((lon_0, lat_0), h3_resolution)
    return pyproj.CRS(projparams=dict(proj="stere", lat_0=lat_0, lon_0=lon_0))
