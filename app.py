#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convertisseur texte-vers-MP3, avec conversion individuelle et par lot."""

import csv
import os
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from gtts import gTTS
except ImportError:
    gTTS = None

LANGUAGES = {"Français": "fr", "English": "en", "Español": "es"}
INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_filename(name, fallback):
    name = INVALID_FILENAME.sub("_", name.strip())
    name = name.rstrip(". ")
    return name[:100] or fallback


class TTSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Texte vers MP3 – conversion individuelle et par lot")
        self.root.geometry("980x700")
        self.root.minsize(780, 570)
        self.busy = False
        self.language = tk.StringVar(value="Français")
        self.status = tk.StringVar(value="Prêt.")
        self.progress = tk.DoubleVar(value=0)
        self._build_ui()

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 17, "bold"))
        style.configure("Hint.TLabel", foreground="#555555")

        container = ttk.Frame(self.root, padding=18)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="Convertisseur Texte vers MP3", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            container,
            text="Conversion simple ou traitement d'un lot de textes (un fichier MP3 par ligne).",
            style="Hint.TLabel",
        ).pack(anchor="w", pady=(2, 12))

        settings = ttk.Frame(container)
        settings.pack(fill="x", pady=(0, 10))
        ttk.Label(settings, text="Langue :").pack(side="left")
        ttk.Combobox(
            settings,
            textvariable=self.language,
            values=list(LANGUAGES),
            state="readonly",
            width=18,
        ).pack(side="left", padx=(7, 0))
        ttk.Label(
            settings,
            text="La langue choisie est utilisée pour toutes les conversions du lot.",
            style="Hint.TLabel",
        ).pack(side="left", padx=14)

        notebook = ttk.Notebook(container)
        notebook.pack(fill="both", expand=True)

        self.single_tab = ttk.Frame(notebook, padding=12)
        self.batch_tab = ttk.Frame(notebook, padding=12)
        notebook.add(self.single_tab, text="Conversion simple")
        notebook.add(self.batch_tab, text="Conversion par lot")

        self._build_single_tab()
        self._build_batch_tab()

        footer = ttk.Frame(container)
        footer.pack(fill="x", pady=(12, 0))
        ttk.Progressbar(footer, variable=self.progress, maximum=100).pack(fill="x")
        ttk.Label(footer, textvariable=self.status, style="Hint.TLabel").pack(anchor="w", pady=(5, 0))

    def _build_single_tab(self):
        ttk.Label(self.single_tab, text="Texte à convertir :").pack(anchor="w")
        self.single_text = tk.Text(self.single_tab, wrap="word", font=("Segoe UI", 11), height=20)
        self.single_text.pack(fill="both", expand=True, pady=(6, 10))
        actions = ttk.Frame(self.single_tab)
        actions.pack(fill="x")
        ttk.Button(actions, text="Ouvrir un fichier .txt", command=self.load_single_text).pack(side="left")
        ttk.Button(actions, text="Effacer", command=lambda: self.single_text.delete("1.0", "end")).pack(side="left", padx=8)
        self.single_button = ttk.Button(actions, text="Convertir en MP3", command=self.start_single)
        self.single_button.pack(side="right")

    def _build_batch_tab(self):
        ttk.Label(
            self.batch_tab,
            text="Ajoutez une ligne par fichier : nom du fichier | texte à lire",
        ).pack(anchor="w")
        ttk.Label(
            self.batch_tab,
            text="Exemple : bonjour | Bonjour à tous !  →  bonjour.mp3",
            style="Hint.TLabel",
        ).pack(anchor="w", pady=(2, 6))

        self.batch_text = tk.Text(self.batch_tab, wrap="word", font=("Segoe UI", 11), height=18)
        self.batch_text.pack(fill="both", expand=True, pady=(0, 10))
        self.batch_text.insert(
            "1.0",
            "fichier_1 | Bonjour, ceci est le premier texte.\n"
            "fichier_2 | This is the second text.\n"
            "fichier_3 | Este es el tercer texto.",
        )

        actions = ttk.Frame(self.batch_tab)
        actions.pack(fill="x")
        ttk.Button(actions, text="Importer un CSV", command=self.import_csv).pack(side="left")
        ttk.Button(actions, text="Charger un exemple", command=self.load_example).pack(side="left", padx=8)
        ttk.Button(actions, text="Effacer", command=lambda: self.batch_text.delete("1.0", "end")).pack(side="left")
        self.batch_button = ttk.Button(actions, text="Créer tous les MP3", command=self.start_batch)
        self.batch_button.pack(side="right")

        ttk.Label(
            self.batch_tab,
            text="CSV accepté : deux colonnes nom,texte (avec ou sans ligne d'en-tête).",
            style="Hint.TLabel",
        ).pack(anchor="w", pady=(8, 0))

    def load_single_text(self):
        path = filedialog.askopenfilename(filetypes=[("Fichiers texte", "*.txt"), ("Tous les fichiers", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as file:
                content = file.read()
            self.single_text.delete("1.0", "end")
            self.single_text.insert("1.0", content)
        except OSError as error:
            messagebox.showerror("Erreur", f"Impossible de lire le fichier.\n{error}")

    def load_example(self):
        self.batch_text.delete("1.0", "end")
        self.batch_text.insert(
            "1.0",
            "salutation | Bonjour à toutes et à tous.\n"
            "instructions | Écoutez attentivement puis répétez.\n"
            "good_morning | Good morning, class!",
        )

    def import_csv(self):
        path = filedialog.askopenfilename(filetypes=[("Fichiers CSV", "*.csv"), ("Tous les fichiers", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as file:
                sample = file.read(2048)
                file.seek(0)
                dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
                rows = list(csv.reader(file, dialect))
            if rows and [cell.lower().strip() for cell in rows[0][:2]] in (["nom", "texte"], ["name", "text"]):
                rows = rows[1:]
            entries = [f"{row[0]} | {row[1]}" for row in rows if len(row) >= 2 and row[1].strip()]
            if not entries:
                raise ValueError("Le CSV ne contient aucune ligne exploitable.")
            self.batch_text.delete("1.0", "end")
            self.batch_text.insert("1.0", "\n".join(entries))
            self.status.set(f"{len(entries)} entrée(s) importée(s).")
        except Exception as error:
            messagebox.showerror("Import CSV", f"Impossible d'importer ce fichier.\n{error}")

    def start_single(self):
        text = self.single_text.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("Texte manquant", "Saisissez un texte avant de lancer la conversion.")
            return
        path = filedialog.asksaveasfilename(
            title="Enregistrer le fichier MP3",
            defaultextension=".mp3",
            initialfile="audio.mp3",
            filetypes=[("Fichier MP3", "*.mp3")],
        )
        if path:
            self.run_background(self.convert_one, text, path, "1/1")

    def start_batch(self):
        entries, errors = self.parse_batch_entries()
        if errors:
            messagebox.showerror("Format du lot", "\n".join(errors[:8]))
            return
        if not entries:
            messagebox.showwarning("Lot vide", "Ajoutez au moins une ligne au format : nom | texte")
            return
        folder = filedialog.askdirectory(title="Choisissez le dossier de destination des MP3")
        if folder:
            self.run_background(self.convert_batch, entries, folder)

    def parse_batch_entries(self):
        entries, errors = [], []
        for number, line in enumerate(self.batch_text.get("1.0", "end").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            if "|" not in line:
                errors.append(f"Ligne {number} : séparateur « | » manquant.")
                continue
            name, text = line.split("|", 1)
            name, text = name.strip(), text.strip()
            if not text:
                errors.append(f"Ligne {number} : texte manquant.")
                continue
            entries.append((safe_filename(name, f"fichier_{number}"), text))
        return entries, errors

    def run_background(self, function, *args):
        if gTTS is None:
            messagebox.showerror("Dépendance manquante", "Installez gTTS avec la commande :\npip install gTTS")
            return
        if self.busy:
            return
        self.busy = True
        self.single_button.configure(state="disabled")
        self.batch_button.configure(state="disabled")
        self.progress.set(0)
        threading.Thread(target=self._worker, args=(function, args), daemon=True).start()

    def _worker(self, function, args):
        try:
            function(*args)
        except Exception as error:
            self.root.after(0, lambda: messagebox.showerror("Erreur", str(error)))
            self.root.after(0, lambda: self.status.set("Une erreur est survenue."))
        finally:
            self.root.after(0, self.finish)

    def finish(self):
        self.busy = False
        self.single_button.configure(state="normal")
        self.batch_button.configure(state="normal")

    def update_progress(self, value, text):
        self.root.after(0, lambda: (self.progress.set(value), self.status.set(text)))

    def convert_one(self, text, output_path, label):
        self.update_progress(10, "Génération du fichier MP3…")
        gTTS(text=text, lang=LANGUAGES[self.language.get()]).save(output_path)
        self.update_progress(100, f"Terminé : {os.path.basename(output_path)}")
        self.root.after(0, lambda: messagebox.showinfo("Conversion terminée", f"Fichier créé :\n{output_path}"))

    def convert_batch(self, entries, folder):
        language = LANGUAGES[self.language.get()]
        created, failed = [], []
        total = len(entries)
        for index, (name, text) in enumerate(entries, 1):
            output_path = os.path.join(folder, f"{name}.mp3")
            self.update_progress((index - 1) * 100 / total, f"Création {index}/{total} : {name}.mp3")
            try:
                gTTS(text=text, lang=language).save(output_path)
                created.append(output_path)
            except Exception as error:
                failed.append(f"{name}.mp3 : {error}")
        self.update_progress(100, f"Lot terminé : {len(created)}/{total} fichier(s) créé(s).")
        message = f"{len(created)} fichier(s) MP3 créé(s) dans :\n{folder}"
        if failed:
            message += "\n\nÉchecs :\n" + "\n".join(failed[:5])
        self.root.after(0, lambda: messagebox.showinfo("Traitement par lot terminé", message))


def main():
    root = tk.Tk()
    TTSApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
