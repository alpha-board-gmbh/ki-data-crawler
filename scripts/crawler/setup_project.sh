#!/bin/bash

echo "--- Initialisiere Web-Daten-Sammler Projektstruktur (fürs Anlernen von Ki-Modellen ---"

# Navigiere zum Skript-Verzeichnis, um relative Pfade zu sichern
# Dies stellt sicher, dass das Skript immer von seinem eigenen Verzeichnis aus ausgeführt wird
SCRIPT_DIR=$(dirname "$0")
cd "$SCRIPT_DIR" || exit

# 0. Deaktiviere eventuell aktive virtuelle Umgebungen
# Dies verhindert Konflikte mit anderen VENVs, falls bereits aktiv
echo "Deaktiviere eventuell aktive virtuelle Umgebung..."
deactivate 2>/dev/null || true # 2>/dev/null unterdrückt Fehlermeldungen, wenn kein venv aktiv ist

# 1. Ordnerstruktur erstellen
echo "Erstelle Daten- und Skriptordner..."
mkdir -p data/raw_data/web_crawls    # Neuer, neutraler Ordner für Webseiten-Rohdaten (wenn direkt gespeichert)
mkdir -p data/raw_data/repo_clones   # Neuer, neutraler Ordner für Repository-Klone
mkdir -p data/processed_data
mkdir -p scripts/crawler
mkdir -p scripts/parser
mkdir -p logs # Für Log-Dateien

echo "Ordnerstruktur erstellt."

# 2. Virtuelle Umgebung einrichten und aktivieren
VENV_NAME="venv-crawl" # Eindeutiger Name für die virtuelle Umgebung
echo "Richte virtuelle Python-Umgebung '$VENV_NAME' ein..."
if [ -d "$VENV_NAME" ]; then
    echo "Virtuelle Umgebung '$VENV_NAME' existiert bereits. Überspringe Erstellung."
else
    python3 -m venv "$VENV_NAME"
    echo "Virtuelle Umgebung '$VENV_NAME' erstellt."
fi

echo "Aktiviere virtuelle Umgebung und installiere Python-Bibliotheken..."
source "$VENV_NAME"/bin/activate

# 3. Benötigte Python-Bibliotheken installieren
# Erstelle oder aktualisiere requirements.txt zuerst
echo "Generiere/Aktualisiere requirements.txt..."
# Temporäre Installation, um requirements.txt zu generieren, falls nicht vorhanden
# Wenn Sie requirements.txt manuell pflegen, entfernen Sie diese Zeilen
pip install requests beautifulsoup4 lxml tqdm # Sicherstellen, dass Basis-Libs zum Generieren da sind
pip freeze > requirements.txt

echo "Installiere Python-Bibliotheken aus requirements.txt..."
pip install -r requirements.txt

echo "Python-Bibliotheken installiert."
echo "Virtuelle Umgebung '$VENV_NAME' ist jetzt aktiv. Bitte denken Sie daran, 'source $VENV_NAME/bin/activate' auszuführen, wenn Sie ein neues Terminal starten."
echo "--- Initialisierung abgeschlossen ---"