# -*- coding: utf-8 -*-
"""Application Streamlit : Texte vers MP3 avec lots et accents anglais avec GTTS"""

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

# Configuration des langues et accents
# Pour l'anglais, lang="en" + tld spécifique pour chaque accent
LANGUAGES = {
    "Francais": {"lang": "fr", "tld": "fr"},
    "English (US)": {"lang": "en", "tld": "com"},
    "English (UK)": {"lang": "en", "tld": "co.uk"},
    "English (Irish)": {"lang": "en", "tld": "ie"},
    "English (Canadian)": {"lang": "en", "tld": "ca"},
    "English (Australian)": {"lang": "en", "tld": "com.au"},
    "English (South African)": {"lang": "en", "tld": "co.za"},
    "Espanol": {"lang": "es", "tld": "es"},
}

SPEEDS = {
    "Normale (1.0x)": False,
    "Lente (0.7x)": True,
}

INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_filename(name: str, fallback: str) -> str:
    cleaned = INVALID_FILENAME.sub("_", name.strip()).rstrip(". ")
    return (cleaned[:100] or fallback).replace(" ", "_")


def parse_batch_entries(content: str) -> Tuple[List[Tuple[str, str]], List[str]]:
    entries: List[Tuple[str, str]] = []
    errors: List[str] = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        if "|" not in line:
            errors.append(f"Ligne {line_number} : le separateur | est manquant.")
            continue
        name, text = (part.strip() for part in line.split("|", 1))
        if not text:
            errors.append(f"Ligne {line_number} : le texte est vide.")
            continue
        entries.append((safe_filename(name, f"fichier_{line_number}"), text))
    return entries, errors


def parse_csv(uploaded_file) -> List[Tuple[str, str]]:
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


def create_mp3(text: str, language: dict, slow: bool) -> bytes:
    """
    Génère un MP3 avec la langue, l'accent et la vitesse sélectionnés.
    
    Pour l'anglais : lang="en" + tld spécifique (com, co.uk, com.au, etc.)
    Pour le français : lang="fr", tld="fr"
    Pour l'espagnol : lang="es", tld="es"
    """
    buffer = io.BytesIO()

    tts = gTTS(
        text=text,
        lang=language["lang"],
        tld=language["tld"],
        slow=slow,
    )
    tts.write_to_fp(buffer)

    return buffer.getvalue()


def create_zip(files: List[Tuple[str, bytes]]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, mp3 in files:
            archive.writestr(f"{filename}.mp3", mp3)
    return output.getvalue()


def configure_state() -> None:
    st.session_state.setdefault("single_text", "")
    st.session_state.setdefault(
        "batch_text",
        "fichier_1 | Bonjour, ceci est le premier texte.\n"
        "fichier_2 | This is the second text in English.\n"
        "fichier_3 | Este es el tercer texto en espanol.",
    )


def settings_sidebar() -> Tuple[dict, bool]:
    with st.sidebar:
        st.header("Parametres audio")
        selected_name = st.selectbox("Langue / accent", list(LANGUAGES), index=1)  # index=1 → English (US) par défaut
        speed_name = st.selectbox("Vitesse", list(SPEEDS), index=0)
        st.markdown("---")
        st.caption("Accents anglais : US, UK, Irish, Canadian, Australian, South African")
        st.caption("Vitesse lente ideale pour l'apprentissage des langues.")
    return LANGUAGES[selected_name], SPEEDS[speed_name]


def show_single_tab(language: dict, slow: bool) -> None:
    st.subheader("Conversion d'un texte")
    st.text_area(
        "Votre texte",
        key="single_text",
        height=255,
        placeholder="Ecrivez ou collez votre texte ici...",
    )

    left, right = st.columns([1, 3])
    with left:
        convert = st.button("Creer le MP3", type="primary", use_container_width=True)
    with right:
        if st.button("Effacer", use_container_width=False):
            st.session_state.single_text = ""
            st.rerun()

    if convert:
        text = st.session_state.single_text.strip()
        if not text:
            st.warning("Veuillez saisir un texte.")
            return
        try:
            with st.spinner("Generation du MP3..."):
                audio = create_mp3(text, language, slow)
            st.success("Fichier audio pret.")
            st.audio(audio, format="audio/mpeg")
            st.download_button(
                "Telecharger audio.mp3",
                data=audio,
                file_name="audio.mp3",
                mime="audio/mpeg",
                type="primary",
            )
        except Exception as error:
            st.error(f"Erreur : {error}")


def show_batch_tab(language: dict, slow: bool) -> None:
    st.subheader("Conversion par lot")
    st.write("Format : nom_du_fichier | texte a lire")

    st.text_area("Liste des fichiers", key="batch_text", height=250)
    controls = st.columns([1, 1, 3])
    with controls[0]:
        convert = st.button("Creer le ZIP", type="primary", use_container_width=True)
    with controls[1]:
        if st.button("Effacer", use_container_width=True):
            st.session_state.batch_text = ""
            st.rerun()

    st.markdown("---")
    st.markdown("#### Import CSV")
    uploaded = st.file_uploader("CSV : colonnes nom et texte", type=["csv"], key="batch_csv")
    if uploaded is not None:
        try:
            imported = parse_csv(uploaded)
            if imported:
                st.session_state.batch_text = "\n".join(f"{name} | {text}" for name, text in imported)
                st.success(f"{len(imported)} ligne(s) importee(s).")
            else:
                st.warning("CSV vide ou invalide.")
        except Exception as error:
            st.error(f"Import CSV impossible : {error}")

    if convert:
        entries, errors = parse_batch_entries(st.session_state.batch_text)
        if errors:
            st.error("\n".join(errors[:10]))
            return
        if not entries:
            st.warning("Ajoutez au moins une ligne.")
            return
        if len(entries) > 100:
            st.warning("Maximum 100 fichiers par lot.")
            return

        files: List[Tuple[str, bytes]] = []
        progress = st.progress(0, text="Preparation...")
        try:
            for index, (name, text) in enumerate(entries, start=1):
                progress.progress((index - 1) / len(entries), text=f"{index}/{len(entries)} : {name}.mp3")
                files.append((name, create_mp3(text, language, slow)))
            archive = create_zip(files)
            progress.progress(100, text="ZIP pret.")
            st.success(f"{len(files)} MP3 generes.")
            st.download_button(
                f"Telecharger ZIP ({len(files)} MP3)",
                data=archive,
                file_name="conversions.zip",
                mime="application/zip",
                type="primary",
            )
            with st.expander("Voir les fichiers"):
                st.code("\n".join(f"{name}.mp3" for name, _ in files))
        except Exception as error:
            st.error(f"Erreur : {error}")


def show_help_tab() -> None:
    st.subheader("Aide")
    st.markdown(
        """
### Conversion simple
1. Choisissez langue/accent et vitesse (sidebar gauche)
2. Saisissez le texte
3. Cliquez sur "Creer le MP3"
4. Telechargez

### Conversion par lot
Format : `nom | texte`
