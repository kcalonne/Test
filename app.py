# -*- coding: utf-8 -*-
"""Application Streamlit : Texte vers MP3 avec lots et accents anglais."""

import csv
import io
import re
import zipfile
from typing import List, Tuple

import streamlit as st
from gtts import gTTS

st.set_page_config(
    page_title="Texte vers MP3",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

LANGUAGES = {
    "Franç·ªais": "fr",
    "English (US)": "en",
    "English (UK)": "en-uk",
    "English (Irish)": "en-ie",
    "English (Canadian)": "en-ca",
    "English (Australian)": "en-au",
    "English (South African)": "en-za",
    "Españ·ª·∞ol": "es",
}

# gTTS propose deux vitesses natives
SPEEDS = {
    "Normale (1.0x)": False,  # slow=False
    "Lente (0.7x)": True,     # slow=True
}

INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_filename(name: str, fallback: str) -> str:
    """Produit un nom compatible avec les fichiers Windows et les archives ZIP."""
    cleaned = INVALID_FILENAME.sub("_", name.strip()).rstrip(". ")
    return (cleaned[:100] or fallback).replace(" ", "_")


def parse_batch_entries(content: str) -> Tuple[List[Tuple[str, str]], List[str]]:
    """Lit les lignes `nom | texte` d'un lot."""
    entries: List[Tuple[str, str]] = []
    errors: List[str] = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        if "|" not in line:
            errors.append(f"Ligne {line_number} : le séparateur `|` est manquant.")
            continue
        name, text = (part.strip() for part in line.split("|", 1))
        if not text:
            errors.append(f"Ligne {line_number} : le texte est vide.")
            continue
        entries.append((safe_filename(name, f"fichier_{line_number}"), text))
    return entries, errors


def parse_csv(uploaded_file) -> List[Tuple[str, str]]:
    """Lit un CSV à deux colonnes : nom,texte (virgule, point-virgule ou tabulation)."""
    raw = uploaded_file.getvalue().decode("utf-8-sig")
    sample = raw[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
    except csv.Error:
        dialect = csv.excel

    reader = csv.reader(io.StringIO(raw), dialect)
    rows = list(reader)
    if rows and len(rows[0]) >= 2:
        header = [cell.strip().lower() for cell in rows[0][:2]]
        if header in (["nom", "texte"], ["name", "text"]):
            rows = rows[1:]

    entries: List[Tuple[str, str]] = []
    for position, row in enumerate(rows, start=1):
        if len(row) < 2:
            continue
        name, text = row[0].strip(), row[1].strip()
        if text:
            entries.append((safe_filename(name, f"fichier_{position}"), text))
    return entries


def create_mp3(text: str, language_code: str, slow: bool) -> bytes:
    """Gé·ªnè·ªre un MP3 avec gTTS."""
    buffer = io.BytesIO()
    gTTS(text=text, lang=language_code, slow=slow).write_to_fp(buffer)
    return buffer.getvalue()


def create_zip(files: List[Tuple[str, bytes]]) -> bytes:
    """Construit une archive ZIP en mémoire."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, mp3 in files:
            archive.writestr(f"{filename}.mp3", mp3)
    return output.getvalue()


def configure_state() -> None:
    """Initialise les zones de saisie persistantes de Streamlit."""
    st.session_state.setdefault("single_text", "")
    st.session_state.setdefault(
        "batch_text",
        "fichier_1 | Bonjour, ceci est le premier texte.\n"
        "fichier_2 | This is the second text in English.\n"
        "fichier_3 | Este es el tercer texto en español.",
    )


def settings_sidebar() -> Tuple[str, bool]:
    with st.sidebar:
        st.header("⚙️ Paramè·ªtres audio")
        selected_name = st.selectbox("Langue / accent", list(LANGUAGES), index=0)
        speed_name = st.selectbox("Vitesse d'enregistrement", list(SPEEDS), index=0)
        st.markdown("---")
        st.caption("Les accents proposés s'appliquent aux textes anglais.")
        st.caption("La vitesse lente est idéale pour l'apprentissage des langues.")
        st.markdown("### Accents anglais")
        st.markdown("US · UK · Irish · Canadian · Australian · South African")
    return LANGUAGES[selected_name], SPEEDS[speed_name]


def show_single_tab(language_code: str, slow: bool) -> None:
    st.subheader("Conversion d'un texte")
    st.text_area(
        "Votre texte",
        key="single_text",
        height=255,
        placeholder="É·⁰crivez ou collez votre texte ici…",
    )

    left, right = st.columns([1, 3])
    with left:
        convert = st.button("🔊 Créer le MP3", type="primary", use_container_width=True)
    with right:
        if st.button("🗑️ Effacer le texte", use_container_width=False):
            st.session_state.single_text = ""
            st.rerun()

    if convert:
        text = st.session_state.single_text.strip()
        if not text:
            st.warning("Veuillez d'abord saisir un texte.")
            return
        try:
            with st.spinner("Gé·ªné·ªration du MP3 en cours…"):
                audio = create_mp3(text, language_code, slow)
            st.success("Le fichier audio est prêt.")
            st.audio(audio, format="audio/mpeg")
            st.download_button(
                "📥 Télécharger audio.mp3",
                data=audio,
                file_name="audio.mp3",
                mime="audio/mpeg",
                type="primary",
            )
        except Exception as error:
            st.error(f"Impossible de créer le MP3 : {error}")


def show_batch_tab(language_code: str, slow: bool) -> None:
    st.subheader("Conversion par lot")
    st.write("Ajoutez une ligne par fichier, selon le modèle : `nom_du_fichier | texte à lire`.")

    st.text_area("Liste des fichiers", key="batch_text", height=250)
    controls = st.columns([1, 1, 3])
    with controls[0]:
        convert = st.button("🚀 Créer le ZIP", type="primary", use_container_width=True)
    with controls[1]:
        if st.button("🗑️ Effacer", use_container_width=True):
            st.session_state.batch_text = ""
            st.rerun()

    st.markdown("---")
    st.markdown("#### Importer un fichier CSV")
    uploaded = st.file_uploader("CSV : colonnes `nom` et `texte`", type=["csv"], key="batch_csv")
    if uploaded is not None:
        try:
            imported = parse_csv(uploaded)
            if imported:
                st.session_state.batch_text = "\n".join(f"{name} | {text}" for name, text in imported)
                st.success(f"{len(imported)} ligne(s) importé·ªe(s). Cliquez sur « Créer le ZIP ».")
            else:
                st.warning("Le CSV ne contient aucune ligne exploitable.")
        except UnicodeDecodeError:
            st.error("Le CSV doit être enregistré en UTF-8.")
        except Exception as error:
            st.error(f"Import CSV impossible : {error}")

    if convert:
        entries, errors = parse_batch_entries(st.session_state.batch_text)
        if errors:
            st.error("\n".join(errors[:10]))
            return
        if not entries:
            st.warning("Ajoutez au moins une ligne valide.")
            return
        if len(entries) > 100:
            st.warning("Pour limiter le temps de traitement, le lot est limité à 100 fichiers.")
            return

        files: List[Tuple[str, bytes]] = []
        progress = st.progress(0, text="Pré·ªparation du lot…")
        try:
            for index, (name, text) in enumerate(entries, start=1):
                progress.progress(
                    (index - 1) / len(entries),
                    text=f"Conversion {index}/{len(entries)} : {name}.mp3",
                )
                files.append((name, create_mp3(text, language_code, slow)))
            archive = create_zip(files)
            progress.progress(100, text="Archive ZIP prête.")
            st.success(f"{len(files)} fichiers MP3 ont été gé.
