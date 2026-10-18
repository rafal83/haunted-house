"""Shared entity behavior."""
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import json
from pathlib import Path
from .const import DOMAIN

VERSION = json.loads((Path(__file__).parent / "manifest.json").read_text(encoding="utf-8"))["version"]


class HauntedEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, engine, key, name, icon):
        self.engine = engine
        self._attr_unique_id = f"{engine.entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_device_info = {"identifiers": {(DOMAIN, engine.entry.entry_id)},
                                  "name": "Haunted House", "manufacturer": "Community prototype",
                                  "model": f"Haunted House {VERSION}"}

    async def async_added_to_hass(self):
        self.async_on_remove(async_dispatcher_connect(
            self.hass, self.engine.signal, self.async_write_ha_state))
