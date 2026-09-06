# -*- coding: utf-8 -*-
"""Application Streamlit : Texte vers MP3 avec lots, accents anglais et vitesses."""

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
    "Français": "fr",
    "English (US)": "en",
    "English (UK)": "en-uk",
    "English (Irish)": "en-ie",
    "English (Canadian)": "en-ca",
    "English (Australian)": "en-au",
    "English (South African)": "en-za",
    "Español": "es",
}

# gTTS propose seulement deux vitesses publiques : normale et lente.
# Les facteurs 0.8x, 0.6x et 0.5x sont appliqués après la synthèse via pydub/ffmpeg.
SPEEDS = {
    "Normale (1.0x)": 1.0,
    "Lent (0.8x)": 0.8,
    "Très lent (0.6x)": 0.6,
    "Extrêmement lent (0.5x)": 0.5,
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


def mp3_at_speed(mp3_data: bytes, speed: float) -> bytes:
    """Change la vitesse sans modifier la hauteur de la voix."""
    if speed == 1.0:
        return mp3_data

    from pydub import AudioSegment

    source = AudioSegment.from_file(io.BytesIO(mp3_data), format="mp3")
    changed = source._spawn(
        source.raw_data,
        overrides={"frame_rate": int(source.frame_rate * speed)},
    ).set_frame_rate(source.frame_rate)
    result = io.BytesIO()
    changed.export(result, format="mp3", bitrate="128k")
    return result.getvalue()


def create_mp3(text: str, language_code: str, speed: float) -> bytes:
    """Génère un MP3 gTTS et applique ensuite la vitesse choisie."""
    buffer = io.BytesIO()
    gTTS(text=text, lang=language_code, slow=False).write_to_fp(buffer)
    return mp3_at_speed(buffer.getvalue(), speed)


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


def settings_sidebar() -> Tuple[str, float]:
    with st.sidebar:
        st.header("⚙️ Paramètres audio")
        selected_name = st.selectbox("Langue / accent", list(LANGUAGES), index=0)
        speed_name = st.selectbox("Vitesse d'enregistrement", list(SPEEDS), index=0)
        st.markdown("---")
        st.caption("Les accents proposés s'appliquent aux textes anglais.")
        st.caption("Les MP3 ralentis sont traités avec FFmpeg dans l'environnement Streamlit.")
        st.markdown("### Accents anglais")
        st.markdown("US · UK · Irish · Canadian · Australian · South African")
    return LANGUAGES[selected_name], SPEEDS[speed_name]


def show_single_tab(language_code: str, speed: float) -> None:
    st.subheader("Conversion d'un texte")
    st.text_area(
        "Votre texte",
        key="single_text",
        height=255,
        placeholder="Écrivez ou collez votre texte ici…",
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
            with st.spinner("Génération du MP3 en cours…"):
                audio = create_mp3(text, language_code, speed)
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


def show_batch_tab(language_code: str, speed: float) -> None:
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
                st.success(f"{len(imported)} ligne(s) importée(s). Cliquez sur « Créer le ZIP ».")
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
        progress = st.progress(0, text="Préparation du lot…")
        try:
            for index, (name, text) in enumerate(entries, start=1):
                progress.progress(
                    (index - 1) / len(entries),
                    text=f"Conversion {index}/{len(entries)} : {name}.mp3",
                )
                files.append((name, create_mp3(text, language_code, speed)))
            archive = create_zip(files)
            progress.progress(100, text="Archive ZIP prête.")
            st.success(f"{len(files)} fichiers MP3 ont été générés.")
            st.download_button(
                f"📥 Télécharger conversions.zip ({len(files)} MP3)",
                data=archive,
                file_name="conversions.zip",
                mime="application/zip",
                type="primary",
            )
            with st.expander("Voir les fichiers inclus"):
                st.code("\n".join(f"{name}.mp3" for name, _ in files))
        except Exception as error:
            st.error(f"Erreur pendant le traitement du lot : {error}")


def show_help_tab() -> None:
    st.subheader("Aide")
    st.markdown(
        """
### Conversion simple
1. Choisissez la langue ou l'accent et la vitesse dans le panneau de gauche.
2. Saisissez le texte puis cliquez sur **Créer le MP3**.
3. Écoutez-le dans la page ou téléchargez-le.

### Conversion par lot
Utilisez une ligne par audio, avec le format `nom | texte` :

```text
lesson_01 | Good morning, class.
lesson_02 | Please listen and repeat.
```

L'application produit une archive ZIP contenant `lesson_01.mp3` et `lesson_02.mp3`.

### CSV
Le CSV doit être encodé en UTF-8 et contenir deux colonnes :

```csv
nom,texte
lesson_01,"Good morning, class."
lesson_02,"Please listen and repeat."
```

### Limites
- Une connexion Internet est nécessaire pour Google Text-to-Speech.
- Les traitements lents (0.8x, 0.6x, 0.5x) reposent sur FFmpeg.
- Pour Streamlit Community Cloud, commencez par des lots de 10 à 30 fichiers ; le maximum intégré est de 100 fichiers par lot.
"""
    )


def main() -> None:
    configure_state()
    st.title("🎙️ Convertisseur Texte vers MP3")
    st.caption("Textes individuels ou lots · MP3 téléchargeables · accents anglais · vitesses pédagogiques")
    language_code, speed = settings_sidebar()

    simple, batch, help_tab = st.tabs(["📝 Conversion simple", "📦 Conversion par lot", "ℹ️ Aide"])
    with simple:
        show_single_tab(language_code, speed)
    with batch:
        show_batch_tab(language_code, speed)
    with help_tab:
        show_help_tab()


if __name__ == "__main__":
    main()
