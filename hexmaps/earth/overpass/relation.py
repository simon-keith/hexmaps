from collections import OrderedDict, deque
from typing import Dict, List, Tuple, Union, get_args

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
    Tuple[node.NodeCoordinatesType, ...],
    Tuple[way.WayCoordinatesType, ...],
    Tuple["RelationCoordinatesType", ...],
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


class RecursedRelation:
    def __init__(
        self,
        element: Union[overpy.Relation, overpy.RelationRelation],
        resolve_missing: bool = False,
    ) -> None:
        if isinstance(element, overpy.RelationRelation):
            element = element.resolve(resolve_missing=resolve_missing)
        node_list, way_list, relation_list = [], [], []
        for m in element.members:
            if isinstance(m, overpy.RelationNode):
                node_list.append(m)
            elif isinstance(m, overpy.RelationWay):
                way_list.append(m)
            elif isinstance(m, overpy.RelationRelation):
                relation_list.append(
                    type(self)(element=m, resolve_missing=resolve_missing)
                )
            else:
                raise ValueError(f"unsupported relation type '{type(m).__name__}'")
        self._resolve_missing = resolve_missing
        self.nodes: Tuple[overpy.RelationNode] = tuple(node_list)
        self.ways: Tuple[overpy.RelationWay] = tuple(way_list)
        self.relations: Tuple["RecursedRelation"] = tuple(relation_list)

    def get_coordinates(self) -> RelationCoordinatesType:
        nodes = tuple(
            node.get_node_coordinates(element=n, resolve_missing=self._resolve_missing)
            for n in self.nodes
        )
        ways = tuple(
            way.get_way_coordinates(element=w, resolve_missing=self._resolve_missing)
            for w in self.ways
        )
        relations = tuple(
            r.get_coordinates(resolve_missing=self._resolve_missing)
            for r in self.relations
        )
        return nodes, ways, relations

    def _recurse_geometries(
        self,
        allow_dangles: bool,
        allow_invalids: bool,
    ) -> Tuple[List[Point], List[LineString], List[Polygon]]:
        point_list, line_list, polygon_list = [], [], []
        # get children geometries
        for rel in self.relations:
            pt, ln, pg = rel._recurse_geometries(
                allow_dangles=allow_dangles,
                allow_invalids=allow_invalids,
            )
            point_list.extend(pt)
            line_list.extend(ln)
            polygon_list.extend(pg)
        # build own geometries
        point_list.extend(
            node.build_node_geometry(element=n, resolve_missing=self._resolve_missing)
            for n in self.nodes
        )
        pg, ln = polygonize(
            lines=(
                way.build_way_geometry(element=w, resolve_missing=self._resolve_missing)
                for w in self.ways
            ),
            allow_dangles=allow_dangles,
            allow_invalids=allow_invalids,
        )
        line_list.extend(ln)
        polygon_list.extend(pg)
        # return final lists
        return point_list, line_list, polygon_list

    def get_geometry(
        self,
        repolygonize: bool = True,
        allow_dangles: bool = True,
        allow_invalids: bool = True,
    ) -> RelationGeometryType:
        point_list, line_list, polygon_list = self._recurse_geometries(
            allow_dangles=allow_dangles,
            allow_invalids=allow_invalids,
        )
        if repolygonize:
            new_polygon_list, line_list = polygonize(
                lines=line_list,
                allow_dangles=allow_dangles,
                allow_invalids=allow_invalids,
            )
            polygon_list.extend(new_polygon_list)
        return GeometryCollection(
            point_list + line_list + [orient(p) for p in polygon_list]
        )
        # geoms = (
        #     MultiPoint(point_list),
        #     MultiLineString(line_list),
        #     MultiPolygon(orient(p) for p in polygon_list),
        # )
        # geoms = tuple(
        #     g if len(g.geoms) > 1 else g.geoms[0] for g in geoms if len(g.geoms) > 0
        # )
        # if len(geoms) == 1:
        #     return geoms[0]
        # return GeometryCollection(geoms)

    def to_dict_tree(
        self,
        reverse: bool = False,
    ) -> Dict[int, Tuple["RecursedRelation", Tuple[int, ...]]]:
        current_index = 0
        queue = deque([(current_index, self)])
        tree = OrderedDict()
        while len(queue) > 0:
            rel_index, rel = queue.pop()
            rel_children_indexes = []
            for child in rel.relations:
                current_index += 1
                rel_children_indexes.append(current_index)
                queue.appendleft((current_index, child))
            tree[rel_index] = rel, tuple(rel_children_indexes)
        if reverse:
            tree = OrderedDict(sorted(tree.items(), reverse=reverse))
        return tree


def get_relation_coordinates(
    element: Union[overpy.Relation, overpy.RelationRelation],
    resolve_missing: bool = False,
) -> RelationCoordinatesType:
    recursed_relation = RecursedRelation(
        element=element,
        resolve_missing=resolve_missing,
    )
    return recursed_relation.get_coordinates()


def build_relation_geometry(
    element: Union[overpy.Relation, overpy.RelationRelation],
    resolve_missing: bool = False,
    repolygonize: bool = True,
    allow_dangles: bool = True,
    allow_invalids: bool = True,
) -> RelationGeometryType:
    recursed_relation = RecursedRelation(
        element=element,
        resolve_missing=resolve_missing,
    )
    return recursed_relation.get_geometry(
        repolygonize=repolygonize,
        allow_dangles=allow_dangles,
        allow_invalids=allow_invalids,
    )


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
        resolve_missing: bool = False,
        repolygonize: bool = True,
        allow_dangles: bool = True,
        allow_invalids: bool = True,
    ) -> "RelationFeature":
        geometry = build_relation_geometry(
            element=element,
            resolve_missing=resolve_missing,
            repolygonize=repolygonize,
            allow_dangles=allow_dangles,
            allow_invalids=allow_invalids,
        )
        return cls(element=element, geometry=geometry)

    @classmethod
    def split_element(
        cls,
        element: overpy.Element,
        resolve_missing: bool = False,
        repolygonize: bool = True,
        allow_dangles: bool = True,
        allow_invalids: bool = True,
    ) -> Tuple["RelationFeature", ...]:
        geometry = build_relation_geometry(
            element=element,
            resolve_missing=resolve_missing,
            repolygonize=repolygonize,
            allow_dangles=allow_dangles,
            allow_invalids=allow_invalids,
        )
        if not isinstance(geometry, GeometryCollection):
            return (cls(element=element, geometry=geometry),)
        return tuple(cls(element=element, geometry=g) for g in geometry.geoms)
