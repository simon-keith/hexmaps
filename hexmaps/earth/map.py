from collections import Counter, OrderedDict
from collections.abc import Mapping
from copy import deepcopy
from itertools import chain
from typing import Any, Dict, Iterable, Optional, Tuple, Union

import folium
from hexmaps.earth.geo import GeoInterface
from shapely.geometry import mapping

TILE_LAYER_COLLECTION = OrderedDict(
    (t.tile_name, t)
    for t in (
        folium.TileLayer(
            name="CartoDB Voyager",
            tiles="https://{s}.basemaps.cartocdn.com/rastertiles/"
            "voyager/{z}/{x}/{y}{r}.png",
            attr=(
                '&copy; <a href="https://www.openstreetmap.org/copyright">'
                "OpenStreetMap</a> contributors &copy; "
                '<a href="https://carto.com/attributions">CARTO</a>'
            ),
            subdomains="abcd",
            max_zoom=20,
        ),
        folium.TileLayer(
            name="CartoDB Positron",
            tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
            attr=(
                '&copy; <a href="https://www.openstreetmap.org/copyright">'
                "OpenStreetMap</a> contributors &copy; "
                '<a href="https://carto.com/attributions">CARTO</a>'
            ),
            subdomains="abcd",
            max_zoom=20,
        ),
        folium.TileLayer(
            name="CartoDB Dark Matter",
            tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
            attr=(
                '&copy; <a href="https://www.openstreetmap.org/copyright">'
                "OpenStreetMap</a> contributors &copy; "
                '<a href="https://carto.com/attributions">CARTO</a>'
            ),
            subdomains="abcd",
            max_zoom=20,
        ),
        folium.TileLayer(
            name="ESRI World Imagery",
            tiles=(
                "https://server.arcgisonline.com/ArcGIS/rest/services/"
                "World_Imagery/MapServer/tile/{z}/{y}/{x}"
            ),
            attr=(
                "Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, "
                "GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, "
                "and the GIS User Community"
            ),
        ),
        folium.TileLayer(
            name="OpenStreetMap",
            tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            attr=(
                'Data by &copy; <a href="http://openstreetmap.org">OpenStreetMap</a>,'
                ' under <a href="http://www.openstreetmap.org/copyright">ODbL</a>.'
            ),
        ),
    )
)


def _to_geojson(geo: Union[GeoInterface, Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(geo, GeoInterface):
        return mapping(geo)
    elif isinstance(geo, Mapping) and all(isinstance(k, str) for k in geo.keys()):
        return deepcopy(geo)
    raise ValueError("invalid geo data type")


def _build_tooltip(
    geojson_data: Dict[str, Any],
    most_common: int,
    **kwargs,
) -> Optional[folium.GeoJsonTooltip]:
    if "features" not in geojson_data or len(geojson_data["features"]) == 0:
        return
    it = chain.from_iterable(f["properties"].keys() for f in geojson_data["features"])
    fields = tuple(k for k, _ in Counter(it).most_common(most_common))
    base_properties = OrderedDict([(k, None) for k in fields])
    for f in geojson_data["features"]:
        properties = base_properties.copy()
        properties.update(f["properties"])
        f["properties"] = properties
    return folium.GeoJsonTooltip(fields=fields, **kwargs)


def build_base_map(
    tiles: Iterable[folium.TileLayer] = TILE_LAYER_COLLECTION.values(),
    **kwargs,
) -> folium.Map:
    m = folium.Map(tiles=None, **kwargs)
    for tile in tiles:
        m.add_child(tile, name=tile.tile_name)
    return m


def _build_geojson_item(
    name: str,
    geo: Union[GeoInterface, Dict[str, Any]],
    geojson_kwargs: Dict[str, Any],
    tooltip_fields: int,
    tooltip_kwargs: Dict[str, Any],
) -> folium.GeoJson:
    geojson_data = _to_geojson(geo)
    tooltip = _build_tooltip(
        geojson_data=geojson_data,
        most_common=tooltip_fields,
        **tooltip_kwargs,
    )
    geojson = folium.GeoJson(
        name=name,
        data=geojson_data,
        tooltip=tooltip,
        **geojson_kwargs,
    )
    return geojson


def _get_geojson_items_bounds(
    geojson_items: Iterable[folium.GeoJson],
) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
    lat_min, lon_min, lat_max, lon_max = None, None, None, None
    for g in geojson_items:
        try:
            (new_lat_min, new_lon_min), (new_lat_max, new_lon_max) = g.get_bounds()
        except KeyError:
            pass
        else:
            if new_lat_min is not None:
                lat_min = min(lat_min or new_lat_min, new_lat_min)
                lon_min = min(lon_min or new_lon_min, new_lon_min)
                lat_max = max(lat_max or new_lat_max, new_lat_max)
                lon_max = max(lon_max or new_lon_max, new_lon_max)
    if lat_min is not None:
        return (lat_min, lon_min), (lat_max, lon_max)


def build_geojson_map(
    geo_mapping: Dict[str, Union[GeoInterface, Dict[str, Any]]],
    *,
    tiles: Iterable[folium.TileLayer] = TILE_LAYER_COLLECTION.values(),
    map_kwargs: Dict[str, Any] = {},
    geojson_kwargs: Dict[str, Any] = {},
    tooltip_fields: int = 10,
    tooltip_kwargs: Dict[str, Any] = {},
) -> folium.Map:
    geojson_list = [
        _build_geojson_item(
            name=name,
            geo=geo,
            geojson_kwargs=geojson_kwargs,
            tooltip_fields=tooltip_fields,
            tooltip_kwargs=tooltip_kwargs,
        )
        for name, geo in geo_mapping.items()
    ]
    base_map = build_base_map(tiles=tiles, **map_kwargs)
    for geojson in geojson_list:
        base_map.add_child(geojson)
    bounds = _get_geojson_items_bounds(geojson_list)
    if bounds is not None:
        base_map.fit_bounds(bounds)
    base_map.add_child(folium.LayerControl())
    return base_map
