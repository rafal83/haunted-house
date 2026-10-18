"""Stable configuration and scene vocabulary."""
DOMAIN = "haunted_house"
PLATFORMS = ["switch", "button", "sensor", "select"]
ENTITY_KEYS = {"lights": "light", "covers": "cover", "media_players": "media_player", "switches": "switch"}
SCENES = ["candle", "graveyard", "storm", "apparition", "haunted"]
INTENSITIES = {
    "family": {"brightness": 90, "volume": .20, "cover_step": 5, "pulse": 1.5, "fear": 1},
    "eerie": {"brightness": 150, "volume": .35, "cover_step": 10, "pulse": 1.0, "fear": 2},
    "haunted": {"brightness": 210, "volume": .50, "cover_step": 15, "pulse": .7, "fear": 3},
}
DEFAULTS = {"volume": .25, "interval": 20, "duration": 30, "cover_cooldown": 180,
            "trigger_cooldown": 20, "intensity": "family"}
ZONE_DEFAULTS = {"name": "Maison", "lights": [], "covers": [], "media_players": [],
                 "switches": [], "triggers": [], "scenes": list(SCENES),
                 "trigger_scene": "apparition"}

# v3 fields are added without altering old option values or zone IDs.
SCENES += ["spatial", "kids", "pursuit", "retreat"]
INTENSITIES["kids"] = {"brightness": 65, "volume": .12, "cover_step": 0, "pulse": 2, "fear": 0}
AUDIO_TAGS = ["candle", "graveyard", "storm", "apparition", "haunted", "footsteps", "whisper", "knock", "laugh", "kids"]
DEFAULTS.update({"progression": True, "auto_walk": False, "walk_interval": 120,
                 "ghost_route": [], "branch_window": 30, "tts_entity": "",
                 "kids_messages": "Bouh ! C’est la citrouille magique !\nLe petit fantôme te souhaite une bonne soirée !"})
ZONE_DEFAULTS.update({"intensity": "inherit", "kids_mode": False, "reactive_lights": [],
                      "branch_enabled": False, "next_zone": "", "return_zone": "",
                      "video_players": [], "video_power_on": False})
ZONE_DEFAULTS["scenes"] = list(SCENES)
ENTITY_KEYS["video_players"] = "media_player"
SERVICES = ["start", "stop", "scare", "play_scene", "ghost_walk", "preview_scene", "test_scene", "history"]

# Media shipped inside the integration, served at MEDIA_URL_PATH and used when a bank is empty.
# Each tag maps to several variants; one is picked at random. HARSH ones need fear >= 2.
MEDIA_URL_PATH = "/haunted_house_media"
BUNDLED_AUDIO = {
    "candle": ["creak", "drone", "breath"],
    "graveyard": ["breath", "whisper", "ambience", "creak"],
    "storm": ["thunder"],
    "apparition": ["scream", "scream_2", "scream_3", "roar", "whisper"],
    "haunted": ["growl", "growl_2", "roar", "drone", "ambience", "hit_bass", "scream_4"],
    "footsteps": ["footsteps"], "whisper": ["whisper", "breath"], "knock": ["knock"],
    "laugh": ["laugh"], "kids": ["kids"],
    "scream": ["scream", "scream_2", "scream_3", "scream_4"],
    "creak": ["creak"], "growl": ["growl", "growl_2", "roar"],
}
HARSH_AUDIO = {"scream", "scream_2", "scream_3", "scream_4", "roar", "growl", "growl_2", "hit_bass"}
BUNDLED_VIDEO = {"scary": ["jumpscare", "surveillance", "static_ghost", "apparition"],
                 "mild": ["apparition", "surveillance"], "kids": ["kids"]}

SCENE_LABELS = {"candle": "Bougies", "graveyard": "Cimetière", "storm": "Orage", "apparition": "Apparition",
                "haunted": "Maison hantée", "spatial": "Sons spatialisés", "kids": "Enfants",
                "pursuit": "Poursuite", "retreat": "Retrait"}
