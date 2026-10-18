# Médias de démonstration

Copier ce dossier dans `/config/www/haunted_house/`. Il devient accessible via :
`http://ADRESSE_HA:8123/local/haunted_house/NOM_DU_FICHIER`.

| Fichier | Usage |
|---|---|
| thunder.wav | Banque Orage |
| footsteps.wav | Banque Pas |
| knock.wav | Banque Coups |
| whisper.wav | Banque Chuchotements / souffle : souffle synthétique, aucune parole |
| laugh.wav | Banque Rire : effet électronique pulsé, aucune parole |
| drone.wav | Ambiance générale inquiétante |
| kids.wav | Banque Enfants : carillon doux |
| apparition.mp4 | Silhouette de fantôme sur fond noir |
| surveillance.mp4 | Faux écran de surveillance avec apparition ; aucune caméra réelle |
| kids.mp4 | Citrouille animée |

Sons : 2 secondes, WAV PCM mono 22 050 Hz. Vidéos : 6 secondes, H.264 MP4 640×360 à 12 images/seconde, sans piste audio. Les lecteurs doivent accepter ces formats et pouvoir joindre l’URL. Tous les contenus sont des créations procédurales originales distribuées sous la licence MIT du projet.

Le script `scripts/generate_assets.py` permet de les recréer avec Python, Pillow et ffmpeg sur une machine de développement. Ces dépendances ne sont pas nécessaires pour exécuter l’intégration.
