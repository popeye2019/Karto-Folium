from flask import render_template, request, redirect, url_for, flash, Blueprint

# import os
# import json
from app.utils.utils_json import load_json_file as load_data
from app.utils.utils_json import save_json_file as save_data
from app.utils.utils_json import get_field_names
from app.utils.utils_json import get_next_index

# Chemin vers le fichier JSON
DATA_FILE = "./app/data/sites/recap.json"

edit_sites_bp = Blueprint(
    "edit_sites", __name__, template_folder="./templates"
)


# Route pour afficher tous les enregistrements
@edit_sites_bp.route("/")
def list_records():
    data = load_data(DATA_FILE)
    fields = get_field_names(data)
    # Construire la liste unique des types de sites (champ 'TYPE')
    unique_types = sorted(
        {
            str(record.get("TYPE", "")).strip()
            for record in data
            if record.get("TYPE")
        },
        key=lambda v: v.lower(),
    )
    return render_template(
        "liste_sites.html", fields=fields, records=data, types=unique_types
    )


# Route pour éditer un enregistrement
@edit_sites_bp.route("/edit/<int:record_index>", methods=["GET", "POST"])
def edit_record(record_index):
    data = load_data(DATA_FILE)

    # Vérifier si l'index est valide
    if record_index < 0 or record_index >= len(data):
        return redirect(url_for("list_records"))
        flash("Enregistrement introuvable.", "danger")

    if request.method == "POST":
        for field in data[record_index].keys():
            if field == "INDEX":
                continue  # verrouille l'index côté serveur
            data[record_index][field] = request.form.get(
                field, data[record_index][field]
            )
        save_data(DATA_FILE, data)
        if record_index < 0 or record_index >= len(data):
            flash("Enregistrement introuvable.", "danger")
            return redirect(url_for("edit_sites.list_records"))

    record = data[record_index]
    return render_template(
        "edit_record.html", record=record, index=record_index
    )


@edit_sites_bp.route("/ajouter", methods=["GET", "POST"])
def ajouter_site():
    data = load_data(DATA_FILE)
    fields = get_field_names(data)
    nouvel_index = get_next_index(DATA_FILE)

    if request.method == "POST":
        new_record = {}
        for field in fields:
            new_record[field] = request.form.get(field, "")

        # Générer un index automatiquement
        new_record["INDEX"] = nouvel_index

        data.append(new_record)
        save_data(DATA_FILE, data)
        flash("Nouveau site ajouté avec succès.", "success")
        return redirect(url_for("edit_sites.list_records"))

    # Pour l'affichage initial du formulaire, préremplir l'index
    record = {field: "" for field in fields}
    record["INDEX"] = nouvel_index
    return render_template("ajouter_site.html", record=record)
