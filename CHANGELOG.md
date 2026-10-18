# Historique

## 0.4.2 — 18 octobre 2026

- Correction : l'appareil de chaque zone est rattaché à l'appareil principal avec `via_device_id` (le paramètre `via_device` est déprécié dans Home Assistant et disparaîtra en 2027.8).

## 0.4.1 — 18 octobre 2026

- Option **Remettre les lumières normales entre deux scènes** (activée par défaut) : les lampes de la zone reviennent à leur état d'avant le spectacle à la fin de chaque scène.

## 0.4.0 — 18 octobre 2026

- **Terreur** : lumières qui scintillent et grésillent de façon irrégulière (chaque lampe sa séquence, 3 changements par seconde au plus), coupures noires, éclairs d'orage en rafale, flashs rouges.
- Scènes réécrites avec montée, noir total puis choc : Bougies, Cimetière, Orage, Apparition, Maison hantée, Sons spatialisés, Poursuite, Rire. Toutes jouent maintenant un son.
- Nouveaux sons sombres : cris, grondements, craquement de porte, tonnerre grave, pas lourds, coups, chuchotements, rire, drone, souffle de fantôme, ambiance (synthèse originale et sources CC0 créditées).
- Quatre vidéos effrayantes originales (visage dans le couloir, caméra de surveillance infrarouge, neige TV, apparition) jouées dès qu'une TV est choisie dans la zone. Cause du « aucune vidéo » : le champ d'URL était vide.
- Le profil **Maison hantée** est effrayant dès la première seconde (plus de montée calme). Les profils Familiale n'ont ni cris ni grondements.
- **Plus aucune URL à saisir** : seuls les sons et vidéos fournis sont utilisés. Les anciens champs sont ignorés.
- **Un appareil par zone** (« Haunted House NOM ») avec capteur, liste de scène de test et boutons ; les commandes globales restent sur l'appareil principal.

## 0.3.4 — 18 octobre 2026

- Les volets ignorés ou non déplacés sont maintenant expliqués dans le journal (`cover_ignored`, `cover_skipped` avec la raison : classe, positionnement non pris en charge, position inconnue, délai).
- Un test ignore le délai de démarrage des volets, pour pouvoir les essayer immédiatement.

## 0.3.3 — 18 octobre 2026

- Liste **Scène de test** par zone sur la page de l'appareil : choisir une scène puis utiliser les boutons Aperçu/Tester, sans passer par Configurer.
- Le modèle affiché de l'appareil suit la version du manifest.

## 0.3.2 — 18 octobre 2026

- Correction : les attributs sans valeur (`effect`, `volume_level`, `source` à `None`) ne sont plus enregistrés ni renvoyés à la restauration. Ils faisaient échouer la restauration à chaque fois et bloquaient les tests (« Arrêtez la session et terminez la restauration »).
- Nouveau bouton **Abandonner la restauration** pour débloquer un appareil qui ne peut pas être restauré.

## 0.3.1 — 18 octobre 2026

- Sons et vidéos servis par l’intégration (`/haunted_house_media/`) : plus de copie manuelle dans `www`.
- Une banque audio vide utilise le son inclus correspondant ; la voix TTS reste prioritaire en mode enfants.
- Icône de l’intégration (requise par la validation HACS).
- Validation hassfest et HACS automatique sur GitHub.

## 0.3.0 — 17 octobre 2026

- Parcours du fantôme entre pièces avec son et lumière séquencés.
- Progression calme, montée et finale, dans les limites des profils et scènes autorisés.
- Profils locaux et mode enfants par zone, banques audio/vidéo séparées et voix TTS facultative.
- Réactions aux extinctions des lampes explicitement autorisées.
- Embranchements de poursuite et de départ pilotés par les capteurs.
- Scène de sons spatialisés et banques audio par scène/effet.
- Lecteurs vidéo, allumage facultatif et tentative de restauration de source/alimentation.
- Aperçu, test isolé avec restauration, boutons de test et parcours de test dans les options.
- Journal persistant de 200 événements, capteurs et actions de consultation.
- Sept sons synthétiques et trois vidéos de démonstration originales inclus.
- Migration automatique v1/v2 et conservation des récupérations.
- 42 tests avec doubles des APIs HA ; pas d’exécution réelle de HA.

## 0.2.0 — 17 octobre 2026

- Zones nommées avec appareils, sons, scènes et déclencheurs propres.
- Éditeur d’options : ajouter, modifier, supprimer et enregistrer les zones.
- Migration automatique du modèle de configuration v1 vers une zone Maison.
- Cinq scènes avec séquences et branches parallèles : bougies, cimetière, orage, apparition, maison hantée.
- Profils familiale, inquiétante et maison hantée avec plafonds de volume/luminosité et amplitude des volets.
- Écoute directe des capteurs binaires, boutons helpers et entités événement.
- Délais de déclenchement et de mouvement de volet indépendants par zone.
- Interruption prioritaire d’une seule zone par une surprise ; arrêt et annulation suivis de toutes les branches.
- Boutons de surprise par zone et action play_scene avec choix de zone et de scène.
- Récupération persistante et reprise après échec de restauration conservées.
- Vingt tests de comportement ; exécution réelle sous HA restant à valider.

## 0.1.0

- Premier prototype à sélection globale d’appareils, effets aléatoires et restauration.
