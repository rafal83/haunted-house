"""Shared entity behavior."""
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import json
from pathlib import Path
from .const import DOMAIN

VERSION = json.loads((Path(__file__).parent / "manifest.json").read_text(encoding="utf-8"))["version"]


def device_info(entry_id, zone=None):
    """Main device for global controls; one child device per zone for its own controls."""
    if zone is None:
        return {"identifiers": {(DOMAIN, entry_id)}, "name": "Haunted House",
                "manufacturer": "Community prototype", "model": f"Haunted House {VERSION}"}
    # The link to the main device is set by the registry in __init__ (via_device_id), not here.
    return {"identifiers": {(DOMAIN, f"{entry_id}_{zone['id']}")}, "name": f"Haunted House {zone['name']}",
            "manufacturer": "Community prototype", "model": "Zone"}


class HauntedEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, engine, key, name, icon, zone=None):
        self.engine = engine
        self._attr_unique_id = f"{engine.entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_device_info = device_info(engine.entry.entry_id, zone)

    async def async_added_to_hass(self):
        self.async_on_remove(async_dispatcher_connect(
            self.hass, self.engine.signal, self.async_write_ha_state))
