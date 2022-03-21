from typing import List, Tuple

import overpy
from hexmaps.earth.overpass.api import OverpassAPI, get_elements, get_features
from pytest import fixture, mark

ElementsType = Tuple[List[overpy.Node], List[overpy.Way], List[overpy.Element]]


def _test_elements(
    elements: ElementsType,
    node_count: int,
    way_count: int,
    relation_count: int,
    split_relations: bool = False,
):
    nodes, ways, relations = elements
    assert len(nodes) == node_count
    assert len(ways) == way_count
    assert len(relations) == relation_count
    nodes_ft, ways_ft, relations_ft = get_features(
        elements=elements,
        resolve_missing=True,
        split_relations=split_relations,
    )
    assert len(nodes_ft) == node_count
    assert len(ways_ft) == way_count
    if split_relations:
        assert relation_count <= len(relations_ft) <= relation_count * 3
    else:
        assert len(relations_ft) == relation_count


_MULTIPOLYGON_QUERY = """[out:json];
(
  rel(2327759);
);
out geom;"""


@fixture(scope="module")
def multipolygon_elements(overpass: OverpassAPI) -> ElementsType:
    return get_elements(overpass.query(_MULTIPOLYGON_QUERY))


@mark.timeout(5)
def test_multipolygon(multipolygon_elements: ElementsType):
    _test_elements(multipolygon_elements, 0, 0, 1)


_PUBLIC_TRANSPORT_QUERY = """[out:json];
(
  rel(7938390);
);
out geom;
"""


@fixture(scope="module")
def public_transport_elements(overpass: OverpassAPI) -> ElementsType:
    return get_elements(overpass.query(_PUBLIC_TRANSPORT_QUERY))


@mark.timeout(15)
def test_public_transport(public_transport_elements: ElementsType):
    _test_elements(public_transport_elements, 0, 0, 1)


@mark.timeout(15)
def test_public_transport_split(public_transport_elements: ElementsType):
    _test_elements(public_transport_elements, 0, 0, 1, split_relations=True)
