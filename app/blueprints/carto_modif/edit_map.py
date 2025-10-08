"""Blueprint providing the Folium map used to pick coordinates."""

from __future__ import annotations

import folium
from flask import Blueprint, render_template, request

edit_map_bp = Blueprint("edit_map", __name__, template_folder="templates")


@edit_map_bp.route("/map")
def get_map():
    """Return an interactive map that exposes the selected coordinates."""
    latitude = request.args.get("lat", type=float, default=46.5)
    longitude = request.args.get("lon", type=float, default=2.5)

    folium_map = folium.Map(location=[latitude, longitude], zoom_start=15, control_scale=True)
    map_name = folium_map.get_name()

    overlay_html = """
    <style>
      #coord-box { position:fixed; top:10px; right:10px; background:#fff; border:1px solid #ccc;
        border-radius:8px; padding:8px 10px; box-shadow:0 2px 8px rgba(0,0,0,.1);
        font:14px system-ui,sans-serif; z-index:9999; }
      #coord-box .line { margin-bottom:6px; }
      #coord-box button { padding:6px 10px; border:1px solid #888; border-radius:6px;
        background:#f5f5f5; cursor:pointer; }
    </style>
    <div id="coord-box">
      <div class="line"><strong>Lat:</strong> <span id="lat-val"></span>
        &nbsp; <strong>Lon:</strong> <span id="lon-val"></span></div>
      <div class="line"><small>Double-clic pour deplacer le point.</small></div>
      <button type="button" onclick="sendToParent()">Valider</button>
    </div>
    """
    folium_map.get_root().html.add_child(folium.Element(overlay_html))

    script = f"""
    (function(){{
      function ready(){{
        var map = window["{map_name}"];
        if (!map) return setTimeout(ready, 0);

        map.doubleClickZoom.disable();
        var marker = L.marker([{latitude}, {longitude}]).addTo(map);

        function setCoords(lat, lon){{
          document.getElementById('lat-val').textContent = Number(lat).toFixed(6);
          document.getElementById('lon-val').textContent = Number(lon).toFixed(6);
          window._coords = {{lat: Number(lat), lon: Number(lon)}};
          marker.setLatLng([lat, lon]);
        }}

        setCoords({latitude}, {longitude});
        map.on('dblclick', function(e){{ setCoords(e.latlng.lat, e.latlng.lng); }});

        window.sendToParent = function(){{
          var coords = window._coords || {{lat:{latitude}, lon:{longitude}}};
          if (window.parent && window.parent.updateCoordinates){{
            window.parent.updateCoordinates(coords.lat.toFixed(6), coords.lon.toFixed(6));
          }} else {{
            alert('Page parente indisponible');
          }}
        }};
      }}
      ready();
    }})();
    """
    folium_map.get_root().script.add_child(folium.Element(script))

    return render_template("map_iframe.html", map_html=folium_map.get_root().render())
