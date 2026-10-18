"""Per-zone scene picker used by the preview and test buttons."""
from homeassistant.components.select import SelectEntity
from .const import DOMAIN, SCENE_LABELS, SCENES
from .entity import HauntedEntity

LABEL_TO_SCENE = {label: scene for scene, label in SCENE_LABELS.items()}


async def async_setup_entry(hass, entry, async_add_entities):
    engine = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SceneSelect(engine, z) for z in engine.zones.values()])


class SceneSelect(HauntedEntity, SelectEntity):
    _attr_options = [SCENE_LABELS[s] for s in SCENES]

    def __init__(self, engine, zone):
        self.zone_id = zone["id"]
        super().__init__(engine, f"test_scene_{self.zone_id}", f"Scène de test {zone['name']}", "mdi:theater")

    @property
    def current_option(self):
        return SCENE_LABELS[self.engine.chosen_scene(self.zone_id)]

    async def async_select_option(self, option):
        self.engine.choose_scene(self.zone_id, LABEL_TO_SCENE[option])
