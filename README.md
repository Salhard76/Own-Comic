# Fumetti in uscita

Web app (PWA) per tenere l'elenco dei fumetti Bonelli e Panini, con uscite, avvisi e flag "acquistato".

## Messa online
1. Crea un repository su GitHub e carica tutti questi file, mantenendo le cartelle (comprese `.github`, `scripts` e `data`).
2. Settings > Pages > Deploy from branch > `main` / root.
3. Apri `https://tuonome.github.io/nome-repo/` da Chrome e scegli "Aggiungi a schermata Home".

## Catalogo delle uscite
1. Scrivi i tuoi titoli in `scripts/lista.txt` (una riga per titolo: `Titolo | bonelli oppure panini | numero di partenza`).
2. Actions > "Aggiorna catalogo" > Run workflow. Parte da solo anche due volte al giorno.
3. Nel log trovi, per ogni fonte, quante voci ha letto e l'intervallo di date. Se una fonte ne trova 0, il file `data/debug-...txt` contiene l'inizio della pagina letta.

## Avvisi sul telefono anche ad app chiusa
1. Installa l'app ntfy (versione Play Store) e iscriviti a un nome di canale lungo e difficile da indovinare.
2. Repository > Settings > Secrets and variables > Actions > nuovo secret `NTFY_TOPIC` con quel nome.
3. Nell'app: Impostazioni > Sincronizzazione GitHub (repository `utente/nome` e token con permesso Contents solo su questo repository) > "Salva su GitHub".
4. Ogni mattina `Avvisi fumetti` legge `data/fumetti.json` e ti manda l'avviso.

## File
- `index.html`, `sw.js`, `manifest.webmanifest`, `icon*.png/svg`: l'app.
- `data/catalogo.json`: catalogo generato dallo script (all'inizio vuoto).
- `scripts/catalogo.py`, `scripts/lista.txt`, `.github/workflows/catalogo.yml`: lettura di Bonelli e Panini.
- `scripts/notify.py`, `.github/workflows/notify.yml`: avvisi push con ntfy.
