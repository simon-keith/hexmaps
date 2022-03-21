from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from itertools import chain, islice
from typing import Any, Callable, Dict, Iterable, Optional, Tuple, Type, Union

import folium
from hexmaps.earth.spatial.geojson import GeoOrGeoSequence, get_feature_collection

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


def build_base_map(
    tiles: Iterable[folium.TileLayer] = TILE_LAYER_COLLECTION.values(),
    **kwargs,
) -> folium.Map:
    m = folium.Map(tiles=None, **kwargs)
    for tile in tiles:
        m.add_child(tile, name=tile.tile_name)
    return m


def _get_geojson_property_counter(data: Dict[str, Any]) -> Counter:
    try:
        it = chain.from_iterable(f["properties"].keys() for f in data["features"])
        return Counter(it)
    except KeyError as e:
        raise ValueError("invalid GeoJSON collection data") from e


def _trim_properties(
    data: Dict[str, Any],
    field_names: Optional[Tuple[str]],
    field_count: Optional[int],
) -> Tuple[str, ...]:
    fields = OrderedDict()
    if field_names is not None:
        fields.update([(f, None) for f in field_names])
    if field_count is not None:
        field_counter = _get_geojson_property_counter(data)
        fields.update(
            islice(
                ((k, None) for k, _ in field_counter.most_common() if k not in fields),
                max(field_count - len(fields), 0),
            )
        )
    for f in data["features"]:
        f["properties"] = OrderedDict([(k, f["properties"].get(k)) for k in fields])
    return tuple(fields)


def _build_geojson_details(
    cls: Union[Type[folium.Tooltip], Type[folium.GeoJsonPopup]],
    data: Dict[str, Any],
    field_names: Tuple[str, ...],
    **kwargs,
) -> Optional[Union[folium.GeoJsonTooltip, folium.GeoJsonPopup]]:
    if len(data["features"]) == 0:
        return
    return cls(fields=field_names, **kwargs)


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


@dataclass
class DetailOptions:
    field_names: Optional[Tuple[str]] = None
    field_count: Optional[int] = 10
    labels: Optional[bool] = None
    localize: Optional[bool] = None
    details_kwargs: Dict[str, Any] = field(default_factory=dict)
    tooltip_kwargs: Dict[str, Any] = field(default_factory=dict)
    popup_kwargs: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.field_names is None and self.field_count is None:
            raise ValueError("must set 'field_names' or 'field_count'")

    def _get_details_kwargs(self) -> Dict[str, Any]:
        kwargs = {}
        if self.labels is not None:
            kwargs["labels"] = self.labels
        if self.localize is not None:
            kwargs["localize"] = self.localize
        return {**kwargs, **self.details_kwargs}

    def get_tooltip_kwargs(self) -> Dict[str, Any]:
        return {**self._get_details_kwargs(), **self.tooltip_kwargs}

    def get_popup_kwargs(self) -> Dict[str, Any]:
        return {**self._get_details_kwargs(), **self.popup_kwargs}


@dataclass
class GeoJsonOptions:
    name: Optional[str] = None
    show: Optional[bool] = None
    zoom_on_click: Optional[bool] = None
    style_function: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    tooltip: bool = True
    popup: bool = False
    kwargs: Dict[str, Any] = field(default_factory=dict)

    def get_kwargs(
        self,
    ) -> Dict[str, Any]:
        kwargs = {}
        if self.name is not None:
            kwargs["name"] = self.name
        if self.show is not None:
            kwargs["show"] = self.show
        if self.zoom_on_click is not None:
            kwargs["zoom_on_click"] = self.zoom_on_click
        if self.style_function is not None:
            kwargs["style_function"] = self.style_function
        return {**kwargs, **self.kwargs}


@dataclass
class GeoJsonArguments:
    geo: GeoOrGeoSequence
    geojson_options: GeoJsonOptions = field(default_factory=GeoJsonOptions)
    detail_options: DetailOptions = field(default_factory=DetailOptions)


def build_geojson_item(args: GeoJsonArguments) -> folium.GeoJson:
    data = get_feature_collection(args.geo)
    field_names = _trim_properties(
        data=data,
        field_names=args.detail_options.field_names,
        field_count=args.detail_options.field_count,
    )
    tooltip_obj = (
        _build_geojson_details(
            cls=folium.GeoJsonTooltip,
            data=data,
            field_names=field_names,
            **args.detail_options.get_tooltip_kwargs(),
        )
        if args.geojson_options.tooltip
        else None
    )
    popup_obj = (
        _build_geojson_details(
            cls=folium.GeoJsonPopup,
            data=data,
            field_names=field_names,
            **args.detail_options.get_popup_kwargs(),
        )
        if args.geojson_options.popup
        else None
    )
    geojson = folium.GeoJson(
        data=data,
        tooltip=tooltip_obj,
        popup=popup_obj,
        **args.geojson_options.get_kwargs(),
    )
    return geojson


def build_geojson_map(
    args: Tuple[Union[GeoJsonArguments, GeoOrGeoSequence]],
    base_map: Optional[folium.Map] = None,
) -> folium.Map:
    base_map = base_map or build_base_map()
    geojson_list = [
        build_geojson_item(
            a if isinstance(a, GeoJsonArguments) else GeoJsonArguments(geo=a)
        )
        for a in args
    ]
    for geojson in geojson_list:
        base_map.add_child(geojson)
    bounds = _get_geojson_items_bounds(geojson_list)
    if bounds is not None:
        base_map.fit_bounds(bounds)
    base_map.add_child(folium.LayerControl())
    return base_map
