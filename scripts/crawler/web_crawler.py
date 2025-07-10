import os
import json
import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque
import time
import logging
import urllib.robotparser # NEU: Für robots.txt-Regeln

# --- Projekt-Konfiguration ---
PROJECT_NAME = "zephyr-docs" # <--- HIER DEN PROJEKTNAMEN FESTLEGEN (z.B. "zephyr", "arduino", "my_company")
base_url = "https://docs.zephyrproject.org/" # <--- Basis-URL für diesen spezifischen Crawl

# --- Datei- und Ordnerpfade ---
# Pfad zur JSONL-Ausgabedatei für gesammelte Segmente
jsonl_output_file = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "processed_data", f"{PROJECT_NAME}_docs_segments.jsonl"
)
# Pfad zur Log-Datei
log_file_path = os.path.join(
    os.path.dirname(__file__), "..", "..", "logs", f"{PROJECT_NAME}_crawler_output.log"
)
# Pfad zur Datei für dauerhaft unerreichbare URLs
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
    'Accept-Language': 'en-US,en;q=0.5', # Angepasst, da Zephyr Doku englisch ist
    'Connection': 'keep-alive'
}


# Sicherstellen, dass die Zielordner existieren
os.makedirs(os.path.dirname(jsonl_output_file), exist_ok=True)
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
os.makedirs(os.path.dirname(unreachable_urls_file), exist_ok=True)


# --- Logging-Setup ---
# Konfiguriere den Root-Logger, um alle Nachrichten in die Log-Datei zu schreiben
logging.basicConfig(
    level=logging.INFO, # Logge alle Meldungen ab INFO-Level
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path, encoding='utf-8')
    ]
)
# Holen Sie sich eine Instanz des Loggers, den Sie im Skript verwenden werden
logger = logging.getLogger('web_crawler_logger') # Oder einfach logging (für den Root-Logger)


# --- Globale Crawler-Variablen ---
visited_urls = set() 
urls_to_visit = deque()
newly_processed_count = 0 
failed_attempts = {} 
unreachable_urls = set() 

# Verwendung einer requests.Session für effizientere HTTP-Anfragen
session = requests.Session()

# NEU: Robots.txt Parser initialisieren und laden
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

        for url in visited_urls:
            urls_to_visit.append(url)
            
        if base_url not in urls_to_visit:
            urls_to_visit.appendleft(base_url)

        newly_processed_count = len(visited_urls)
        
        logger.info(f"{len(visited_urls)} URLs bereits erfolgreich verarbeitet und in 'visited_urls' markiert.")
        logger.info(f"{len(urls_to_visit)} URLs initial in der Warteschlange für den Neustart (inkl. bereits besuchter für Link-Discovery).")
        logger.info(f"Crawler startet effektiv bei {newly_processed_count} bereits verarbeiteten Seiten.")

    except Exception as e:
        logger.error(f"FEHLER beim Laden des bestehenden Crawling-Status: {e}")
        logger.info("Starte Crawling komplett neu.")
        visited_urls.clear()
        urls_to_visit.clear()
        urls_to_visit.append(base_url)
        newly_processed_count = 0
        failed_attempts.clear()
        unreachable_urls.clear() 
else:
    logger.info("Keine bestehende Datei gefunden. Starte Crawling neu.")
    urls_to_visit.append(base_url)

# --- Initialer Status-Output auf Konsole (für sofortiges Feedback) ---
print("\n--- Aktueller Crawler-Status ---")
print(f"Gesamt-URLs in Datei (visited_urls): {len(visited_urls)}")
print(f"URLs in der Warteschlange (urls_to_visit): {len(urls_to_visit)}")
print(f"Neu verarbeitete Seiten im aktuellen Lauf (inkl. geladener): {newly_processed_count}") 
print("----------------------------------\n")


# --- Haupt-Crawler-Logik ---
total_urls_processed_in_this_run = 0 
while urls_to_visit:
    current_url = urls_to_visit.popleft()
    
    total_urls_processed_in_this_run += 1

    if current_url in unreachable_urls:
        logger.info(f"Überspringe dauerhaft unerreichbare URL: {current_url}")
        continue 

    print(f"Verarbeitet: {total_urls_processed_in_this_run} | Queue: {len(urls_to_visit)} | Neu gesichert: {newly_processed_count} | Gesamt gesichert: {len(visited_urls)}    ", end='\r')
    
    try:
        response = session.get(current_url, timeout=HTTP_TIMEOUT, headers=HEADERS) 
        response.raise_for_status() 
        soup = BeautifulSoup(response.text, 'html.parser')

        if current_url not in visited_urls: 
            main_content_div = soup.find('div', itemprop="articleBody")
            if not main_content_div:
                main_content_div = soup.find('div', role="main", class_="document")

            if not main_content_div:
                logger.warning(f"Konnte Hauptinhalts-Div für {current_url} nicht finden. Inhalt wird nicht gespeichert.")
                visited_urls.add(current_url) 
            else:
                text_content = main_content_div.get_text(separator='\n', strip=True)
                text_content = '\n'.join(line.strip() for line in text_content.splitlines() if line.strip())

                page_title_tag = soup.find('h1')
                page_title = page_title_tag.get_text(strip=True) if page_title_tag else \
                             (soup.find('title').get_text(strip=True) if soup.find('title') else 'No Title Found')

                path_part = urlparse(current_url).path.strip('/').replace('/', '_').replace('.', '_')
                unique_id = path_part if path_part else "homepage"

                data_segment = {
                    "id": unique_id,
                    "url": current_url,
                    "title": page_title,
                    "content": text_content,
                    "source": f"{PROJECT_NAME}_docs", 
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }

                with open(jsonl_output_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(data_segment, ensure_ascii=False) + '\n')

                visited_urls.add(current_url)
                newly_processed_count += 1
                
                if newly_processed_count % 500 == 0: 
                    logger.info(f"Fortschritts-Update: Neu verarbeitete Seiten (im aktuellen Lauf): {newly_processed_count} | URLs in der Warteschlange (urls_to_visit): {len(urls_to_visit)} | Gesamt bereits in Datei (visited_urls): {len(visited_urls)}")
        
        # === Link-Discovery (IMMER ausführen nach erfolgreichem Download & Parse) ===
        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(current_url, href)

            path_without_query_fragment = urlparse(full_url).path
            _, file_extension = os.path.splitext(path_without_query_fragment)
            file_extension = file_extension.lower()

            if (urlparse(full_url).netloc == urlparse(base_url).netloc and
                full_url.startswith(base_url) and
                file_extension not in IGNORED_EXTENSIONS and 
                "#" not in full_url):
                
                # NEU: Robots.txt-Filter prüfen
                # rp.can_fetch(User-Agent, URL) prüft, ob der User-Agent die URL crawlen darf
                if rp.can_fetch(HEADERS['User-Agent'], full_url): 
                    if full_url not in visited_urls and full_url not in urls_to_visit: 
                        urls_to_visit.append(full_url)
                else:
                    logger.info(f"Link {full_url} wird aufgrund von robots.txt-Regeln nicht gecrawlt.")
    
    except requests.exceptions.RequestException as e:
        logger.error(f"FEHLER beim Crawling (HTTP/Network) von {current_url}: {e}")
        
        failed_attempts[current_url] = failed_attempts.get(current_url, 0) + 1
        
        if failed_attempts[current_url] < MAX_RETRIES:
            urls_to_visit.append(current_url) 
            logger.info(f"URL {current_url} erneut zur Warteschlange hinzugefügt ({failed_attempts[current_url]}/{MAX_RETRIES} Versuch).")
            time.sleep(5) 
        else:
            logger.warning(f"URL {current_url} hat maximale Wiederholungsversuche ({MAX_RETRIES}) erreicht. Ignoriere sie dauerhaft.")
            unreachable_urls.add(current_url) 
            visited_urls.add(current_url) 
        
    except Exception as e:
        logger.error(f"UNERWARTETER FEHLER für {current_url}: {e}")
        visited_urls.add(current_url)
        unreachable_urls.add(current_url) 


# --- Finale Aktionen nach dem Crawling ---
print("\n") 
logger.info(f"Crawling der Zephyr-Dokumentation abgeschlossen. Daten gespeichert in: {jsonl_output_file}")

if unreachable_urls:
    logger.info(f"Speichere {len(unreachable_urls)} unerreichbare URLs in: {unreachable_urls_file}")
    with open(unreachable_urls_file, 'w', encoding='utf-8') as f_unreachable:
        for url in unreachable_urls:
            unreachable_data = {
                "url": url,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "reason": f"Failed after {MAX_RETRIES} attempts (last error logged)",
            }
            f_unreachable.write(json.dumps(unreachable_data, ensure_ascii=False) + '\n')
else:
    logger.info("Keine unerreichbaren URLs während des Crawlings gefunden.")

print(f"Crawling der Zephyr-Dokumentation abgeschlossen. {len(visited_urls)} URLs gesichert.")
print(f"Details finden Sie in der Log-Datei: {log_file_path}")