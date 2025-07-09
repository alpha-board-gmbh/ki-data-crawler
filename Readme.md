# Zephyr LLM Projekt
Dieses Repository enthält alle Skripte, Daten und Konfigurationen für das Fine-Tuning eines Large Language Models (LLM) auf der Basis von Zephyr OS. Das Ziel ist es, ein spezialisiertes LLM zu entwickeln, das bei Programmier- und Hardware-Design-Aufgaben im Kontext von Zephyr OS unterstützen kann. Dies hier ist der Ordner, wo ein Crawler in Python die Datenbasis zusammensuchen soll.

Wir lesen der Reihe nach ein:

- Zephyr Dokumentation
- Zephyr OS repo
- Zephyr SDK und Modul-Repositorien
- Github-Projekte in Open Source Software
- Guthub-Projekte in Open Source Hardware
- Mailinglisten und Foren, falls wir welche finden

## 1. Projektstruktur
Die Struktur des Projekts ist wie folgt organisiert:

ki_data_collector/  
├── .git/                         # Versteckter Ordner: Von Git verwaltete Versionskontrolle  
├── README.md                     # Diese Datei: Projektbeschreibung und Anleitung  
├── setup_project.sh              # Skript zum initialen Setup der Umgebung und Installation von Bibliotheken  
├── requirements.txt              # Liste der benötigten Python-Bibliotheken  
├── data/  
│   ├── raw_data/                 # Hier landen alle direkt gesammelten Rohdaten (unverändert)  
│   │   ├── web_crawls/           #   - Rohe HTML-Dateien aus Web-Crawls (optional, z.B. für Debugging)  
│   │   ├── repo_clones/          #   - Geklonte Code-Repositories (z.B. Git-Repos)  
│   │   └── other_raw/            #   - Für sonstige Rohdaten (z.B. APIs, PDFs, etc.)  
│   └── processed_data/           # Hier landen alle bereinigten und vorformatierten Daten  
│       ├── [PROJECT_NAME]_docs_segments.jsonl #   - Beispiel: zephyr_docs_segments.jsonl (bereinigte Doku-Segmente)  
│       ├── [PROJECT_NAME]_docs_unreachable_urls.jsonl # - Beispiel: zephyr_docs_unreachable_urls.jsonl (URLs, die nicht erreicht werden konnten)  
│       └── [PROJECT_NAME]_repo_segments.jsonl #   - Beispiel: zephyr_repo_segments.jsonl (Code-Repository-Segmente)  
├── scripts/  
│   ├── crawler/                  # Skripte zum Sammeln der Rohdaten (z.B. Web-Crawler, GitHub-API-Scraper)  
│   │   └── web_crawler.py        #   - Allgemeiner Web-Crawler (unser Haupt-Crawler-Skript)  
│   └── parser/                   # Skripte zur Verarbeitung und Normalisierung der Rohdaten  
│       └── repo_parser.py        #   - Allgemeiner Code-Repository Parser (noch zu erstellen)  
├── logs/                         # Hier werden Log-Dateien der Skripte gespeichert  
│   └── [PROJECT_NAME]_crawler_output.log # - Beispiel: zephyr_crawler_output.log  
└── venv-crawl/                   # Virtuelle Python-Umgebung für dieses Projekt  

*(Hinweis: `[PROJECT_NAME]` ist ein Platzhalter, der im Skript durch den tatsächlichen Projektnamen ersetzt wird, z.B. "zephyr". Versteckte Dateien und Ordner (wie `.git/`) beginnen mit einem Punkt.)*

## 2. Erste Schritte und Einrichtung
Die Installation des Projekts erfolgt idealerweise über Git.

### Projekt klonen und initiales Setup

1.  **Klonen Sie das Repository:**
    Navigieren Sie zum gewünschten Speicherort auf Ihrem System und klonen Sie das Git-Repository. Ersetzen Sie `YOUR_GITHUB_REPO_URL` durch die tatsächliche URL Ihres GitHub-Repositorys (z.B. `https://github.com/alpha-board-org/ki_data_collector.git`).

    ```bash
    git clone YOUR_GITHUB_REPO_URL ki_data_collector 
    cd ki_data_collector
    ```

    *(Hinweis: Der Ordner `ki_data_collector` wird durch den `git clone`-Befehl erstellt und enthält bereits die gesamte Ordnerstruktur.)*

2.  **Initiales Setup ausführen:**
    Führen Sie das `setup_project.sh`-Skript aus, um die virtuelle Umgebung zu erstellen und die notwendigen Python-Bibliotheken zu installieren.
    
    ```bash
    ./setup_project.sh
    ```

## 3. VENV verwenden und Bibliotheken installieren

### VENV einrichten
Das `setup_project.sh`-Skript kümmert sich bereits um die Erstellung und erste Aktivierung der virtuellen Umgebung (`venv-crawl`) sowie die Installation der grundlegenden Bibliotheken aus `requirements.txt`.

Nachdem das `setup_project.sh`-Skript durchgelaufen ist, ist die `venv-crawl` im aktuellen Terminal aktiv. Wenn Sie ein neues Terminalfenster öffnen, müssen Sie die virtuelle Umgebung dort erneut aktivieren:

```bash
source venv-crawl/bin/activate # Aktiviert die virtuelle Umgebung
```

### Wie erkenne ich, ob das Venv aktiv ist?
Nach der Aktivierung sollte der Name Ihrer virtuellen Umgebung (hier: (venv-crawl)) in Ihrer Terminal-Eingabeaufforderung erscheinen, z.B.:

> (venv-crawl) DeinBenutzer@DeinRechner ki_data_collector %

Sie können dies auch mit den folgenden Befehlen überprüfen:

```which python```: Zeigt den Pfad zum Python-Interpreter innerhalb des aktiven Venvs an.

```echo $VIRTUAL_ENV```: Gibt den Pfad zum Venv-Stammverzeichnis aus, wenn aktiv.

## 4. Crawler-Skript für Zephyr-Dokumentation
Der Web-Crawler, der für die Zephyr-Dokumentation verwendet wird, befindet sich nun unter scripts/crawler/web_crawler.py. Der Crawler sucht in dieser Version nur nach Text, nicht nach Bildern etc. (das liegt daran, dass wir derzeit nur ein Textmodell fine-tunen wollen, kein Modell für Text und Bild). In späteren Versionen sammeln wir vielleicht auch alle Bilder mit ein.

### Crawler-Skript anpassen
Öffnen Sie die Datei `scripts/crawler/web_crawler.py`.

* **Legen Sie den Projektnamen fest:**
    Ändern Sie die Variable `PROJECT_NAME` am Anfang des Skripts auf den Namen Ihres aktuellen Projekts, z.B. `"zephyr-docs"`:
    ```python
    PROJECT_NAME = "zephyr-docs"
    ```

* **Legen Sie die Basis-URL fest:**
    Stellen Sie sicher, dass die `base_url` auf die Start-URL der Dokumentation zeigt, die Sie crawlen möchten, z.B. die [Dokumentation von Zephyr OS](https://docs.zephyrproject.org/):
    ```python
    base_url = "https://docs.zephyrproject.org/"
    ```

* **Prüfen und Anpassen der HTML-Selektoren für den Hauptinhalt:**
    Dies ist ein kritischer Schritt, um sicherzustellen, dass der Crawler nur den relevanten Textinhalt einer Webseite extrahiert und keine Navigationselemente, Footer oder Header. Die aktuellen Selektoren sind für die Zephyr-Dokumentation optimiert. Für andere Webseiten müssen Sie diese möglicherweise anpassen.

    **So finden Sie die richtigen Selektoren:**
    1.  Öffnen Sie die Webseite, die Sie crawlen möchten, in Ihrem Webbrowser (z.B. `https://docs.zephyrproject.org/`).
    2.  Navigieren Sie zu einer typischen Inhaltsseite (z.B. ein Artikel, ein Tutorial).
    3.  **Rechtsklicken** Sie auf den **Haupttextbereich** der Seite (nicht auf Navigation, Header, Footer etc.).
    4.  Wählen Sie im Kontextmenü des Browsers "Untersuchen" (oder "Inspect Element" / "Element untersuchen"). Die Entwicklertools Ihres Browsers öffnen sich.
    5.  Im HTML-Code-Fenster der Entwicklertools:
        * Navigieren Sie im Baum nach oben (`Parent-Elemente`) und nach unten (`Kind-Elemente`), bis Sie ein `<div>`, `<article>`, `<section>` oder ein ähnliches HTML-Tag finden, das den **gesamten Hauptinhalt** des Artikels umschließt, aber **nichts Unnötiges** (wie Seitenleisten, Navigation, Footer, Header, Kommentare, Social-Media-Buttons).
        * Achten Sie auf eindeutige **Attribute** dieses Tags, wie `id="main-content"`, `class="article-body"`, `itemprop="articleBody"`, `role="main"`, oder eine Kombination davon.
    6.  Passen Sie die `soup.find()`-Befehle im Skript entsprechend an. Der Crawler versucht aktuell zuerst `itemprop="articleBody"` und dann einen Selektor mit `role="main"` und `class_="document"`:
        ```python
        # Beispiel: Anpassen der Hauptinhalts-Selektoren im Skript
        main_content_div = soup.find('div', itemprop="articleBody")
        if not main_content_div:
            main_content_div = soup.find('div', role="main", class_="document")
        # Falls die Webseite z.B. einen Hauptinhalt mit id="content" hat, würden Sie hinzufügen:
        # if not main_content_div:
        #    main_content_div = soup.find('div', id='content')
        ```

* **Prüfen und Anpassen der zu ignorierenden Dateierweiterungen (`IGNORED_EXTENSIONS`):**
    Die Liste enthält gängige Bild-, Archiv- und Skriptformate. Wenn die Ziel-Webseite andere Dateitypen verlinkt, die Sie nicht in Ihrem Text-Datensatz haben möchten (z.B. `.mp4` für Videos, `.exe` für ausführbare Dateien), fügen Sie diese der Liste hinzu.

### 4.2. Crawler ausführen

Stellen Sie sicher, dass Ihre `venv-crawl` aktiv ist (`source venv-crawl/bin/activate`).

Führen Sie das Skript vom **Hauptverzeichnis Ihres Projekts** (z.B. `ki_data_collector/`) aus:

```bash
python scripts/crawler/web_crawler.py
```

Dieser Befehl startet den Crawling-Prozess. Die gesammelten Daten werden in der Datei data/processed_data/[PROJECT_NAME]_docs_segments.jsonl gespeichert (z.B. data/processed_data/zephyr_docs_segments.jsonl). Log-Meldungen finden Sie in logs/[PROJECT_NAME]_crawler_output.log. URLs, die nicht dauerhaft erreicht werden konnten, werden in data/processed_data/[PROJECT_NAME]_docs_unreachable_urls.jsonl protokolliert.

## 5. Nächste Schritte

* Qualitätskontrolle der gesammelten Daten: Überprüfen Sie nach Abschluss des Crawls die erzeugte JSONL-Datei (data/processed_data/[PROJECT_NAME]_docs_segments.jsonl) auf die Qualität des Inhalts. Achten Sie darauf, dass der Text sauber, lesbar und relevant ist und keine unnötigen HTML-Elemente oder Navigationsteile enthält.
* Weitere Datenquellen sammeln: Nachdem die Dokumentationsdaten erfolgreich gesammelt wurden, können Sie weitere Datenquellen integrieren. Dies umfasst typischerweise:
    * Zephyr OS Quellcode: Verwendung des scripts/parser/repo_parser.py-Skripts (noch zu erstellen), um Code-Repositories zu parsen.
    * Zephyr SDK und Modul-Repositories: Ähnlich wie der OS Quellcode.
    * GitHub-Projekte (Open Source Software & Hardware): Erfordert möglicherweise angepasste Crawler, die GitHub-APIs nutzen, um Code, Issues und Diskussionen zu sammeln.
    * Mailinglisten und Foren: Benötigt spezifische Scraper für jede Plattform, um Frage-Antwort-Paare und Diskussionen zu extrahieren.
* Datenkombination und Vorbereitung für LLM Fine-Tuning: Sobald Sie Daten aus verschiedenen Quellen gesammelt haben, müssen diese weiter bereinigt, normalisiert und in ein konsistentes Format gebracht werden, das für das Instruction Fine-Tuning von LLMs geeignet ist. Dies könnte das Zusammenführen mehrerer JSONL-Dateien, das Filtern nach Relevanz und das Formatieren in ein "Question-Answering" oder "Instruction-Response"-Schema umfassen.
