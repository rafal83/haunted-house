"""Engine status and zone diagnostics."""
from homeassistant.components.sensor import SensorEntity
from .const import DOMAIN
from .entity import HauntedEntity


async def async_setup_entry(hass, entry, async_add_entities):
    engine = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HauntedStatus(engine), NarrativeStatus(engine), HistoryStatus(engine),
                        *[ZoneStatus(engine, z) for z in engine.zones.values()]])


class HauntedStatus(HauntedEntity, SensorEntity):
    def __init__(self, engine):
        super().__init__(engine, "status", "État", "mdi:ghost-outline")

    @property
    def native_value(self):
        return self.engine.last_effect

    @property
    def extra_state_attributes(self):
        return {"running": self.engine.running, "errors": self.engine.errors,
                "intensity": self.engine.options["intensity"], "phase": self.engine.phase, "last_zone": self.engine.last_zone,
                "preview": self.engine.last_preview, "ghost_route_active": list(self.engine._reserved_zones),
                "restoration_pending": bool(self.engine.snapshot) and not self.engine.running,
                "snapshot_entities": list(self.engine.snapshot),
                "zones": [{"id": z["id"], "name": z["name"],
                           "scene": self.engine.zone_last_effect.get(z["id"], "idle"),
                           "active": z["id"] in self.engine._effects and not self.engine._effects[z["id"]].done()}
                          for z in self.engine.zones.values()]}


class NarrativeStatus(HauntedEntity, SensorEntity):
    def __init__(self, engine):
        super().__init__(engine, "phase", "Phase du spectacle", "mdi:drama-masks")

    @property
    def native_value(self):
        return self.engine.phase


class HistoryStatus(HauntedEntity, SensorEntity):
    def __init__(self, engine):
        super().__init__(engine, "history", "Journal des manifestations", "mdi:history")

    @property
    def native_value(self):
        return self.engine.history[-1]["kind"] if self.engine.history else "empty"

    @property
    def extra_state_attributes(self):
        return {"count": len(self.engine.history), "events": self.engine.history[-20:]}


class ZoneStatus(HauntedEntity, SensorEntity):
    def __init__(self, engine, zone):
        self.zone_id = zone["id"]
        super().__init__(engine, f"zone_status_{self.zone_id}", "Dernière scène", "mdi:ghost-outline", zone)

    @property
    def native_value(self):
        return self.engine.zone_last_effect.get(self.zone_id, "idle")

    @property
    def extra_state_attributes(self):
        task = self.engine._effects.get(self.zone_id)
        return {"zone": self.engine.zones[self.zone_id]["name"], "active": bool(task and not task.done()),
                "chosen_test_scene": self.engine.chosen_scene(self.zone_id)}
