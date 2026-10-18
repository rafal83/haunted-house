"""Pure configuration migration/validation helpers, independent of HA."""
from copy import deepcopy
from .const import DEFAULTS, ZONE_DEFAULTS, ENTITY_KEYS, INTENSITIES, SCENES


def normalize(options):
    """Convert the v1 flat layout to one zone, without changing entity IDs."""
    source = deepcopy(dict(options))
    result = deepcopy(DEFAULTS)
    result.update({k: source[k] for k in DEFAULTS if k in source})
    zones = source.get("zones")
    if zones is None:
        zones = [{"id": "maison", "name": "Maison", **{k: source.get(k, []) for k in ENTITY_KEYS}}]
    # Keys that are no longer supported (custom sound/video URLs) are dropped.
    result["zones"] = [{k: v for k, v in (deepcopy(ZONE_DEFAULTS) | zone).items() if k in ZONE_DEFAULTS or k == "id"}
                       for zone in zones]
    return result


def validate_zone(zone, other_zones):
    if not zone.get("name", "").strip():
        return {"name": "empty_name"}
    if not any(zone.get(key) for key in ENTITY_KEYS):
        return {"base": "empty_zone"}
    seen = {e for z in other_zones for k in ENTITY_KEYS for e in z.get(k, [])}
    local_seen = set()
    for key, domain in ENTITY_KEYS.items():
        ids = zone.get(key, [])
        if any(not isinstance(e, str) or not e.startswith(domain + ".") for e in ids):
            return {key: "invalid_entity"}
        # A device belongs to one zone to avoid simultaneous contradictory commands.
        if len(ids) != len(set(ids)) or set(ids) & (seen | local_seen):
            return {key: "duplicate_entity"}
        local_seen.update(ids)
    if any(not e.startswith(("binary_sensor.", "input_button.", "event.")) for e in zone.get("triggers", [])):
        return {"triggers": "invalid_entity"}
    if not zone.get("scenes") or any(s not in SCENES for s in zone["scenes"]):
        return {"scenes": "invalid_scene"}
    if zone.get("trigger_scene") not in SCENES:
        return {"trigger_scene": "invalid_scene"}
    if not set(zone.get("reactive_lights", [])) <= set(zone.get("lights", [])):
        return {"reactive_lights": "reactive_subset"}
    if zone.get("intensity", "inherit") not in ["inherit", *INTENSITIES]:
        return {"intensity": "invalid_profile"}
    return {}


def trigger_fired(old, new, entity_id):
    """Ignore initialization, unavailable states, attribute-only updates and resets."""
    if not old or not new or old.state in ("unknown", "unavailable") or new.state in ("unknown", "unavailable"):
        return False
    if old.state == new.state:
        return False
    if entity_id.startswith("binary_sensor."):
        return old.state == "off" and new.state == "on"
    return entity_id.startswith(("input_button.", "event."))
