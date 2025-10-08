from flask import render_template, request, redirect, url_for, flash,Blueprint
#import os
#import json
from app.utils.utils_json import load_json_file as load_data
from app.utils.utils_json import save_json_file as save_data
from app.utils.utils_json import get_field_names

# Chemin vers le fichier JSON
DATA_FILE = './app/data/sites/recap.json'

edit_carte_dynamique_test_bp = Blueprint('edit_carte_dynamique_test', __name__,template_folder='./templates')

#####tout reecrire
# Route pour afficher tous les enregistrements
@edit_carte_dynamique_test_bp.route('/')
def affiche():
    #data = load_data(DATA_FILE)
    #fields = get_field_names(data)
    return render_template('edit_carte_dynamique_test.html')

