from collections import OrderedDict
from collections.abc import Mapping
from itertools import chain
from typing import Any, Dict, Iterable, Union

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
        return geo
    raise ValueError("invalid geo data type")


def _get_tooltip(geojson_data: Dict[str, Any], **kwargs) -> folium.GeoJsonTooltip:
    it = chain.from_iterable(g["properties"].keys() for g in geojson_data["features"])
    fields = tuple(OrderedDict(((f, None) for f in it)).keys())
    return folium.GeoJsonTooltip(fields=tuple(fields), **kwargs)


def get_base_map(
    tiles: Iterable[folium.TileLayer] = TILE_LAYER_COLLECTION.values(),
    **kwargs,
) -> folium.Map:
    m = folium.Map(tiles=None, **kwargs)
    for tile in tiles:
        m.add_child(tile, name=tile.tile_name)
    return m


def get_geojson_map(
    name: str,
    geo: Union[GeoInterface, Dict[str, Any]],
    *,
    tiles: Iterable[folium.TileLayer] = TILE_LAYER_COLLECTION.values(),
    map_kwargs: Dict[str, Any] = {},
    geojson_kwargs: Dict[str, Any] = {},
    tooltip_kwargs: Dict[str, Any] = {},
) -> folium.Map:
    geojson_data = _to_geojson(geo)
    tooltip = _get_tooltip(geojson_data, **tooltip_kwargs)
    geojson = folium.GeoJson(
        name=name,
        data=geojson_data,
        tooltip=tooltip,
        **geojson_kwargs,
    )
    base_map = get_base_map(tiles=tiles, **map_kwargs)
    base_map.add_child(geojson)
    base_map.fit_bounds(geojson.get_bounds())
    base_map.add_child(folium.LayerControl())
    return base_map
