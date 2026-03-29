import pandas as pd
import matplotlib.pyplot as plt


def main():
    try:
        print("Lese data.csv ein (nur Distanz)...")
        # Wir lesen nur die Spalte 'Distance_m'
        # Falls deine Spalten anders heißen, passe 'usecols' an oder entferne es.
        df = pd.read_csv('radar_log_2026-01-22_12-54-13.csv', sep=';', usecols=['Distance_m'])

        # Optional: Daten etwas glätten
        df['Distance_Smoothed'] = df['Distance_m'].rolling(window=10, center=True).mean()

        x_werte = df.index * 10

        # Plot erstellen
        plt.figure(figsize=(10, 6))

        plt.plot(x_werte, df['Distance_m'], label='Rohdaten', color='lightgray', alpha=0.5)
        plt.plot(x_werte, df['Distance_Smoothed'], label='Geglättet', color='orange', linewidth=2)

        # Titel setzen
        plt.suptitle('Radar Bild einer linearen Bewegung', fontsize=16, fontweight='bold')
        plt.title('Bewegung über: Boden -> Stuhl -> Tisch -> Bildschirm -> Boden')

        plt.ylabel('Distanz [m]')
        plt.xlabel('Zeit [ms]')
        plt.grid(True)
        plt.legend()

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])

        dateiname = 'distanz_plot_index.png'
        plt.savefig(dateiname)
        print(f"Erfolg! Der Plot wurde als '{dateiname}' gespeichert.")

        # plt.show()

    except FileNotFoundError:
        print("Fehler: Datei nicht gefunden.")
    except Exception as e:
        print(f"Ein Fehler ist aufgetreten: {e}")


if __name__ == "__main__":
    main()