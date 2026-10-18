"""Global and per-zone controls."""
from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN
from .entity import HauntedEntity


async def async_setup_entry(hass, entry, async_add_entities):
    engine = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HauntedButton(engine, True), HauntedButton(engine, False),
                        DiscardButton(engine), GhostButton(engine), *[ZoneButton(engine, z) for z in engine.zones.values()],
                        *[TestButton(engine, z, preview) for z in engine.zones.values() for preview in (True, False)]])


class HauntedButton(HauntedEntity, ButtonEntity):
    def __init__(self, engine, stop):
        self._stop = stop
        super().__init__(engine, "stop" if stop else "scare",
                         "Arrêter et restaurer" if stop else "Déclencher une surprise",
                         "mdi:stop-circle" if stop else "mdi:halloween")

    async def async_press(self):
        if self._stop:
            await self.engine.stop()
        else:
            try:
                await self.engine.effect(scare=True)
            except ValueError as err:
                raise HomeAssistantError(str(err)) from err


class DiscardButton(HauntedEntity, ButtonEntity):
    def __init__(self, engine):
        super().__init__(engine, "discard_restoration", "Abandonner la restauration", "mdi:backup-restore")

    async def async_press(self):
        try:
            await self.engine.discard_restoration()
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err


class ZoneButton(HauntedEntity, ButtonEntity):
    def __init__(self, engine, zone):
        self.zone_id = zone["id"]
        super().__init__(engine, f"surprise_{self.zone_id}", "Surprise", "mdi:halloween", zone)

    async def async_press(self):
        try:
            await self.engine.effect(scare=True, zone_id=self.zone_id)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err


class GhostButton(HauntedEntity, ButtonEntity):
    def __init__(self, engine):
        super().__init__(engine, "ghost_walk", "Faire circuler le fantôme", "mdi:ghost")

    async def async_press(self):
        try:
            await self.engine.walk()
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err


class TestButton(HauntedEntity, ButtonEntity):
    def __init__(self, engine, zone, preview):
        self.zone_id, self._preview = zone["id"], preview
        super().__init__(engine, f"{'preview' if preview else 'test'}_{zone['id']}",
                         "Aperçu (scène choisie)" if preview else "Tester (scène choisie)",
                         "mdi:eye" if preview else "mdi:play-circle-outline", zone)

    async def async_press(self):
        scene = self.engine.chosen_scene(self.zone_id)
        if self._preview:
            self.engine.preview(self.zone_id, scene)
        else:
            try:
                await self.engine.test_scene(self.zone_id, scene)
            except ValueError as err:
                raise HomeAssistantError(str(err)) from err
