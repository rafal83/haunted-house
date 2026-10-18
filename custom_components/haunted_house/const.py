"""Stable configuration and scene vocabulary."""
DOMAIN = "haunted_house"
PLATFORMS = ["switch", "button", "sensor", "select"]
ENTITY_KEYS = {"lights": "light", "covers": "cover", "media_players": "media_player", "switches": "switch"}
SCENES = ["candle", "graveyard", "storm", "apparition", "haunted"]
INTENSITIES = {
    "family": {"brightness": 90, "volume": .20, "cover_step": 5, "pulse": 1.5},
    "eerie": {"brightness": 150, "volume": .35, "cover_step": 10, "pulse": 1.0},
    "haunted": {"brightness": 210, "volume": .50, "cover_step": 15, "pulse": .7},
}
DEFAULTS = {"volume": .25, "interval": 20, "duration": 30, "cover_cooldown": 180,
            "trigger_cooldown": 20, "intensity": "family", "sounds": ""}
ZONE_DEFAULTS = {"name": "Maison", "lights": [], "covers": [], "media_players": [],
                 "switches": [], "triggers": [], "sounds": "", "scenes": list(SCENES),
                 "trigger_scene": "apparition"}

# v3 fields are added without altering old option values or zone IDs.
SCENES += ["spatial", "kids", "pursuit", "retreat"]
INTENSITIES["kids"] = {"brightness": 65, "volume": .12, "cover_step": 0, "pulse": 2}
AUDIO_TAGS = ["candle", "graveyard", "storm", "apparition", "haunted", "footsteps", "whisper", "knock", "laugh", "kids"]
DEFAULTS.update({"progression": True, "auto_walk": False, "walk_interval": 120,
                 "ghost_route": [], "branch_window": 30, "tts_entity": "",
                 "kids_messages": "Bouh ! C’est la citrouille magique !\nLe petit fantôme te souhaite une bonne soirée !"})
ZONE_DEFAULTS.update({"intensity": "inherit", "kids_mode": False, "reactive_lights": [],
                      "branch_enabled": False, "next_zone": "", "return_zone": "",
                      "video_players": [], "videos": "", "kids_videos": "", "video_power_on": False})
ZONE_DEFAULTS["scenes"] = list(SCENES)
ZONE_DEFAULTS.update({f"sound_{tag}": "" for tag in AUDIO_TAGS})
ENTITY_KEYS["video_players"] = "media_player"
SERVICES = ["start", "stop", "scare", "play_scene", "ghost_walk", "preview_scene", "test_scene", "history"]

# Media shipped inside the integration, served at MEDIA_URL_PATH and used when a bank is empty.
MEDIA_URL_PATH = "/haunted_house_media"
BUNDLED_AUDIO = {"candle": "drone", "graveyard": "drone", "storm": "thunder", "apparition": "whisper",
                 "haunted": "drone", "footsteps": "footsteps", "whisper": "whisper", "knock": "knock",
                 "laugh": "laugh", "kids": "kids"}

SCENE_LABELS = {"candle": "Bougies", "graveyard": "Cimetière", "storm": "Orage", "apparition": "Apparition",
                "haunted": "Maison hantée", "spatial": "Sons spatialisés", "kids": "Enfants",
                "pursuit": "Poursuite", "retreat": "Retrait"}
