# Haunted House v3 👻 — Home Assistant

[![Validate](https://github.com/rafal83/haunted-house/actions/workflows/validate.yml/badge.svg)](https://github.com/rafal83/haunted-house/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

**Version 0.4.0.** Une ambiance hantée locale avec des scènes par pièce, un fantôme qui se déplace, des réactions aux personnes, une progression narrative, des sons et vidéos, et un mode enfants.

**Statut : prototype. Les 47 tests de comportement et de séquencement utilisent des doubles des APIs HA ; hassfest et la validation HACS passent sur GitHub. Le chargement dans un vrai Home Assistant, les sélecteurs du frontend et les appareils physiques restent à valider.** Cible : Home Assistant Core 2025.12 ou ultérieur.

## Installation et mise à jour

### Via HACS (recommandé)

1. HACS → menu ⋮ → **Dépôts personnalisés**.
2. Ajouter `https://github.com/rafal83/haunted-house` avec le type **Intégration**.
3. Chercher **Haunted House**, **Télécharger**, puis redémarrer Home Assistant.
4. Les sons sont inclus dans l’intégration : rien d’autre à copier (voir « TV, projecteur et médias inclus »).

### Manuellement

1. Si une ancienne version est installée, arrêter le mode hanté puis utiliser **Arrêter et restaurer**. Terminer toute récupération en attente.
2. Copier ou remplacer le dossier `custom_components/haunted_house` dans `/config/custom_components/haunted_house`. Garder la configuration et les données `.storage`.
3. Redémarrer Home Assistant.
4. Nouvelle installation : **Paramètres → Appareils et services → Ajouter une intégration → Haunted House**. Mise à jour : ouvrir l’intégration existante.

La configuration v1 est convertie en une zone **Maison**. Les zones et réglages v2 sont conservés. Les nouveaux champs sont ajoutés avec leurs valeurs par défaut : progression activée, parcours automatique désactivé, lampes réactives et vidéos non sélectionnées. Les commandes globales conservent leurs identifiants. Les sauvegardes de récupération des anciennes versions restent lisibles.

Le paquet s’installe via HACS (dépôt personnalisé) ou manuellement. Il n’est pas dans le catalogue HACS par défaut. Avec HACS, les mises à jour apparaissent à chaque nouvelle release GitHub ; redémarrer HA après la mise à jour.

## Démarrage rapide

1. Créer une zone avec une ou deux lampes, puis ajouter une enceinte.
2. Dans le second formulaire, indiquer seulement si les TV/projecteurs peuvent être allumés. Les sons et vidéos sont fournis par l’intégration : aucune URL à saisir.
3. Depuis **Configurer → Prévisualiser et tester une scène**, sélectionner cette zone et **Orage**. Vérifier l’aperçu puis lancer le test. Il s’arrête après 20 secondes maximum et restaure les états.
4. Ajouter les autres pièces, puis définir **Histoire et parcours**.
5. Activer **Mode hanté**. Utiliser le bouton **Faire circuler le fantôme** pour lancer un parcours immédiatement.

Les enceintes et TV doivent pouvoir joindre l’URL interne de Home Assistant (**Paramètres → Système → Réseau**), car les médias sont servis par l’intégration. Aucun appareil n’est sélectionné automatiquement.

## Les ajouts de la v3

| Fonction | Comportement |
|---|---|
| Fantôme itinérant | Parcours ordonné des zones : lumière et pas au début, souffle dans les pièces intermédiaires, coups dans la dernière |
| Montée de tension | Début calme, manifestations plus présentes, finale dans le dernier cinquième de la session |
| Maison qui répond | Une lampe autorisée, éteinte pendant le spectacle, se rallume doucement après environ deux secondes |
| Sons spatialisés | Pas, souffle et coups joués successivement sur les enceintes de la zone |
| TV/projecteur | Lecture d’une apparition ou d’un faux écran de surveillance sur un lecteur vidéo compatible HA |
| Embranchements | Poursuite si une détection arrive dans la pièce suivante ; réaction après un départ sans nouvelle détection |
| Mode enfants | Profil et médias propres à chaque zone, couleurs douces, carillon ou phrases TTS, aucun mouvement de volet |
| Sons et vidéos inclus | Cris, grondements, craquements, tonnerre et vidéos effrayantes fournis par l’intégration, sans URL à renseigner |
| Aperçu et test | Liste des appareils, test isolé d’une seule zone et restauration automatique |
| Historique | 200 événements conservés : heures, zones, scènes, déclencheurs, interruptions et échecs d’appareils |

## Configuration des zones

Une zone est un groupe logique nommé librement : Entrée, Salon, Jardin… Vous sélectionnez explicitement ses entités ; ce n’est pas une importation automatique des pièces HA.

Le premier formulaire définit :

- lumières ; volets/rideaux ; enceintes ; prises de décoration ; TV/projecteurs ;
- déclencheurs : `binary_sensor`, `input_button` ou entité `event` ;
- scènes automatiques autorisées et scène sur déclenchement ;
- profil local ou héritage du profil général ; mode enfants ;
- lampes réactives, choisies parmi les lumières de cette zone ;
- activation des embranchements, pièce suivante et pièce de réponse après départ ;

Le second formulaire demande seulement si les TV/projecteurs de la zone peuvent être allumés. Les sons et vidéos ne se configurent pas : l’intégration joue les siens.

Chaque zone devient un **appareil** Home Assistant distinct (« Haunted House NOM ») avec son capteur, sa liste de scène de test et ses boutons Surprise, Aperçu et Tester. Les commandes globales (mode hanté, arrêter et restaurer, fantôme, abandonner la restauration) restent sur l’appareil principal « Haunted House ».

Dans les options, **Ajouter/Modifier/Supprimer une zone**, **Réglages généraux**, **Histoire et parcours** préparent les changements. Choisir **Enregistrer** pour les appliquer. Une session active sera arrêtée et restaurée avant rechargement. Les tests utilisent la configuration enregistrée, pas un brouillon d’options.

Un même identifiant piloté ne peut figurer dans deux zones, ni être à la fois enceinte et lecteur vidéo. Les groupes HA et leurs membres ne doivent pas être sélectionnés ensemble : leurs recouvrements physiques ne sont pas détectés. Une enceinte déjà groupée peut diffuser au-delà de la zone choisie.

## Catalogue de scènes

| Scène | Identifiant | Effets |
|---|---|---|
| Bougies | `candle` | Flammes orange qui vacillent, extinction brusque, braise rouge, craquement ou souffle |
| Cimetière | `graveyard` | Vert maladif qui grésille, souffle, noir total puis éclair blanc |
| Orage | `storm` | Éclairs blancs en rafale (jusqu’à trois), coupure, tonnerre grave |
| Apparition | `apparition` | Violet qui grésille, chuchotements, noir, flash rouge, cri, volet, accessoire et vidéo |
| Maison hantée | `haunted` | Lumières rouges qui scintillent, grondement, noir total, flash rouge et cri, accessoire et vidéo |
| Sons spatialisés | `spatial` | Pas, souffle puis coups sur des enceintes successives, lumière qui vacille |
| Citrouille magique | `kids` | Orange et rose doux, carillon, vidéo de citrouille et éventuellement TTS |
| Poursuite | `pursuit` | Lumière verte qui grésille, pas, coups, noir puis retour violet |
| Rire derrière vous | `retreat` | Rouge qui scintille et rire |

Les branches son, vidéo, accessoire et lumière sont coordonnées au niveau logiciel. Les latences propres aux appareils empêchent une synchronisation audiovisuelle à la milliseconde. Aucun stroboscope n’est utilisé : le scintillement est irrégulier, chaque lampe suit sa propre séquence et ne change jamais plus d’environ trois fois par seconde.

Les scènes se dégradent selon le matériel présent : une scène lumineuse fonctionne sans enceinte, une apparition sans volet garde ses autres effets.

## Profils par pièce et enfants

| Profil | Valeur | Plafond lumière | Plafond volume | Pas de volet | Peur |
|---|---|---:|---:|---:|---|
| Familiale | `family` | 90 / 255 | 20 % | ±5 points | Scintillements et coupures légers, souffles, craquements, aucun cri |
| Inquiétante | `eerie` | 150 / 255 | 35 % | ±10 points | Cris, grondements, flashs rouges |
| Maison hantée | `haunted` | 210 / 255 | 50 % | ±15 points | Tout, dès la première seconde (pas de montée calme) |
| Enfants | `kids` | 65 / 255 | 12 % | Aucun | Aucune |

**Pour avoir vraiment peur** : choisir le profil **Maison hantée** dans **Réglages généraux** et monter le **volume** (le volume envoyé est plafonné à la valeur la plus basse entre ce réglage et le profil ; 0,5 ou plus pour Maison hantée). Les profils Familiale et Inquiétante gardent la montée calme du début de session.

Le volume envoyé est le minimum entre votre réglage et le plafond effectif du profil. Le mode enfants d’une zone transforme ses scènes, parcours et embranchements en scène douce. Il utilise **uniquement** le carillon et la vidéo de citrouille inclus ; jamais les cris ni les vidéos effrayantes.

Pour les voix, renseigner une entité TTS existante dans **Histoire et parcours**, par exemple `tts.piper`, puis une phrase par ligne. Quand elle est configurée, cette entité lit une phrase aléatoire à la place du carillon. La voix et la disponibilité réseau dépendent de votre moteur TTS ; l’intégration ne crée pas elle-même une voix. Les phrases par défaut sont douces et modifiables.

## Histoire, rythme et finale

La progression, désactivable, suit le temps de la session :

- **Calme**, premiers 40 % : plafond lumière et volume multiplié par 0,45, intervalle allongé ; choix de préférence parmi Bougies/Cimetière/Citrouille si autorisés.
- **Montée**, de 40 à 80 % : plafonds multipliés par 0,75 et cadence habituelle.
- **Finale**, derniers 20 % : plafonds du profil, cadence accrue et une scène finale par zone. Maison hantée si autorisée, sinon une scène de la sélection de cette zone.

Une pièce en mode enfants reste douce pendant toute la progression. La scène finale respecte les délais de surprise déjà en vigueur ; un déclenchement très récent peut donc la retarder ou l’empêcher dans cette zone.

Une zone joue une scène à la fois. Les zones sont indépendantes. Une surprise remplace la scène de sa zone ; les autres continuent. Une scène automatique ne remplace jamais une scène en cours. Les commandes d’appareils sont limitées à quatre simultanément.

Valeurs initiales : session de 30 minutes, intervalle moyen 20 secondes, surprises espacées de 20 secondes par zone, mouvements de volet espacés de 180 secondes par zone. Le rythme conserve une variation aléatoire et un intervalle minimal de 8 secondes.

## Parcours du fantôme

Dans **Histoire et parcours**, sélectionner les zones dans l’ordre voulu. Vide = ordre de la liste des zones enregistrées. Le bouton **Faire circuler le fantôme** lance le parcours pendant une session active. L’option de circulation automatique relance un parcours à l’intervalle choisi ; elle est désactivée par défaut.

Le parcours prend temporairement la main sur ses pièces et annule leurs scènes précédentes. Une détection prioritaire dans l’une de ces pièces interrompt le parcours. Un seul parcours peut être actif à la fois. Les pièces enfants jouent leur variante douce.

Le déplacement audio est une succession de lectures, pas une spatialisation multicanal ou une mesure de position des personnes. Pour un effet convaincant, prévoir des enceintes dans plusieurs pièces et renseigner les banques Pas, Souffle et Coups.

## Réactions aux personnes et embranchements

Un capteur binaire déclenche au passage **off → on**. Un helper `input_button` ou une entité `event` déclenche lorsque son horodatage change. Initialisation, états indisponibles et changements d’attributs seuls sont ignorés. Les événements de bus bruts nécessitent une automatisation HA appelant une action de l’intégration.

Pour les embranchements :

1. Activer cette fonction dans la zone de départ et choisir sa **Pièce suivante attendue**.
2. Une présence dans cette pièce pendant le délai configuré déclenche une scène **Poursuite** dans la pièce suivante.
3. Après un passage **on → off** dans la zone de départ, si aucun nouveau déclenchement n’a eu lieu et qu’aucun de ses capteurs binaires sélectionnés ne reste actif au terme du délai, une scène **Rire derrière vous** est demandée dans la pièce de réponse, ou dans la même pièce si aucune n’est choisie.

Ces règles utilisent les transitions des capteurs configurés, sans identification des personnes. Un contact de porte ne prouve pas à lui seul un départ : choisir de préférence des capteurs de présence pour ce mécanisme. Une nouvelle détection n’importe où dans le spectacle annule une branche de départ en attente.

## Lampes qui répondent

Sélectionner explicitement les **Lampes qui se rallument après extinction** dans chaque zone. Pendant la session, une transition marche → arrêt de l’une de ces lampes programme une réponse deux secondes plus tard, avec un délai minimal entre réponses.

L’intégration ignore les événements portant son propre contexte HA. Elle ne peut pas toujours distinguer une extinction manuelle d’une extinction provenant d’une autre automatisation : cette fonction réagit aux deux. Aucune lampe n’est réactive par défaut. L’arrêt du spectacle annule les réponses en attente.

## TV, projecteur et médias inclus

Aucune URL à renseigner : les sons et vidéos sont **fournis par l’intégration** et servis par Home Assistant sur `/haunted_house_media/`. L’adresse utilisée est l’URL interne de Home Assistant (**Paramètres → Système → Réseau**) ; elle doit être joignable par les enceintes et les TV. Il n’y a pas de réglage pour les remplacer.

Chaque scène choisit au hasard parmi plusieurs variantes. Les profils Familiale n’utilisent ni cris ni grondements. En mode enfants, la voix TTS configurée reste prioritaire sur le carillon inclus.

**Vidéos.** Dès qu’une TV ou un projecteur est choisi dans la zone, les scènes Apparition, Maison hantée et Citrouille jouent une de leurs vidéos environ six secondes, puis l’arrêtent. Le lecteur doit accepter `media_player.play_media` avec un contenu vidéo et pouvoir joindre l’URL. Une TV qui expose seulement marche/arrêt ou changement de source ne suffit pas. Une TV éteinte est ignorée sauf si **Autoriser l’allumage** est activé. Si elle a été allumée par le spectacle, elle est rééteinte lors de la restauration de session ; sa source initiale est aussi rappelée lorsqu’elle est connue. Une application ou une émission antérieure n’est pas reprise. Quand une vidéo n’est pas jouée, le journal contient `video_skipped` avec la raison (aucun lecteur disponible, allumage non autorisé, URL de base introuvable).

| Média | Fichiers | Origine |
|---|---|---|
| Cris | `scream`, `scream_2`, `scream_3`, `scream_4` | Synthèse originale et montages de cris de créatures CC0 |
| Grondements | `growl`, `growl_2`, `roar`, `hit_bass` | Synthèse originale et montages CC0 |
| Ambiances | `drone`, `ambience`, `breath`, `creak` | Synthèse originale, « Ambient horror » et « Ghost breath » (CC0) |
| Autres sons | `thunder`, `footsteps`, `knock`, `whisper`, `laugh` | Synthèse originale |
| Enfants | `kids.wav`, `kids.mp4` | Carillon et citrouille originaux |
| Vidéos effrayantes | `jumpscare.mp4`, `surveillance.mp4`, `static_ghost.mp4`, `apparition.mp4` | Créations procédurales originales |

Aucune voix ni enregistrement de personne n’est utilisé, et aucun visage n’est une photographie : les visages sont des dessins générés. Les sources CC0 sont créditées dans `custom_components/haunted_house/media/CREDITS.md`. Les scripts de la machine de développement (`scripts/generate_horror_audio.py`, `build_cc0_media.py`, `generate_horror_video.py`, `generate_assets.py`) recréent les fichiers avec numpy, Pillow et ffmpeg ; ils ne sont pas nécessaires dans HA.

## Aperçu et test

**Configurer → Prévisualiser et tester une scène** propose une zone et une scène, affiche la scène effective et les appareils sélectionnés, puis permet d’exécuter le test. Sans lancer le test, aucune commande n’est envoyée.

Depuis la page de l’appareil de la zone (« Haunted House NOM »), sans passer par Configurer : choisir la scène dans la liste **Scène de test** (Bougies, Cimetière, Orage, Apparition, Maison hantée, Sons spatialisés, Enfants, Poursuite, Retrait), puis appuyer sur **Aperçu (scène choisie)** ou **Tester (scène choisie)**. Par défaut la liste affiche la scène de déclenchement de la zone ; le choix est oublié au rechargement de l’intégration. Le test garde les mêmes règles : session arrêtée, 20 secondes maximum, restauration automatique. L’aperçu est disponible dans les attributs du capteur État.

Le test est une session isolée, sans parcours automatique, réaction aux capteurs, progression ou autres zones. Il refuse de démarrer tant que le spectacle est actif ou qu’une restauration reste en attente. Il sauvegarde les appareils de sa zone, joue la scène pendant 20 secondes maximum puis restaure, y compris après interruption. Le bouton global d’arrêt peut l’interrompre.

Un test ignore le délai de démarrage des volets : la scène Apparition les fait bouger tout de suite, si le volet est éligible. Un aperçu liste les appareils sélectionnés, pas la garantie que leurs fonctionnalités soient toutes disponibles.

## Journal et commandes

Le capteur **Journal des manifestations** expose les 20 dernières entrées. L’historique persistant garde les 200 dernières ; il est sauvegardé avec un délai de quelques secondes et vidé sur disque à l’arrêt normal. Chaque événement est également émis sur le bus sous `haunted_house_event`.

Le capteur **Phase du spectacle** indique `idle`, `steady`, `calm`, `rising` ou `finale`. Le capteur **État** conserve les diagnostics par zone, la récupération et le dernier aperçu.

Actions existantes : `haunted_house.start`, `stop`, `scare`, `play_scene`.

```yaml
action: haunted_house.play_scene
data:
  zone_id: IDENTIFIANT_DE_ZONE
  scene: storm
```

Parcours choisi :

```yaml
action: haunted_house.ghost_walk
data:
  zone_ids:
    - IDENTIFIANT_ENTREE
    - IDENTIFIANT_SALON
```

Aperçu sans commander les appareils :

```yaml
action: haunted_house.preview_scene
data:
  zone_id: IDENTIFIANT_DE_ZONE
  scene: apparition
response_variable: apercu
```

Test isolé :

```yaml
action: haunted_house.test_scene
data:
  zone_id: IDENTIFIANT_DE_ZONE
  scene: storm
response_variable: resultat
```

Journal :

```yaml
action: haunted_house.history
data:
  limit: 50
response_variable: journal
```

`preview_scene` et `history` renvoient obligatoirement une réponse ; `test_scene` peut en renvoyer une. Les identifiants des zones sont visibles dans l’attribut `zones` du capteur État. La zone migrée depuis v1 conserve l’identifiant `maison`.

## Arrêt, sauvegarde et limites de restauration

Avant toute commande, les états des appareils éligibles sont persistés. L’arrêt manuel, la fin de session et la fin d’un test tentent de rétablir : marche/arrêt et attributs des lampes ; position des volets ; marche/arrêt des prises ; volume des enceintes et arrêt des médias lancés ; source connue des lecteurs vidéo et extinction de ceux allumés par le spectacle.

La musique, les files d’attente, les groupes d’enceintes et les applications TV antérieures ne sont pas restaurés. La restauration peut remplacer un réglage manuel effectué pendant la session.

Les volets doivent avoir une classe `blind`, `curtain`, `shade` ou `shutter`, une position connue et accepter les positions. Les portes, portails, garages et volets déjà en mouvement sont exclus. Les volets ne bougent que dans la scène **Apparition**, jamais en mode enfants, pas avant le délai de 180 secondes (par défaut) après le démarrage de la session, et d’un pas de 5 % seulement en profil Familiale (10 % Inquiétante, 15 % Maison hantée). Quand un volet est ignoré, le journal contient `cover_ignored` ou `cover_skipped` avec la raison. Un appareil indisponible au début est ignoré jusqu’à la session suivante. Choisir pour les prises uniquement des décorations adaptées au spectacle : la nature de l’appareil branché n’est pas détectable.

Après un redémarrage brutal, aucune scène ne reprend automatiquement. Si le capteur affiche `recovery_pending`, utiliser **Arrêter et restaurer**. Les échecs de restauration restent sauvegardés pour nouvel essai et bloquent un nouveau démarrage. Un arrêt normal de HA tente la restauration sans garantie si les appareils ou le réseau sont déjà arrêtés. Si un appareil ne peut vraiment pas être restauré (supprimé, hors ligne définitivement), le bouton **Abandonner la restauration** oublie l’instantané sans rien envoyer aux appareils ; vérifier ensuite leur état à la main. L’attribut `snapshot_entities` du capteur État liste les appareils en attente, et les événements `device_error` du journal indiquent l’entité et l’action en échec. Une commande acceptée ne garantit pas qu’un volet a atteint physiquement sa position.

## Validation et périmètre

```bash
python3 -m unittest discover -s tests -v
```

47 tests couvrent les modèles, les neuf scènes, les options en plusieurs étapes, la conservation des médias après édition, les parcours, réactions, embranchements, profils enfants, TTS, lecture vidéo, aperçu, test isolé, interruption pendant un test, journal et restauration. Les tests de formulaire utilisent eux aussi des doubles : ils vérifient le séquencement, pas le rendu frontend ni les schémas HA réels.

Le workflow GitHub `Validate` lance hassfest et la validation HACS à chaque push. Les fichiers Python, JSON et YAML sont vérifiés. Les cinq vidéos sont décodées et leur durée contrôlée. Cette validation ne remplace pas un essai dans votre instance HA avec votre matériel.

Domaines pilotés : `light`, `cover`, `media_player`, `switch`, plus une entité `tts` explicitement configurée pour la voix. Déclencheurs : `binary_sensor`, `input_button`, `event`. La v3 n’ajoute pas de contrôle arbitraire des autres domaines.

Références : documentation développeur Home Assistant sur les [config flows](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/), [options flows](https://developers.home-assistant.io/docs/config_entries_options_flow_handler/), [événements](https://developers.home-assistant.io/docs/integration_listen_events/), [actions et réponses](https://developers.home-assistant.io/docs/dev_101_services/) ; actions [play_media](https://www.home-assistant.io/actions/media_player.play_media/) et [tts.speak](https://www.home-assistant.io/actions/tts.speak).

Licence MIT, y compris les médias originaux de démonstration.
