"""Module utilitaire pour la gestion d'uploads de fichiers (images, PDF, etc.)."""

from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Dict

# Extensions acceptées par défaut
DEFAULT_ALLOWED_EXTENSIONS: Dict[str, set[str]] = {
    "image": {".png", ".jpg", ".jpeg", ".gif"},
    "pdf": {".pdf"},
}

# Extensions interdites quel que soit le contexte (fichiers exécutables, scripts, etc.)
BANNED_EXTENSIONS = {
    ".py",
    ".pyc",
    ".pyo",
    ".exe",
    ".dll",
    ".bat",
    ".cmd",
    ".sh",
    ".msi",
    ".jar",
}

@dataclass(frozen=True)
class UploadPolicy:
    """Décrit les contraintes applicables à une catégorie d'upload."""

    allowed_extensions: set[str]
    max_size_bytes: int
    mime_prefixes: tuple[str, ...] = ()

    def is_extension_allowed(self, extension: str) -> bool:
        return extension.lower() in self.allowed_extensions

    def is_mime_allowed(self, mime_type: str | None) -> bool:
        if not self.mime_prefixes:
            return True
        if not mime_type:
            return False
        return any(mime_type.startswith(prefix) for prefix in self.mime_prefixes)


IMAGE_UPLOAD_POLICY = UploadPolicy(
    allowed_extensions=DEFAULT_ALLOWED_EXTENSIONS["image"],
    max_size_bytes=5 * 1024 * 1024,  # 5 Mo
    mime_prefixes=("image/",),
)

PDF_UPLOAD_POLICY = UploadPolicy(
    allowed_extensions=DEFAULT_ALLOWED_EXTENSIONS["pdf"],
    max_size_bytes=10 * 1024 * 1024,  # 10 Mo
    mime_prefixes=("application/pdf",),
)

UPLOAD_POLICIES: Dict[str, UploadPolicy] = {
    "image": IMAGE_UPLOAD_POLICY,
    "pdf": PDF_UPLOAD_POLICY,
}

class UploadError(RuntimeError):
    """Exception levée lorsque l'upload ne respecte pas la politique définie."""


def ensure_directory(target_dir: Path | str) -> Path:
    """Garantit l'existence du dossier cible."""
    directory = Path(target_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def secure_basename(filename: str) -> str:
    """Retourne un nom de fichier sécurisé (suppression du chemin et caractères dangereux)."""
    name = os.path.basename(filename or "")
    name = name.strip().replace("\x00", "")
    return name


def validate_extension(filename: str, policy: UploadPolicy) -> None:
    extension = Path(filename).suffix.lower()
    if extension in BANNED_EXTENSIONS:
        raise UploadError(f"Extension interdite: {extension}")
    if not policy.is_extension_allowed(extension):
        allowed = ", ".join(sorted(policy.allowed_extensions))
        raise UploadError(
            f"Extension '{extension}' non autorisée. Extensions permises: {allowed}"
        )


def validate_size(file_storage, policy: UploadPolicy) -> None:
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > policy.max_size_bytes:
        raise UploadError(
            "Fichier trop volumineux. "
            f"Taille maximale: {policy.max_size_bytes // 1024 // 1024} Mo"
        )


def validate_mime(file_storage, policy: UploadPolicy) -> None:
    mime_type = file_storage.mimetype
    if not policy.is_mime_allowed(mime_type):
        raise UploadError(f"Type MIME non autorisé: {mime_type}")


def save_upload(file_storage, *, category: str, target_dir: Path | str) -> Path:
    """Valide et enregistre un fichier uploadé selon la catégorie souhaitée."""
    if category not in UPLOAD_POLICIES:
        raise UploadError(f"Catégorie inconnue: {category}")

    policy = UPLOAD_POLICIES[category]
    filename = secure_basename(file_storage.filename)
    if not filename:
        raise UploadError("Nom de fichier invalide")

    validate_extension(filename, policy)
    validate_size(file_storage, policy)
    validate_mime(file_storage, policy)

    directory = ensure_directory(target_dir)
    destination = directory / filename

    # Éviter d'écraser un fichier existant en suffixant si nécessaire.
    counter = 1
    stem = Path(filename).stem
    extension = Path(filename).suffix
    while destination.exists():
        destination = directory / f"{stem}_{counter}{extension}"
        counter += 1

    file_storage.stream.seek(0)
    destination.write_bytes(file_storage.stream.read())
    return destination


def register_policy(name: str, policy: UploadPolicy) -> None:
    """Enregistre dynamiquement une politique d'upload supplémentaire."""
    if name in UPLOAD_POLICIES:
        raise UploadError(f"Une politique existe déjà pour '{name}'")
    UPLOAD_POLICIES[name] = policy


# Idées complémentaires :
# - Connecter ce module à une base de données pour journaliser les uploads.
# - Générer un nom unique et stocker un hash du fichier pour détecter les doublons.
# - Intégrer une analyse antivirus ou un service de sandbox pour les PDF.
# - Limiter le nombre d'uploads par utilisateur/heure pour éviter les abus.
# - Ajouter une fonction de redimensionnement automatique des images avant stockage.
