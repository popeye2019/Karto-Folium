from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Tuple, Optional

import folium
from folium import FeatureGroup, LayerControl, Marker
from folium.plugins import MarkerCluster

from app.utils.utils_geocarto import (
    TypeMetadata,
    load_geo_datasets,
    load_type_metadata,
    normalize_label,
)

try:
    from pyproj import Transformer  # type: ignore
except ImportError:  # pragma: no cover - optional
    Transformer = None  # type: ignore

TRANSFORMER = None
if Transformer is not None:  # pragma: no cover - best effort
    try:
        TRANSFORMER = Transformer.from_crs("EPSG:3945", "EPSG:4326", always_xy=True)
    except Exception:  # pragma: no cover
        TRANSFORMER = None


# Point vers le dossier app/ (et non app/utils) pour trouver app/data et app/data/icones
BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ICON_NAME = "compteur.png"
BASE_ICON_SIZE: Tuple[int, int] = (50, 50)
ICON_CACHE: dict[str, str] = {}
URL_OUVRAGE = "https://karto.mine.nu/static/ouvrages/"


def parse_float(value, default=None):
    if value is None:
        return default
    if isinstance(value, str):
        value = value.strip().replace(",", ".")
        if value == "":
            return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_int(value, default=None):
    parsed = parse_float(value, None)
    if parsed is None:
        return default
    try:
        return int(parsed)
    except (TypeError, ValueError):
        return default


def resolve_icon(name: str) -> str:
    icon_path = BASE_DIR / "data/icones" / name
    if not icon_path.is_file():
        raise FileNotFoundError(f"Icône introuvable : {icon_path}")
    return str(icon_path)


def get_icon_path(icon_name: str) -> str:
    if not icon_name:
        icon_name = DEFAULT_ICON_NAME
    cached = ICON_CACHE.get(icon_name)
    if cached:
        return cached
    try:
        resolved = resolve_icon(icon_name)
    except FileNotFoundError:
        if icon_name != DEFAULT_ICON_NAME:
            resolved = resolve_icon(DEFAULT_ICON_NAME)
        else:
            raise
    ICON_CACHE[icon_name] = resolved
    return resolved


def compute_icon_size(meta: TypeMetadata | None) -> tuple[int, int]:
    scale = meta.scale if meta else 1.0
    width = max(12, int(BASE_ICON_SIZE[0] * scale))
    height = max(12, int(BASE_ICON_SIZE[1] * scale))
    return (width, height)


@dataclass
class LayerEntry:
    meta: TypeMetadata
    group: FeatureGroup
    target: object


def build_layer_registry(
    carte: folium.Map, metadata_map: dict[str, TypeMetadata]
) -> tuple[dict[str, LayerEntry], LayerEntry]:
    registry: dict[str, LayerEntry] = {}
    for _, meta in metadata_map.items():
        if not meta.enabled:
            continue
        feature_group = FeatureGroup(name=meta.group, show=meta.show)
        feature_group.add_to(carte)
        target_layer: object = feature_group
        if meta.cluster:
            cluster_layer = MarkerCluster(name=meta.group)
            cluster_layer.add_to(feature_group)
            target_layer = cluster_layer
        registry[meta.key] = LayerEntry(meta=meta, group=feature_group, target=target_layer)

    default_meta = TypeMetadata(
        type_name="Autres ouvrages",
        icon=DEFAULT_ICON_NAME,
        group="Autres ouvrages",
        enabled=True,
        cluster=False,
        scale=1.0,
        show=False,
    )
    default_group = FeatureGroup(name=default_meta.group, show=False)
    default_group.add_to(carte)
    default_entry = LayerEntry(meta=default_meta, group=default_group, target=default_group)
    registry["__default__"] = default_entry
    return registry, default_entry


def resolve_layer_entry(
    type_name: str,
    registry: dict[str, LayerEntry],
    default_entry: LayerEntry,
) -> LayerEntry:
    key = normalize_label(type_name)
    return registry.get(key) or default_entry


def calcul_centre_commune(coordonnes):
    lat = 0.0
    lon = 0.0
    nb = len(coordonnes)
    for elem in coordonnes:
        lat += elem[1]
        lon += elem[0]
    return [lat / nb, lon / nb]


def generate_map(
    output_path: Path | str,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    zoom: Optional[int] = None,
    select_layer: Optional[str] = None,
    exclusive: bool = False,
) -> Path:
    """Génère la carte statique des ouvrages et l'enregistre dans output_path.

    Paramètres:
      - output_path: chemin du fichier HTML de sortie (str ou Path).
    Retour:
      - Path absolu du fichier généré.
    """
    # Centre par défaut
    lat0 = float(lat) if lat is not None else 45.148537
    lon0 = float(lon) if lon is not None else 1.463
    zoom0 = int(zoom) if zoom is not None else 10
    carte = folium.Map(location=[lat0, lon0], zoom_start=zoom0)

    # Chargement données
    (
        geo,
        liste_ouvrages,
        liste_commune_asst_collectif,
        liste_communes_agglo,
        communes_exclues,
    ) = load_geo_datasets(BASE_DIR)

    # Couches + métadonnées
    type_metadata = load_type_metadata(BASE_DIR)
    layer_registry, default_layer_entry = build_layer_registry(carte, type_metadata)

    commune_entry = layer_registry.get(normalize_label("COMMUNE"))
    if commune_entry is None:
        commune_meta = None
        commune_target = default_layer_entry.target
    else:
        commune_meta = commune_entry.meta
        commune_target = commune_entry.target

    # Fond de carte
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri",
        name="Esri Satellite",
        overlay=False,
        control=True,
    ).add_to(carte)
    style1 = {"fillColor": "#228B22", "color": "#228B22"}
    folium.GeoJson(geo, name="SEABB", style_function=lambda x: style1).add_to(carte)

    # Ajout mairies
    commune_icon_name = commune_meta.icon if commune_meta else DEFAULT_ICON_NAME
    icon_mairie_path = get_icon_path(commune_icon_name)
    icon_mairie_size = compute_icon_size(commune_meta)
    for elem in geo.get("features", []):
        commune_nom = elem.get("properties", {}).get("nom", "")
        temp1 = None
        temp2 = None
        if commune_nom in liste_communes_agglo:
            matching = next((item for item in liste_commune_asst_collectif if item.get("COMMUNE") == commune_nom), None)
            if matching:
                t1 = parse_float(matching.get("LAT_MAIRIE"))
                t2 = parse_float(matching.get("LONG_MAIRIE"))
                if t1 is not None and t2 is not None:
                    temp1, temp2 = t1, t2
        if temp1 is None or temp2 is None:
            try:
                coordonnes_commune = elem.get("geometry", {}).get("coordinates", [])[0]
                temp1, temp2 = calcul_centre_commune(coordonnes_commune)
            except Exception:
                temp1, temp2 = 45.0, 1.0

        iframe_mairie = folium.IFrame(
            html=(
                "<h2>Mairie de "
                + commune_nom
                + "</h2><br><p><code><a href=\"https://www.google.com/maps/dir//"
                + f"{temp1},{temp2}/@{temp1},{temp2},17z"
                + "\" target=\"_blank\">Lien</a></code></p>"
            ),
            width=400,
            height=200,
        )
        icone_mairie = folium.features.CustomIcon(icon_image=icon_mairie_path, icon_size=icon_mairie_size)
        Marker((temp1, temp2), popup=folium.Popup(iframe_mairie), icon=icone_mairie).add_to(commune_target)

    # Ajout ouvrages
    disabled_types = {key for key, meta in type_metadata.items() if not meta.enabled}
    logged_disabled: set[str] = set()
    logged_unknown: set[str] = set()
    for elem in liste_ouvrages:
        # Filtre: masquer les sites hors service
        etat = str(elem.get("ETAT", "")).strip().upper()
        if etat in {"HS", "H.S", "HORS SERVICE", "HORS-SERVICE"}:
            continue
        ouvrage_nom = elem.get("NOM", "")
        ouvrage_commune = elem.get("COMMUNE", "")
        lat_raw = elem.get("LAT")
        lon_raw = elem.get("LONG")
        try:
            temp1 = parse_float(lat_raw)
            temp2 = parse_float(lon_raw)
            if temp1 is None or temp2 is None or temp1 > 100.0:
                raise ValueError("Latitude invalide")
        except Exception:
            if TRANSFORMER is not None:
                lon_value = parse_float(lon_raw)
                lat_value = parse_float(lat_raw)
                if lon_value is not None and lat_value is not None:
                    try:
                        temp2, temp1 = TRANSFORMER.transform(lon_value, lat_value)
                    except Exception:
                        temp1, temp2 = 45.0, 1.0
                else:
                    temp1, temp2 = 45.0, 1.0
            else:
                temp1, temp2 = 45.0, 1.0

        ouvrage_coord = (temp1, temp2)
        ouvrage_type = elem.get("TYPE", "")
        normalized_type = normalize_label(ouvrage_type)
        if normalized_type in disabled_types:
            if normalized_type not in logged_disabled:
                print(f"Type désactivé ignoré: {ouvrage_type}")
                logged_disabled.add(normalized_type)
            continue
        entry = resolve_layer_entry(ouvrage_type, layer_registry, default_layer_entry)
        meta = entry.meta
        target_layer = entry.target
        if entry is default_layer_entry and normalized_type not in disabled_types:
            if normalized_type not in logged_unknown:
                print("Type non configuré dans type_site.json, utilisation du groupe par défaut:", ouvrage_type)
                logged_unknown.add(normalized_type)

        ouvrage_documentation = elem.get("DOCUMENTATION", "")
        balise_html = "<br></code></p> "
        if ouvrage_documentation:
            documentation_url = URL_OUVRAGE + str(ouvrage_documentation)
            balise_html = f"<br><a href=\" {documentation_url} \" target=\"_blank\">documentation </a><br></code></p> "

        generate_coordinate = f"{temp1},{temp2}/@{temp1},{temp2},17z"
        html_ouvrage = (
            "<h3> Ouvrage: "
            + ouvrage_nom
            + " / "
            + ouvrage_commune
            + " "
            + ouvrage_type
            + "</h3><br><p><code><a href=\"https://www.google.com/maps/dir//"
            + generate_coordinate
            + "\" target=\"_blank\">Vers...</a><br> "
            + balise_html
        )
        iframe_ouvrage = folium.IFrame(html=html_ouvrage, width=300, height=200)
        icon_path = get_icon_path(meta.icon if meta else DEFAULT_ICON_NAME)
        icon_size = compute_icon_size(meta)
        icone_ouvrage = folium.features.CustomIcon(icon_image=icon_path, icon_size=icon_size)
        Marker(location=ouvrage_coord, popup=folium.Popup(iframe_ouvrage), icon=icone_ouvrage).add_to(target_layer)

    LayerControl().add_to(carte)

    # Inject helper script to support URL parameters: lat, lon, zoom, layer
    # and to expose overlay groups and type->group mapping to the page.
    try:
        map_var = carte.get_name()
        # Build mapping of overlay display name -> JS variable name of the FeatureGroup
        overlay_lines: list[str] = []
        for _, entry in layer_registry.items():
            group_label = entry.meta.group
            group_js_var = entry.group.get_name()
            overlay_lines.append(f'__overlays["{group_label}"] = {group_js_var};')

        # Map normalized type -> display group label (so we can receive ?layer=<TYPE>)
        type_to_group = {k: m.group for k, m in load_type_metadata(BASE_DIR).items()}
        type_to_group_json = json.dumps(type_to_group)

        # Provide initial config fallback when no URL params are supplied
        initial_config = {
            "lat": lat0,
            "lon": lon0,
            "zoom": zoom0,
            "layer": select_layer or "",
            "exclusive": bool(exclusive),
        }
        initial_config_json = json.dumps(initial_config)

        script = (
            "(function(){\n"
            "  function ready(){\n"
            f"    var map = window[\"{map_var}\"];\n"
            "    if (!map) return setTimeout(ready, 0);\n\n"
            "    window.__leaflet_map = map;\n"
            "    var __overlays = window.__layer_overlays = {};\n"
            + "    " + "\n    ".join(overlay_lines) + "\n"
            + f"    window.__type_to_group = {type_to_group_json};\n"
            + f"    var __initial_cfg = {initial_config_json};\n\n"
            "    function applyFromParams(){\n"
            "      try {\n"
            "        var params = new URLSearchParams(window.location.search || \"\");\n"
            "        var plat = parseFloat(params.get('lat'));\n"
            "        var plon = parseFloat(params.get('lon'));\n"
            "        var pzoom = parseInt(params.get('zoom') || '0', 10);\n"
            "        var player = params.get('layer');\n" +
"        var exclusive = params.get('exclusive');\n"
            "        if ((player == null || player === '') && __initial_cfg.layer) { player = __initial_cfg.layer; }\n"
            "        if (isNaN(plat) || isNaN(plon)) { plat = __initial_cfg.lat; plon = __initial_cfg.lon; }\n"
            "        if (isNaN(pzoom) || pzoom <= 0) { pzoom = __initial_cfg.zoom; }\n\n"
            "        if (!isNaN(plat) && !isNaN(plon)) {\n"
            "          if (!isNaN(pzoom) && pzoom > 0) {\n"
            "            map.setView([plat, plon], pzoom);\n"
            "          } else {\n"
            "            map.setView([plat, plon]);\n"
            "          }\n"
            "        }\n\n"
            "        var wantExclusive = (exclusive === '1' || exclusive === 'true' || __initial_cfg.exclusive === true);\n"
            "        if (player) {\n"
            "          var norm = (player || '').toString().normalize('NFD')\n"
            "            .replace(/[\\u0300-\\u036f]/g, '')\n"
            "            .replace(/[\\'\\\/-]/g, ' ')\n"
            "            .replace(/\\s+/g, ' ')\n"
            "            .trim()\n"
            "            .toLowerCase();\n"
            "          var groupLabel = (window.__type_to_group && window.__type_to_group[norm]) || null;\n"
            "          var targetLayer = null;\n"
            "          if (groupLabel && __overlays[groupLabel]) {\n"
            "            targetLayer = __overlays[groupLabel];\n"
            "          } else {\n"
            "            for (var k in __overlays) {\n"
            "              if (k.toLowerCase() === (player||'').toLowerCase()) {\n"
            "                targetLayer = __overlays[k];\n"
            "                break;\n"
            "              }\n"
            "            }\n"
            "          }\n"
            "          if (targetLayer) {\n"
            "            if (wantExclusive) {\n"
            "              for (var k in __overlays) {\n"
            "                if (__overlays[k] && map.hasLayer(__overlays[k]) && __overlays[k] !== targetLayer) {\n"
            "                  map.removeLayer(__overlays[k]);\n"
            "                }\n"
            "              }\n"
            "            }\n"
            "            if (!map.hasLayer(targetLayer)) { map.addLayer(targetLayer); }\n"
            "          }\n"
            "        }\n"
            "      } catch(e) { }\n"
            "    }\n\n"
            "    if (document.readyState === 'loading') {\n"
            "      document.addEventListener('DOMContentLoaded', applyFromParams);\n"
            "    } else {\n"
            "      applyFromParams();\n"
            "    }\n"
            "  }\n"
            "  ready();\n"
            "})();\n"
        )
        carte.get_root().script.add_child(folium.Element(script))
    except Exception:
        # Non-fatal if the enhancement script fails to inject
        pass
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    carte.save(str(out_path))
    return out_path.resolve()
