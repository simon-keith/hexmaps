from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable

import pyproj
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry

PYPROJ_CRS = pyproj.CRS("OGC:CRS84")
PYPROJ_GEOD = PYPROJ_CRS.get_geod()


class GeoInterface(ABC):
    @property
    @abstractmethod
    def __geo_interface__(self) -> Dict[str, Any]:
        pass


class BaseFeature(GeoInterface):
    @abstractmethod
    def get_geometry(self) -> BaseGeometry:
        pass

    @abstractmethod
    def get_properties(self) -> Dict[str, Any]:
        pass

    @property
    def __geo_interface__(self) -> Dict[str, Any]:
        return {
            "type": "Feature",
            "geometry": mapping(self.get_geometry()),
            "properties": self.get_properties(),
        }


def build_geojson_data(geo_iterable: Iterable[GeoInterface]) -> Dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": tuple(map(mapping, geo_iterable)),
    }
