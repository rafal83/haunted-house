"""Haunted House v3 entry, service and event lifecycle."""
from pathlib import Path
import voluptuous as vol
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import SupportsResponse
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_state_change_event
from .const import DOMAIN, MEDIA_URL_PATH, PLATFORMS, SCENES, SERVICES
from .engine import HauntedEngine
from .entity import device_info
from .model import normalize


async def async_migrate_entry(hass, entry):
    if entry.version > 3:
        return False
    if entry.version < 3:
        hass.config_entries.async_update_entry(entry, options=normalize(entry.options), version=3)
    return True


async def async_setup_entry(hass, entry):
    domain_data = hass.data.setdefault(DOMAIN, {})
    if not domain_data.get("media_registered"):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(MEDIA_URL_PATH, str(Path(__file__).parent / "media"), False)])
        domain_data["media_registered"] = True
    engine = HauntedEngine(hass, entry)
    await engine.load()
    domain_data[entry.entry_id] = engine

    async def service(call):
        try:
            if call.service == "start":
                await engine.start()
            elif call.service == "stop":
                await engine.stop()
            elif call.service == "ghost_walk":
                await engine.walk(call.data.get("zone_ids"))
            elif call.service == "preview_scene":
                return engine.preview(call.data["zone_id"], call.data["scene"])
            elif call.service == "test_scene":
                report = await engine.test_scene(call.data["zone_id"], call.data["scene"])
                return report if call.return_response else None
            elif call.service == "history":
                return {"events": engine.history[-call.data.get("limit", 50):]}
            else:
                await engine.effect(scare=True, zone_id=call.data.get("zone_id"), scene=call.data.get("scene"))
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

    for name in SERVICES:
        fields, response = {}, SupportsResponse.NONE
        if name in ("scare", "play_scene", "preview_scene", "test_scene"):
            required_zone = name in ("preview_scene", "test_scene")
            fields[vol.Required("zone_id") if required_zone else vol.Optional("zone_id")] = str
            fields[vol.Optional("scene") if name == "scare" else vol.Required("scene")] = vol.In(SCENES)
        if name == "ghost_walk":
            fields[vol.Optional("zone_ids")] = [str]
        elif name == "history":
            fields[vol.Optional("limit", default=50)] = vol.All(vol.Coerce(int), vol.Range(min=1, max=200))
        if name in ("history", "preview_scene"):
            response = SupportsResponse.ONLY
        elif name == "test_scene":
            response = SupportsResponse.OPTIONAL
        hass.services.async_register(DOMAIN, name, service, schema=vol.Schema(fields), supports_response=response)

    watched = list({e for z in engine.zones.values() for e in z["triggers"] + z["reactive_lights"]})

    async def on_event(event):
        await engine.handle_event(event.data["entity_id"], event.data.get("old_state"), event.data.get("new_state"))

    if watched:
        entry.async_on_unload(async_track_state_change_event(hass, watched, on_event))

    async def shutdown(event):
        await engine.stop()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown))
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    _sync_devices(hass, entry, engine)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _sync_devices(hass, entry, engine):
    """Create the main device and one child device per zone; drop devices of removed zones."""
    registry = dr.async_get(hass)
    main = registry.async_get_or_create(config_entry_id=entry.entry_id, **device_info(entry.entry_id))
    keep = {entry.entry_id}
    for zone in engine.zones.values():
        info = device_info(entry.entry_id, zone)
        device = registry.async_get_or_create(config_entry_id=entry.entry_id, **info)
        if device.via_device_id != main.id:
            registry.async_update_device(device.id, via_device_id=main.id)
        keep.update(ident for domain, ident in info["identifiers"] if domain == DOMAIN)
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        if not any(domain == DOMAIN and ident in keep for domain, ident in device.identifiers):
            registry.async_remove_device(device.id)


async def async_reload_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    engine = hass.data[DOMAIN][entry.entry_id]
    await engine.stop()
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    hass.data[DOMAIN].pop(entry.entry_id)
    for name in SERVICES:
        hass.services.async_remove(DOMAIN, name)
    return True
