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
import re # NEU: Für reguläre Ausdrücke

# NEU: Warnungen für XMLParsedAsHTMLWarning unterdrücken
import warnings
from bs4 import XMLParsedAsHTMLWarning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


# --- Projekt-Konfiguration ---
PROJECT_NAME = "zephyr" # <--- HIER DEN PROJEKTNAMEN FESTLEGEN (z.B. "zephyr", "arduino", "my_company")
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

# NEU: Pfad zur Datei für gesammelte GitHub-Links
github_links_output_file = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "processed_data", f"{PROJECT_NAME}_github_links.jsonl"
)

# NEU: Domains, die als GitHub-Links gesammelt werden sollen
GITHUB_DOMAINS = ["github.com", "raw.githubusercontent.com"]
# NEU: Dateierweiterungen, die von GitHub-Links interessant sind
GITHUB_FILE_EXTENSIONS = (
    '.c', '.h', '.cpp', '.hpp', # C/C++ Source and Headers
    '.dts', '.dtsi',           # Device Tree Source and Includes
    'Kconfig', '.kconfig',     # Kconfig files
    '.cmake', 'CMakeLists.txt', # CMake build files
    '.py',                     # Python scripts
    '.md', '.rst',             # Markdown/reStructuredText
    '.txt', '.json', '.yaml', '.yml' # Andere relevante Textdateien
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

# Mindestlänge des Textinhalts (in Zeichen). Anpassen nach Bedarf.
MIN_CONTENT_LENGTH = 100 

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
os.makedirs(os.path.dirname(github_links_output_file), exist_ok=True)


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
collected_github_links = set() # NEU: Für Links zu GitHub-Dateien

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
        
        # NEU: Lade bereits gesammelte GitHub-Links, falls vorhanden
        if os.path.exists(github_links_output_file):
            logger.info(f"Lade bereits gesammelte GitHub-Links aus '{github_links_output_file}'.")
            try:
                with open(github_links_output_file, 'r', encoding='utf-8') as f_github_links:
                    for line_github_num, line_github in enumerate(f_github_links):
                        try:
                            github_link_data = json.loads(line_github)
                            if 'url' in github_link_data:
                                collected_github_links.add(github_link_data['url'])
                        except json.JSONDecodeError:
                            logger.warning(f"JSON-Fehler in Zeile {line_github_num+1} von {github_links_output_file}. Ignoriere Zeile.")
            except Exception as e:
                logger.error(f"FEHLER beim Laden der GitHub-Links: {e}")

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
        collected_github_links.clear()
else:
    logger.info("Keine bestehende Datei gefunden. Starte Crawling neu.")
    urls_to_visit.append(base_url)
    # NEU: collected_github_links muss auch hier initialisiert werden (was es als leeres Set schon ist, aber zur Klarheit)
    collected_github_links.clear() # Sicherstellen, dass bei Neustart leer

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

        # === Hauptinhalts-Extraktion und Speicherung (NUR wenn noch NICHT besucht) ===
        if current_url not in visited_urls: 
            # Selektoren in der Reihenfolge der Präferenz/Umfassung
            main_content_div = soup.find('div', itemprop="articleBody")
            if not main_content_div:
                main_content_div = soup.find('div', role="main", class_="document")
            if not main_content_div: 
                main_content_div = soup.find('div', class_='textblock')
            if not main_content_div: 
                main_content_div = soup.find('div', class_='contents') # Für Doxygen Gruppen/Modul-Seiten
            if not main_content_div: 
                main_content_div = soup.find('div', id='doc-content') # Generischer Doxygen-Inhalt
            if not main_content_div: 
                main_content_div = soup.find('div', id='content') # Noch generischerer Fallback
            
            memdoc_contents = [] # Für den Fall, dass wir memdoc-Blöcke sammeln
            if not main_content_div: # Nur versuchen, wenn bisher kein Haupt-Div gefunden wurde
                all_memdocs = soup.find_all('div', class_='memdoc')
                if all_memdocs:
                    for memdoc_div in all_memdocs:
                        memitem_parent = memdoc_div.find_parent('div', class_='memitem')
                        if memitem_parent:
                            memtitle_tag = memitem_parent.find(['h2', 'h3'], class_='memtitle') 
                            if memtitle_tag:
                                memdoc_contents.append(f"TITLE: {memtitle_tag.get_text(separator=' ', strip=True)}\n")
                        
                        memdoc_contents.append(memdoc_div.get_text(separator='\n', strip=True))
                        memdoc_contents.append("\n---\n") # Trennzeichen zwischen einzelnen memdocs
                    
                    if memdoc_contents:
                        main_content_div = "MEMDOCS_COLLECTED" # Dummy-Wert, signalisiert Inhalt gefunden


            text_content = ""
            page_title = ""

            if main_content_div and main_content_div != "MEMDOCS_COLLECTED": # Regulärer Div gefunden
                text_content = main_content_div.get_text(separator='\n', strip=True)
                
                page_title_tag = soup.find('h1')
                page_title = page_title_tag.get_text(strip=True) if page_title_tag else \
                             (soup.find('title').get_text(strip=True) if soup.find('title') else 'No Title Found')
            elif main_content_div == "MEMDOCS_COLLECTED" and memdoc_contents: # Inhalt aus MemDocs gesammelt
                text_content = '\n'.join(memdoc_contents) # memdoc_contents enthält bereits gestrippte Zeilen und Trenner
                page_title = soup.find('title').get_text(strip=True) if soup.find('title') else 'No Title Found (MemDocs)'
            else: # Immer noch kein Hauptinhalt gefunden, dies ist eine Warnung
                logger.warning(f"Konnte Hauptinhalts-Div für {current_url} nicht finden (alle Selektoren fehlgeschlagen). Inhalt wird nicht gespeichert.")
                visited_urls.add(current_url) 
                continue # Überspringe den Rest der Verarbeitung für diese URL


            # --- NEU HINZUZUFÜGENDE TEXTBEREINIGUNG START ---
            # 1. Allgemeine Kodierungs- und Sonderzeichenbereinigung
            text_content = text_content.replace('ïƒ', '') # Entfernt das spezielle Unicode-Zeichen
            text_content = text_content.replace('â€™', "'") # Korrigiert falsch dekodiertes Apostroph (Right Single Quotation Mark)
            text_content = text_content.replace('â€œ', '"').replace('â€', '"') # Korrigiert Anführungszeichen (Left/Right Double Quotation Mark)
            text_content = text_content.replace('â€“', '-') # Korrigiert Gedankenstrich (En Dash)
            text_content = text_content.replace('â€¢', '-') # Korrigiert Aufzählungszeichen (Bullet)
            # Weitere häufige Probleme: Unicode Zero Width Space (U+200B) oder Non-breaking Space (U+00A0)
            text_content = text_content.replace('\u200b', '').replace('\u00a0', ' ')
            
            # 2. Spezifische Bereinigung für Doxygen Source-Dateien (.h_source.html, .c_source.html)
            # Hier müssen wir präziser werden, da die vorherige Regex-Logik nicht alle Fälle abdeckte.
            if "doxygen/html/" in current_url and "_source.html" in current_url:
                lines = text_content.splitlines()
                cleaned_source_lines = []
                
                # Muster für Doxygen-Source-Header (Go to ..., Copyright)
                # und für generierte Fußzeilen (Definition, Dateiname:Zeile)
                in_doxygen_source_header = True
                in_doxygen_source_footer = False
                
                for line in lines:
                    stripped_line = line.strip()

                    # Erkennung des Endes des Headers (beginnt nach Copyright, endet vor erstem #ifndef / #define / echtem Code)
                    if in_doxygen_source_header:
                        # Findet den Beginn des Copyright-Blocks
                        if re.match(r'^\d+\s*\/\*.*Copyright \(c\).*', stripped_line) or stripped_line == "Go to the documentation of this file.":
                            continue # Überspringe diese Zeile
                        # Ende des Copyright-Blocks, Beginn des eigentlichen Codes
                        if re.match(r'^\d+\s*#ifndef', stripped_line) or re.match(r'^\d+\s*#define', stripped_line) or re.match(r'^\d+\s*\w+\s+\w+', stripped_line):
                            in_doxygen_source_header = False
                            # Wenn es eine Zeilennummer hat, entfernen wir sie hier
                            if stripped_line and stripped_line[0].isdigit() and (' ' in stripped_line or '\t' in stripped_line):
                                parts = stripped_line.split(' ', 1)
                                if len(parts) > 1 and parts[0].isdigit():
                                    cleaned_source_lines.append(parts[1])
                                else:
                                    cleaned_source_lines.append(line)
                            else:
                                cleaned_source_lines.append(line)
                            continue
                        else:
                            continue # Überspringe weiterhin Header-Zeilen
                    
                    # Logik für Footer (muss nach dem Header-Handling kommen)
                    # Erkennen des Beginns des generierten Fußzeilenblocks
                    if re.match(r'^(Definition|Flags|Size)\n', line) or \
                       re.match(r'^[a-zA-Z_]+\s*$', line) or \
                       (re.match(r'^.*\.h:[\d]+$', line) and not in_doxygen_source_header): # Dateireferenz ohne Zeilennummer
                        in_doxygen_source_footer = True

                    if in_doxygen_source_footer:
                        continue # Überspringe alle Zeilen im Footer

                    # Normale Zeilen verarbeiten
                    # Entferne nur die Zeilennummern am Anfang
                    if stripped_line and stripped_line[0].isdigit() and (' ' in stripped_line or '\t' in stripped_line):
                        parts = stripped_line.split(' ', 1)
                        if len(parts) > 1 and parts[0].isdigit():
                            cleaned_source_lines.append(parts[1])
                        else: # Falls keine Zahl als erster Teil, Originalzeile beibehalten
                            cleaned_source_lines.append(line)
                    else:
                        cleaned_source_lines.append(line)
                
                text_content = '\n'.join(cleaned_source_lines)
                
                # Zusätzliche Bereinigung von leeren Zeilen nach #ifdef/#endif Blöcken, etc.
                text_content = '\n'.join(filter(None, text_content.splitlines())).strip()

            # --- ENDE DER TEXTBEREINIGUNG ---


            # Mindestlängenprüfung und Speichern des Segments
            if len(text_content) < MIN_CONTENT_LENGTH:
                logger.warning(f"Inhalt von {current_url} ist zu kurz ({len(text_content)} Zeichen) oder leer nach Bereinigung. Nicht gespeichert.")
                visited_urls.add(current_url) 
                continue 
            
            # --- Hier kommt der Aufbau von data_segment und das Speichern in die JSONL-Datei ---
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
        
        # ... (Rest des Codes - Link-Discovery und Error-Hanndling) ...
        # === Link-Discovery (IMMER ausführen nach erfolgreichem Download & Parse) ===
        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(current_url, href)

            # Parse die URL, um Domain und Erweiterung zu prüfen
            parsed_full_url = urlparse(full_url)
            full_url_domain = parsed_full_url.netloc
            path_without_query_fragment = parsed_full_url.path
            _, file_extension = os.path.splitext(path_without_query_fragment)
            file_extension = file_extension.lower()
            
            # Spezielle Behandlung für Kconfig-Dateien ohne typische Dateierweiterung
            if not file_extension and '.' not in os.path.basename(path_without_query_fragment): 
                if 'kconfig' in os.path.basename(path_without_query_fragment).lower():
                    file_extension = 'kconfig' 

            # Prüfen, ob es ein Link zu unserer Zephyr-Doku ist
            is_zephyr_doc_link = (full_url_domain == urlparse(base_url).netloc and full_url.startswith(base_url))
            
            # Prüfen, ob es ein Link zu GitHub ist (und relevant)
            is_github_link = False
            if full_url_domain in GITHUB_DOMAINS:
                # Prüfe auf relevante Dateiendungen oder spezielle Dateinamen (wie 'Kconfig')
                if file_extension in GITHUB_FILE_EXTENSIONS or \
                   (not file_extension and 'kconfig' in os.path.basename(path_without_query_fragment).lower()):
                    is_github_link = True

            # Externe Links, die nicht GitHub sind, und intern ignorierte Dateierweiterungen oder Anker
            if file_extension in IGNORED_EXTENSIONS or "#" in full_url:
                continue # Dies ignoriert bekannte unerwünschte Formate und Ankerlinks

            # Logik zum Hinzufügen zu urls_to_visit ODER collected_github_links
            if is_zephyr_doc_link:
                # Nur hinzufügen, wenn die URL NOCH NICHT in visited_urls ist UND noch nicht in urls_to_visit ist
                if full_url not in visited_urls and full_url not in urls_to_visit: 
                    if rp.can_fetch(HEADERS['User-Agent'], full_url): 
                        urls_to_visit.append(full_url)
                    else:
                        logger.info(f"Link {full_url} (Zephyr-Doku) wird aufgrund von robots.txt-Regeln nicht gecrawlt.")
            elif is_github_link:
                # Nur hinzufügen, wenn der Link noch nicht gesammelt wurde
                if full_url not in collected_github_links:
                    github_data_segment = {
                        "url": full_url,
                        "source_page": current_url, # Woher der Link kommt
                        "timestamp_collected": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "file_extension": file_extension # Dateierweiterung zur späteren Verarbeitung
                    }
                    with open(github_links_output_file, 'a', encoding='utf-8') as f_github_links:
                        f_github_links.write(json.dumps(github_data_segment, ensure_ascii=False) + '\n')
                    collected_github_links.add(full_url)
                    logger.info(f"GitHub-Link gesammelt: {full_url} (von {current_url})")
            else:
                # Alle anderen externen Links werden geloggt (später vielleicht aus, um das Log sauber zu halten)
                logger.debug(f"Ignoriere externen Link (nicht Zephyr, nicht GitHub): {full_url}")


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
print(f"Gesammelte GitHub-Links: {len(collected_github_links)}. Details in {os.path.basename(github_links_output_file)}")