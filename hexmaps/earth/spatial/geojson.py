from abc import ABC, abstractmethod
from collections.abc import Sequence as ABCSequence
from typing import Any, Dict, List, Sequence, Union

from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry


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


class BaseCollection(GeoInterface):
    @abstractmethod
    def get_features(self) -> List[Dict[str, Any]]:
        pass

    @property
    def __geo_interface__(self) -> Dict[str, Any]:
        return {
            "type": "FeatureCollection",
            "features": self.get_features(),
        }


def validate_feature_data(data: Dict[str, Any]) -> Dict[str, Any]:
    if data.get("type") != "Feature":
        raise ValueError("type must be 'Feature'")
    if "geometry" not in data:
        raise ValueError("missing geometry")
    if "properties" not in data:
        raise ValueError("missing properties")
    return data


def validate_collection_data(data: Dict[str, Any]) -> Dict[str, Any]:
    if data.get("type") != "FeatureCollection":
        raise ValueError("type must be 'FeatureCollection'")
    if "features" not in data:
        raise ValueError("missing features")
    for f in data["features"]:
        validate_feature_data(f)
    return data


def validate_geojson_data(data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return validate_feature_data(data)
    except ValueError:
        pass
    try:
        return validate_collection_data(data)
    except ValueError:
        pass
    raise ValueError("must be a valid 'Feature' or 'FeatureCollection'")


def get_geojson_data(geo: GeoInterface) -> Dict[str, Any]:
    return validate_geojson_data(geo.__geo_interface__)


GeoOrGeoSequence = Union[GeoInterface, Sequence[GeoInterface]]


def get_feature_collection(geo: GeoOrGeoSequence) -> Dict[str, Any]:
    if isinstance(geo, ABCSequence):
        features = [validate_feature_data(g.__geo_interface__) for g in geo]
        return {
            "type": "FeatureCollection",
            "features": features,
        }
    data = geo.__geo_interface__
    if data.get("type") == "Feature":
        return {
            "type": "FeatureCollection",
            "features": [validate_feature_data(data)],
        }
    return validate_collection_data(data)
