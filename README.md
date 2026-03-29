# TI IWR6843ISK Radar Tools

Zur Visualisierung von Heatmap-Daten des TI IWR6843ISK Radarsensors `heatmap.py`  
und der Versuch statische Objekte zu erkennen `staticObj.py`

## Voraussetzungen

* TI IWR6843ISK
* für den betrieb unter Windows und auch den mmWave Demo Visualizer  
wird der XDS110 treiber gebraucht  

## Dateien

1.  **`heatmap.py` (Web-Dashboard)**
    * Startet einen Flask-Webserver.
    * Sendet die Konfiguration an das Radar.
    * Zeigt eine **Live-Heatmap** (Entfernung vs. Winkel) im Browser an.
    * Zugriff über: `<IP-ADRESSE>:5000`

2.  **`staticObj.py`**
    * Liest Radar-Daten ohne GUI.
    * Zeigt erkannte (statische) Objekte und Distanzen direkt im Terminal (ASCII-Art).
    * Loggt alle erfassten Objekte (mit Zeitstempel, Winkel, Distanz und Signalstärke) fortlaufend in einer CSV-Datei

3.  **`profile.cfg` (Konfiguration)**
    * Steuert die Physik des Sensors.
    * **Werte:** Slope 70 MHz/us, 256 Samples.
    * **Leistung:** Max Reichweite ca. 12.8m, Auflösung ca. 5cm.
    * **Modus:** Nur Heatmap aktiviert (Punktwolke aus).
##
![Demo](https://cdn.7tv.app/emote/01F6MQ33FG000FFJ97ZB8MWV52/4x.gif) 
