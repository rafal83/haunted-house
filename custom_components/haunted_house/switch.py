"""Show switch."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN
from .entity import HauntedEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([HauntedSwitch(hass.data[DOMAIN][entry.entry_id])])


class HauntedSwitch(HauntedEntity, SwitchEntity):
    def __init__(self, engine):
        super().__init__(engine, "enabled", "Mode hanté", "mdi:ghost")

    @property
    def is_on(self):
        return self.engine.running

    async def async_turn_on(self, **kwargs):
        try:
            await self.engine.start()
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_turn_off(self, **kwargs):
        await self.engine.stop()
