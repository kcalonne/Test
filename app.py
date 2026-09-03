# -*- coding: utf-8 -*-
"""
Convertisseur Texte vers MP3 - Version Streamlit Cloud
Dé¬°ploiement gratuit sur https://streamlit.io/cloud
"""

import csv
import io
import os
import re
import zipfile
from typing import List, Tuple

import streamlit as st
from gtts import gTTS

# Configuration de la page
st.set_page_config(
    page_title="Convertisseur Texte vers MP3",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Constantes
LANGUAGES = {"Franç¬°ais": "fr", "English": "en", "Españ¬°¬∞ol": "es"}
INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_filename(name: str, fallback: str) -> str:
    """Nettoie un nom de fichier pour qu'il soit valide."""
    name = INVALID_FILENAME.sub("_", name.strip())
    name = name.rstrip(". ")
    return (name[:100] or fallback).replace(" ", "_").lower()


def parse_batch_entries(text: str) -> Tuple[List[Tuple[str, str]], List[str]]:
    """Parse les entré¬°es batch et retourne (entré¬°es, erreurs)."""
    entries, errors = [], []
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        if "|" not in line:
            errors.append(f"Ligne {number} : séparateur « | » manquant")
            continue
        parts = line.split("|", 1)
        if len(parts) != 2:
            errors.append(f"Ligne {number} : format invalide")
            continue
        name, text_content = parts[0].strip(), parts[1].strip()
        if not text_content:
            errors.append(f"Ligne {number} : texte manquant")
            continue
        entries.append((safe_filename(name, f"fichier_{number}"), text_content))
    return entries, errors


def convert_text_to_mp3(text: str, language: str) -> bytes:
    """Convertit un texte en MP3 et retourne les bytes."""
    tts = gTTS(text=text, lang=language, slow=False)
    mp3_io = io.BytesIO()
    tts.write_to_fp(mp3_io)
    mp3_io.seek(0)
    return mp3_io.read()


def create_zip_from_mp3s(mp3_files: List[Tuple[str, bytes]]) -> bytes:
    """Cré¬°e un fichier ZIP contenant plusieurs MP3."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for filename, mp3_data in mp3_files:
            zip_file.writestr(f"{filename}.mp3", mp3_data)
    zip_buffer.seek(0)
    return zip_buffer.read()


def main():
    """Application principale Streamlit."""

    # En-t™te
    st.title("🎙️ Convertisseur Texte vers MP3")
    st.markdown(
        """
        Convertissez vos textes en fichiers audio MP3. 
        **Conversion simple** ou **par lot** avec t&eacute;l&eacute;chargement.
        """
    )

    # Sidebar - S&eacute;lection de la langue
    with st.sidebar:
        st.header("⚙️ Param&egrave;tres")
        selected_language = st.selectbox(
            "Langue",
            options=list(LANGUAGES.keys()),
            index=0,
            help="La langue choisie est utilis&eacute;e pour toutes les conversions",
        )
        st.info(
            "💡 **Astuce** : gTTS n&eacute;cessite une connexion Internet pour fonctionner."
        )
        st.markdown("---")
        st.markdown(
            """
            **Fonctionnalit&eacute;s :**
            - Conversion texte → MP3
            - Mode batch (plusieurs fichiers)
            - Import CSV
            - T&eacute;l&eacute;chargement ZIP
            """
        )

    # Onglets
    tab1, tab2, tab3 = st.tabs(["📝 Conversion simple", "📦 Conversion par lot", "ℹ️ Aide"])

    # ============================================
    # ONGLET 1 : CONVERSION SIMPLE
    # ============================================
    with tab1:
        st.header("Conversion d'un seul texte")

        text_input = st.text_area(
            "Votre texte",
            height=200,
            placeholder="Saisissez ou collez votre texte ici...",
            help="Vous pouvez aussi importer un fichier .txt depuis l'onglet Aide",
        )

        col1, col2, col3 = st.columns([1, 1, 2])

        with col1:
            convert_btn = st.button("🔊 Convertir", type="primary", use_container_width=True)

        with col2:
            if st.button("🗑️ Effacer", use_container_width=True):
                st.session_state.single_text = ""
                st.rerun()

        with col3:
            st.empty()

        if convert_btn and text_input.strip():
            try:
                with st.spinner("G&eacute;n&eacute;ration du fichier MP3 en cours..."):
                    language_code = LANGUAGES[selected_language]
                    mp3_data = convert_text_to_mp3(text_input.strip(), language_code)

                st.success("✅ Fichier MP3 g&eacute;n&eacute;r&eacute; avec succ&egrave;s !")

                # T&eacute;l&eacute;chargement
                st.download_button(
                    label="📥 T&eacute;l&eacute;charger le MP3",
                    data=mp3_data,
                    file_name="audio.mp3",
                    mime="audio/mpeg",
                    use_container_width=True,
                )

            except Exception as e:
                st.error(f"❌ Erreur lors de la conversion : {str(e)}")
                st.info(
                    "V&eacute;rifiez votre connexion Internet (gTTS n&eacute;cessite un acc&egrave;s au web)."
                )

        elif convert_btn and not text_input.strip():
            st.warning("⚠️ Veuillez saisir du texte avant de convertir.")

    # ============================================
    # ONGLET 2 : CONVERSION PAR LOT
    # ============================================
    with tab2:
        st.header("Conversion de plusieurs textes (batch)")

        st.markdown(
            """
            **Format :** une ligne par fichier au format `nom | texte`
            
            **Exemple :**
            ```
            fichier_1 | Bonjour, ceci est le premier texte.
            fichier_2 | This is the second text in English.
            fichier_3 | Este es el tercer texto en español.
            ```
            """
        )

        # Zone de texte pour le batch
        batch_input = st.text_area(
            "Vos textes (un par ligne)",
            value="fichier_1 | Bonjour, ceci est le premier texte à convertir en audio.\nfichier_2 | This is the second text in English for demonstration.\nfichier_3 | Este es el tercer texto en español para probar el software.",
            height=250,
            help="Ajoutez une ligne par fichier : nom | texte",
        )

        # Boutons d'action
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            convert_batch_btn = st.button("🚀 Convertir tout le lot", type="primary", use_container_width=True)

        with col2:
            if st.button("📂 Charger exemple", use_container_width=True):
                st.session_state.batch_example = True
                st.rerun()

        with col3:
            if st.button("🗑️ Effacer", use_container_width=True):
                st.session_state.batch_input = ""
                st.rerun()

        with col4:
            st.empty()

        # Gestion de l'exemple
        if st.session_state.get("batch_example", False):
            batch_input = "fichier_1 | Bonjour, ceci est le premier texte à convertir en audio.\nfichier_2 | This is the second text in English for demonstration.\nfichier_3 | Este es el tercer texto en español para probar el software.\nintroduction | Bienvenue dans cette leç¬°on de langue étrang&egrave;re.\nexercise_1 | Répé¬°tez apr&egrave;s moi : bonjour, merci, au revoir."
            st.session_state.batch_example = False

        # Import CSV
        st.markdown("---")
        st.subheader("📄 Import CSV (optionnel)")

        uploaded_file = st.file_uploader(
            "Importer un fichier CSV",
            type=["csv"],
            help="Format : deux colonnes nom,texte (avec ou sans ligne d'en-t™te)",
        )

        if uploaded_file is not None:
            try:
                content = uploaded_file.read().decode("utf-8-sig")
                lines = content.strip().split("\n")

                # Détection et suppression de l'en-t™te
                if lines and lines[0].lower().startswith(("nom", "name")):
                    lines = lines[1:]

                # Conversion en format batch
                batch_lines = []
                for line in lines:
                    if line.strip():
                        parts = line.split(",", 1)
                        if len(parts) == 2:
                            name = parts[0].strip().strip('"')
                            text = parts[1].strip().strip('"')
                            if text:
                                batch_lines.append(f"{name} | {text}")

                if batch_lines:
                    st.success(f"✅ {len(batch_lines)} entr&eacute;e(s) import&eacute;e(s)")
                    batch_input = "\n".join(batch_lines)
                else:
                    st.warning("⚠️ Aucune donn&eacute;e valide trouv&eacute;e dans le CSV")

            except Exception as e:
                st.error(f"❌ Erreur lors de l'import : {str(e)}")

        # Conversion batch
        if convert_batch_btn and batch_input.strip():
            entries, errors = parse_batch_entries(batch_input)

            if errors:
                st.error("❌ Erreurs dans le format :\n\n" + "\n".join(errors[:5]))
                if len(errors) > 5:
                    st.warning(f"... et {len(errors) - 5} autres erreurs")
            elif not entries:
                st.warning("⚠️ Aucune entr&eacute;e valide trouv&eacute;e")
            else:
                try:
                    with st.spinner(f"G&eacute;n&eacute;ration de {len(entries)} fichier(s) MP3..."):
                        language_code = LANGUAGES[selected_language]
                        mp3_files = []

                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        for idx, (name, text) in enumerate(entries, 1):
                            status_text.text(f"Conversion {idx}/{len(entries)} : {name}.mp3")
                            mp3_data = convert_text_to_mp3(text, language_code)
                            mp3_files.append((name, mp3_data))
                            progress_bar.progress(idx / len(entries))

                        status_text.text("Cr&eacute;ation du fichier ZIP...")

                        # Cr&eacute;ation du ZIP
                        zip_data = create_zip_from_mp3s(mp3_files)

                        st.success(f"✅ {len(entries)} fichier(s) MP3 g&eacute;n&eacute;r&eacute;(s) avec succ&egrave;s !")

                        # T&eacute;l&eacute;chargement ZIP
                        st.download_button(
                            label=f"📥 T&eacute;l&eacute;charger le ZIP ({len(entries)} MP3)",
                            data=zip_data,
                            file_name="conversions.zip",
                            mime="application/zip",
                            use_container_width=True,
                        )

                        # Liste des fichiers
                        with st.expander("📋 Voir la liste des fichiers"):
                            for name, _ in mp3_files:
                                st.write(f"- `{name}.mp3`")

                except Exception as e:
                    st.error(f"❌ Erreur lors de la conversion : {str(e)}")
                    st.info(
                        "V&eacute;rifiez votre connexion Internet (gTTS n&eacute;cessite un acc&egrave;s au web)."
                    )

        elif convert_batch_btn and not batch_input.strip():
            st.warning("⚠️ Veuillez saisir des textes avant de convertir.")

    # ============================================
    # ONGLET 3 : AIDE
    # ============================================
    with tab3:
        st.header("ℹ️ Aide et informations")

        st.markdown(
            """
            ### 🎯 Comment utiliser cette application ?
            
            #### Conversion simple
            1. Saisissez votre texte dans la zone de texte
            2. S&eacute;lectionnez la langue dans la sidebar
            3. Cliquez sur "Convertir"
            4. T&eacute;l&eacute;chargez le fichier MP3
            
            #### Conversion par lot
            1. Ajoutez une ligne par fichier : `nom | texte`
            2. Cliquez sur "Convertir tout le lot"
            3. T&eacute;l&eacute;chargez le fichier ZIP contenant tous les MP3
            
            ### 📄 Format CSV accept&eacute;
            
            ```csv
            nom,texte
            bonjour,"Bonjour à tous"
            hello,"Hello everyone"
            ```
            
            ### 🌐 D&eacute;ploiement sur Streamlit Cloud
            
            1. Cr&eacute;ez un compte sur [streamlit.io](https://streamlit.io)
            2. Connectez votre d&eacute;p™t GitHub
            3. S&eacute;lectionnez ce fichier `app_streamlit.py`
            4. D&eacute;ploiez gratuitement !
            
            ### ⚠️ Limitations
            
            - **gTTS n&eacute;cessite une connexion Internet**
            - Texte maximum : ~5000 caract&egrave;res par conversion
            - Limite de d&eacute;p™t : 100 fichiers par lot (recommand&eacute;)
            
            ### 🔧 Technologies utilis&eacute;es
            
            - **Streamlit** : interface web
            - **gTTS** : Google Text-to-Speech
            - **Python** : langage de programmation
            """
        )

        st.markdown("---")
        st.info(
            "💡 **Astuce** : Pour importer un fichier texte, copiez-collez simplement son contenu dans la zone de texte."
        )


if __name__ == "__main__":
    main()
