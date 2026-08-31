# WG Finanztracker

## Voraussetzungen

* Python 3.14+
* Docker und Docker Compose
* [Tesseract OCR](https://tesseract-ocr.github.io/tessdoc/)

## Installation

Repository klonen und die Python-Abhängigkeiten installieren:

```bash
pip install .
```

## Datenbank starten

Die PostgreSQL-Datenbank wird über Docker Compose gestartet:

```bash
docker compose up -d
```

## Anwendung starten

```bash
flask --app wg_finanztracker.web.app run
```

Anschließend ist die Anwendung unter `http://127.0.0.1:5000` erreichbar.

Zum Beenden der Datenbank:

```bash
docker compose down
```
