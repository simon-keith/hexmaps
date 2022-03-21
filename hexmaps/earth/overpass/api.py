import itertools
import json
import math
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from enum import Enum
from typing import AnyStr, List, Optional, Set, Tuple

import overpy
from hexmaps.earth.overpass.node import NodeFeature
from hexmaps.earth.overpass.relation import RelationFeature
from hexmaps.earth.overpass.way import WayFeature

_DEFAULT_OVERPASS_MAXSIZE = 536870912
_DEFAULT_OVERPASS_TIMEOUT = timedelta(seconds=180)
_DEFAULT_OVERPASS_OUT = {"body", "geom"}


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


def _build_settings(
    bbox: Optional[BBox],
    timeout: timedelta,
    maxsize: int,
) -> str:
    query_parts = [
        "[out:json]",
        f"[timeout:{math.floor(timeout.total_seconds())}]",
        f"[maxsize:{maxsize}]",
    ]
    if bbox:
        query_parts.append(f"[bbox:{bbox.south},{bbox.west},{bbox.north},{bbox.east}]")
    query_parts.append(";")
    return "".join(query_parts)


def build_union_query(
    union_block: str,
    out: Optional[Set[str]] = None,
    bbox: Optional[BBox] = None,
    recurse: Recurse = Recurse.NONE,
    timeout: timedelta = _DEFAULT_OVERPASS_TIMEOUT,
    maxsize: int = _DEFAULT_OVERPASS_MAXSIZE,
) -> str:
    # check arguments
    union_block = union_block.strip()
    if not union_block.startswith("(") and not union_block.endswith(");"):
        raise ValueError("argument is not a Union block statement")
    if out is None:
        out = _DEFAULT_OVERPASS_OUT
    out_statement = f'out{" " * (len(out) > 0)}{" ".join(out)};'
    # build query
    query_parts = [
        _build_settings(
            bbox=bbox,
            timeout=timeout,
            maxsize=maxsize,
        ),
        union_block,
    ]
    if recurse != Recurse.NONE:
        query_parts.append(f"(._; {recurse.value});")
    query_parts.append(out_statement)
    query = "\n".join(query_parts)
    return query


class OverpassAPI(overpy.Overpass):
    default_url = "https://overpass.kumi.systems/api/interpreter"
    default_resolve_out = _DEFAULT_OVERPASS_OUT.copy()
    default_resolve_recurse = Recurse.DOWN
    default_resolve_timeout = timedelta(seconds=10)
    default_resolve_maxsize = _DEFAULT_OVERPASS_MAXSIZE

    def __init__(
        self,
        *args,
        resolve_out: Optional[Set[str]] = None,
        resolve_recurse: Optional[Recurse] = None,
        resolve_timeout: Optional[timedelta] = None,
        resolve_maxsize: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.resolve_out = (
            self.default_resolve_out.copy() if resolve_out is None else resolve_out
        )
        self.resolve_recurse = (
            self.default_resolve_recurse if resolve_recurse is None else resolve_recurse
        )
        self.resolve_timeout = (
            self.default_resolve_timeout if resolve_timeout is None else resolve_timeout
        )
        self.resolve_maxsize = (
            self.default_resolve_maxsize if resolve_maxsize is None else resolve_maxsize
        )

    def parse_json(self, data: AnyStr, encoding: str = "utf-8") -> "OverpassResult":
        # FIXME: this code was copy pasted from overpy
        # and may be broken in case of a dependency update
        if isinstance(data, bytes):
            data = data.decode(encoding)
        data = json.loads(data, parse_float=Decimal)
        if "remark" in data:
            self._handle_remark_msg(msg=data.get("remark"))
        return OverpassResult.from_json(data, api=self)

    def parse_xml(self, *args, **kwargs) -> "OverpassResult":
        raise NotImplementedError("XML parsing is not implemented")


class OverpassResult(overpy.Result):
    def _build_resolve_query(self, element_type: str, element_id: int) -> str:
        api: OverpassAPI = self.api
        return build_union_query(
            union_block=f"({element_type}({element_id}););",
            out=api.resolve_out,
            bbox=None,
            recurse=api.resolve_recurse,
            timeout=api.resolve_timeout,
            maxsize=api.resolve_maxsize,
        )

    def get_area(self, area_id: int, resolve_missing: bool = False):
        # FIXME: this code was copy pasted from overpy
        # and may be broken in case of a dependency update
        areas = self.get_areas(area_id=area_id)
        if len(areas) == 0:
            if resolve_missing is False:
                raise overpy.exception.DataIncomplete(
                    "Resolve missing area is disabled"
                )
            query = self._build_resolve_query("area", area_id)
            tmp_result = self.api.query(query)
            self.expand(tmp_result)
            areas = self.get_areas(area_id=area_id)
        if len(areas) == 0:
            raise overpy.exception.DataIncomplete("Unable to resolve requested areas")
        return areas[0]

    def get_node(self, node_id: int, resolve_missing: bool = False):
        # FIXME: this code was copy pasted from overpy
        # and may be broken in case of a dependency update
        nodes = self.get_nodes(node_id=node_id)
        if len(nodes) == 0:
            if not resolve_missing:
                raise overpy.exception.DataIncomplete(
                    "Resolve missing nodes is disabled"
                )
            query = self._build_resolve_query("node", node_id)
            tmp_result = self.api.query(query)
            self.expand(tmp_result)
            nodes = self.get_nodes(node_id=node_id)
        if len(nodes) == 0:
            raise overpy.exception.DataIncomplete("Unable to resolve all nodes")
        return nodes[0]

    def get_way(self, way_id: int, resolve_missing: bool = False):
        # FIXME: this code was copy pasted from overpy
        # and may be broken in case of a dependency update
        ways = self.get_ways(way_id=way_id)
        if len(ways) == 0:
            if resolve_missing is False:
                raise overpy.exception.DataIncomplete("Resolve missing way is disabled")
            query = self._build_resolve_query("way", way_id)
            tmp_result = self.api.query(query)
            self.expand(tmp_result)
            ways = self.get_ways(way_id=way_id)
        if len(ways) == 0:
            raise overpy.exception.DataIncomplete("Unable to resolve requested way")
        return ways[0]

    def get_relation(self, rel_id: int, resolve_missing: bool = False):
        # FIXME: this code was copy pasted from overpy
        # and may be broken in case of a dependency update
        relations = self.get_relations(rel_id=rel_id)
        if len(relations) == 0:
            if resolve_missing is False:
                raise overpy.exception.DataIncomplete(
                    "Resolve missing relations is disabled"
                )
            query = self._build_resolve_query("rel", rel_id)
            tmp_result = self.api.query(query)
            self.expand(tmp_result)
            relations = self.get_relations(rel_id=rel_id)
        if len(relations) == 0:
            raise overpy.exception.DataIncomplete(
                "Unable to resolve requested reference"
            )
        return relations[0]


def get_elements(
    result: overpy.Result,
) -> Tuple[List[overpy.Node], List[overpy.Way], List[overpy.Relation]]:
    return (
        result.get_nodes(),
        result.get_ways(),
        result.get_relations(),
    )


def get_features(
    elements: Tuple[List[overpy.Node], List[overpy.Way], List[overpy.Relation]],
    resolve_missing: bool = False,
    split_relations: bool = False,
) -> Tuple[List[NodeFeature], List[WayFeature], List[RelationFeature]]:
    nodes, ways, relations = elements
    node_features = [
        NodeFeature.from_element(
            element=n,
            resolve_missing=resolve_missing,
        )
        for n in nodes
    ]
    way_features = [
        WayFeature.from_element(
            element=w,
            resolve_missing=resolve_missing,
        )
        for w in ways
    ]
    if split_relations:
        relation_features = list(
            itertools.chain.from_iterable(
                RelationFeature.split_element(
                    element=r,
                    resolve_missing=resolve_missing,
                )
                for r in relations
            )
        )
    else:
        relation_features = [
            RelationFeature.from_element(element=r, resolve_missing=resolve_missing)
            for r in relations
        ]
    return node_features, way_features, relation_features
