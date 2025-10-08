from flask import Blueprint, render_template, request, redirect, url_for, send_file
import folium
import os

# Créer un blueprint pour les routes liées à l'édition de la carte
edit_map_bp = Blueprint('edit_map', __name__,template_folder='./templates')

# Chemin pour stocker le fichier HTML de la carte
CARTE_HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..', 'static', 'edit_carte_dynamique.html')

# Template principal contenant une iframe pour afficher la carte
main_page_template = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Éditeur de Carte Dynamique</title>
</head>
<body>
    <h1>Carte Interactive avec Position de Clic</h1>
    <form method="POST" action="{{ url_for('edit_map.update_marker') }}">
        <label for="latitude">Latitude:</label>
        <input type="text" id="latitude" name="latitude" placeholder="48.8566" required>
        <label for="longitude">Longitude:</label>
        <input type="text" id="longitude" name="longitude" placeholder="2.3522" required>
        <button type="submit">Mettre à jour le marqueur</button>
    </form>
    <h2>Carte:</h2>
    <iframe src="{{ url_for('edit_map.get_map') }}" width="100%" height="500" id="map_iframe"></iframe>

    <script>
        // Fonction pour recevoir les coordonnées cliquées depuis la carte
        function updateCoordinates(lat, lon) {
            document.getElementById('latitude').value = lat;  // Met à jour la latitude
            document.getElementById('longitude').value = lon;  // Met à jour la longitude
        }
    </script>
</body>
</html>
"""

# Fonction pour générer la carte avec un marqueur et gestionnaire de clic
def generate_map(lat, lon):
    # Créer la carte avec doubleClickZoom désactivé
    map_instance = folium.Map(location=[lat, lon], zoom_start=12, doubleClickZoom=False)

    # Ajouter un marqueur
    folium.Marker(
        location=[lat, lon],
        popup=f"Marqueur: ({lat}, {lon})",
        icon=folium.Icon(icon="info-sign", color="blue")
    ).add_to(map_instance)

    # Ajouter un gestionnaire de clic avec communication parent
    script = """
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            // Trouver l'objet de la carte Folium par son identifiant dynamique
            var mapId = Object.keys(window).find(key => key.startsWith('map_') && window[key]._container);
            var map = window[mapId];

            // Ajouter un gestionnaire de clic
            if (map) {
                map.on('click', function(e) {
                    // Récupérer les coordonnées
                    var lat = e.latlng.lat;
                    var lon = e.latlng.lng;

                    // Appeler la fonction dans la fenêtre principale
                    window.parent.updateCoordinates(lat, lon);
                });
            } else {
                console.error("Carte non trouvée !");
            }
        });
    </script>
    """
    map_instance.get_root().html.add_child(folium.Element(script))

    # Enregistrer la carte dans un fichier HTML
    map_instance.save(CARTE_HTML_PATH)

# Route principale pour afficher la page avec le formulaire et la carte
@edit_map_bp.route("/")
def index():
    return render_template("edit_map.html")

# Route pour récupérer la carte HTML
@edit_map_bp.route("/map")
def get_map():
    return send_file(CARTE_HTML_PATH)

# Route pour mettre à jour le marqueur
@edit_map_bp.route("/update_marker", methods=["POST"])
def update_marker():
    # Obtenir les nouvelles coordonnées du formulaire
    latitude = float(request.form["latitude"])
    longitude = float(request.form["longitude"])
    # Régénérer la carte avec les nouvelles coordonnées
    generate_map(latitude, longitude)
    return redirect(url_for("edit_map.index"))

# Générer une carte initiale
generate_map(48.8566, 2.3522)  # Paris, France
