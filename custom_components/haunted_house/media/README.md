# Médias inclus

Ces fichiers sont servis par l’intégration à l’adresse `http://ADRESSE_HA:8123/haunted_house_media/NOM_DU_FICHIER`. Aucune copie dans `/config/www` n’est nécessaire.

Les sons sont joués automatiquement quand une banque audio est vide. Les vidéos sont à ajouter explicitement dans les champs vidéo.

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
