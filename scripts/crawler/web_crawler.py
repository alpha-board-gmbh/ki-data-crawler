import os
import json
import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque
import time
import logging
import urllib.robotparser

# --- Projekt-Konfiguration ---
PROJECT_NAME = "zephyr_docs" # <--- HIER DEN PROJEKTNAMEN FESTLEGEN (z.B. "zephyr", "arduino", "my_company")
base_url = "https://docs.zephyrproject.org/latest/" # <--- Basis-URL für diesen spezifischen Crawl

# --- Datei- und Ordnerpfade ---
jsonl_output_file = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "processed_data", f"{PROJECT_NAME}_docs_segments.jsonl"
)
log_file_path = os.path.join(
    os.path.dirname(__file__), "..", "..", "logs", f"{PROJECT_NAME}_crawler_output.log"
)
unreachable_urls_file = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "processed_data", f"{PROJECT_NAME}_docs_unreachable_urls.jsonl"
)

# Dateierweiterungen, die ignoriert werden sollen
IGNORED_EXTENSIONS = (
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', # Bilder
    '.pdf', '.zip', '.tar', '.gz', '.rar', # Dokumente / Archive
    '.css', '.js', # Stylesheets / JavaScript
    '.ico', # Favicons
)

# Maximale Wiederholungsversuche pro URL
MAX_RETRIES = 3 
# Timeout für HTTP-Anfragen in Sekunden
HTTP_TIMEOUT = 30 # Sekunden

# HTTP-Header für Anfragen
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.88 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive'
}


# Sicherstellen, dass die Zielordner existieren
os.makedirs(os.path.dirname(jsonl_output_file), exist_ok=True)
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
os.makedirs(os.path.dirname(unreachable_urls_file), exist_ok=True)


# --- Logging-Setup ---
logger = logging.getLogger('web_crawler_logger')
logger.setLevel(logging.INFO) 
logger.propagate = False 

if not logger.handlers:
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)


# --- Globale Crawler-Variablen ---
visited_urls = set() 
urls_to_visit = deque()
newly_processed_count = 0 
failed_attempts = {} 
unreachable_urls = set() 

# Verwendung einer requests.Session für effizientere HTTP-Anfragen
session = requests.Session()

# Robots.txt Parser initialisieren und laden
rp = urllib.robotparser.RobotFileParser()
rp.set_url(urljoin(base_url, 'robots.txt'))
try:
    rp.read()
    logger.info(f"Robots.txt von {urljoin(base_url, 'robots.txt')} erfolgreich geladen.")
except Exception as e:
    logger.warning(f"FEHLER beim Laden oder Parsen der robots.txt: {e}. Crawler wird ohne robots.txt-Regeln fortfahren.")


# --- Verbesserte Resume-Logik ---
logger.info("Prüfe auf vorherigen Crawling-Status...")
if os.path.exists(jsonl_output_file):
    logger.info(f"Bestehende Datei '{jsonl_output_file}' gefunden. Lade bereits verarbeitete URLs und setze Startpunkte...")
    
    try:
        with open(jsonl_output_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f):
                try:
                    data = json.loads(line)
                    if 'url' in data:
                        visited_urls.add(data['url'])
                except json.JSONDecodeError:
                    logger.warning(f"JSON-Fehler in Zeile {line_num+1} von {jsonl_output_file}. Ignoriere Zeile.")
        
        if os.path.exists(unreachable_urls_file):
            logger.info(f"Lade bereits unerreichbare URLs aus '{unreachable_urls_file}'.")
            try:
                with open(unreachable_urls_file, 'r', encoding='utf-8') as f_unreachable:
                    for line_unreachable_num, line_unreachable in enumerate(f_unreachable):
                        try:
                            unreachable_url_data = json.loads(line_unreachable)
                            if 'url' in unreachable_url_data:
                                unreachable_urls.add(unreachable_url_data['url'])
                                visited_urls.add(unreachable_url_data['url']) 
                        except json.JSONDecodeError:
                            logger.warning(f"JSON-Fehler in Zeile {line_unreachable_num+1} von {unreachable_urls_file}. Ignoriere Zeile.")
            except Exception as e:
                logger.error(f"FEHLER beim Laden der unerreichbaren URLs: {e}")

        for url in visited_