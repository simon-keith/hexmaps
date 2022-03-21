from abc import abstractmethod
from enum import Enum
from typing import Any, Dict

import overpy
from hexmaps.earth.spatial.geojson import BaseFeature
from shapely.geometry.base import BaseGeometry


class OverpassFeatureType(str, Enum):
    NODE = "Node"
    WAY = "Way"
    RELATION = "Relation"


class OverpassFeature(BaseFeature):
    def __init__(self, element: overpy.Element, geometry: BaseGeometry) -> None:
        element = self._validate_element(element)
        geometry = self._validate_geometry(geometry)
        self._id = element.id
        self._type = OverpassFeatureType(type(element).__name__)
        self._tags = element.tags
        self._attributes = element.attributes
        self._geometry = geometry

    @property
    def id(self) -> int:
        return self._id

    @property
    def type(self) -> OverpassFeatureType:
        return self._type

    @property
    def tags(self) -> Dict[str, Any]:
        return self._tags.copy()

    @property
    def attributes(self) -> Dict[str, Any]:
        return self._attributes.copy()

    @property
    def geometry(self):
        return self._geometry

    def get_geometry(self):
        return self._geometry

    def get_properties(self) -> Dict[str, Any]:
        return {
            "element": self._type.value,
            "id": self._id,
            **self._tags,
        }

    @classmethod
    @abstractmethod
    def _validate_element(cls, element: overpy.Element) -> overpy.Element:
        return element

    @classmethod
    @abstractmethod
    def _validate_geometry(cls, geometry: BaseGeometry) -> BaseGeometry:
        return geometry

    @classmethod
    @abstractmethod
    def from_element(
        cls,
        element: overpy.Element,
        resolve_missing: bool = True,
        **kwargs,
    ) -> "OverpassFeature":
        pass
