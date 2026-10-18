"""UI setup and transactional options editor for zones."""
from copy import deepcopy
from uuid import uuid4
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector, entity_registry as er
from .const import DOMAIN, DEFAULTS, ENTITY_KEYS, ZONE_DEFAULTS, SCENES, INTENSITIES
from .model import normalize, validate_zone


def choose(options, multiple=False, translation_key=None):
    settings = {"options": options, "multiple": multiple, "mode": "dropdown"}
    if translation_key:
        settings["translation_key"] = translation_key
    return selector.SelectSelector(selector.SelectSelectorConfig(**settings))


def global_schema(values):
    v = DEFAULTS | values
    fields = {vol.Required("intensity", default=v["intensity"]): choose(list(INTENSITIES), translation_key="intensities"),
              vol.Required("restore_between_scenes", default=v["restore_between_scenes"]): selector.BooleanSelector()}
    for key, low, high, step in (("volume", 0, 1, .05), ("interval", 8, 120, 1),
                                ("duration", 1, 180, 1), ("cover_cooldown", 120, 1800, 1),
                                ("trigger_cooldown", 10, 300, 1)):
        fields[vol.Required(key, default=v[key])] = selector.NumberSelector(
            selector.NumberSelectorConfig(min=low, max=high, step=step, mode="box"))
    return vol.Schema(fields)


def zone_schema(values, zones=None):
    v = ZONE_DEFAULTS | values
    fields = {vol.Required("name", default=v["name"]): selector.TextSelector()}
    for key, domain in ENTITY_KEYS.items():
        fields[vol.Optional(key, default=v[key])] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain=domain, multiple=True))
    fields[vol.Optional("triggers", default=v["triggers"])] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain=["binary_sensor", "input_button", "event"], multiple=True))
    fields[vol.Required("scenes", default=v["scenes"])] = choose(SCENES, True, "scenes")
    fields[vol.Required("trigger_scene", default=v["trigger_scene"])] = choose(SCENES, translation_key="scenes")
    fields[vol.Required("intensity", default=v["intensity"])] = choose(["inherit", *INTENSITIES], translation_key="intensities")
    fields[vol.Required("kids_mode", default=v["kids_mode"])] = selector.BooleanSelector()
    fields[vol.Optional("reactive_lights", default=v["reactive_lights"])] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="light", multiple=True))
    fields[vol.Required("branch_enabled", default=v["branch_enabled"])] = selector.BooleanSelector()
    route_options = [{"value": "", "label": "—"}, *[{"value": z["id"], "label": z["name"]} for z in (zones or [])]]
    for key in ("next_zone", "return_zone"):
        fields[vol.Optional(key, default=v[key])] = choose(route_options)
    return vol.Schema(fields)


def media_schema(values):
    return vol.Schema({vol.Required("video_power_on", default=values.get("video_power_on", False)): selector.BooleanSelector()})


def story_schema(values, zones):
    v = DEFAULTS | values
    fields = {}
    for key in ("progression", "auto_walk"):
        fields[vol.Required(key, default=v[key])] = selector.BooleanSelector()
    for key, low, high in (("walk_interval", 30, 1800), ("branch_window", 5, 120)):
        fields[vol.Required(key, default=v[key])] = selector.NumberSelector(selector.NumberSelectorConfig(min=low, max=high, step=1, mode="box"))
    fields[vol.Optional("ghost_route", default=v["ghost_route"])] = choose(
        [{"value": z["id"], "label": z["name"]} for z in zones], multiple=True)
    fields[vol.Optional("tts_entity", default=v["tts_entity"])] = selector.TextSelector()
    fields[vol.Optional("kids_messages", default=v["kids_messages"])] = selector.TextSelector(selector.TextSelectorConfig(multiline=True))
    return vol.Schema(fields)


def validate(hass, zone, others):
    errors = validate_zone(zone, others)
    if errors:
        return errors
    registry = er.async_get(hass)
    for key in ENTITY_KEYS:
        for entity_id in zone.get(key, []):
            registered = registry.async_get(entity_id)
            if registered and registered.platform == DOMAIN:
                return {key: "own_entity"}
    for entity_id in zone.get("covers", []):
        state = hass.states.get(entity_id)
        if state and state.attributes.get("device_class") in ("door", "garage", "gate"):
            return {"covers": "unsafe_cover"}
    return {}


class HauntedHouseFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 3

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        errors = {}
        if user_input is not None:
            self._settings = user_input
            return await self.async_step_zone()
        return self.async_show_form(step_id="user", data_schema=global_schema(user_input or {}), errors=errors)

    async def async_step_zone(self, user_input=None):
        errors = {}
        if user_input is not None:
            errors = validate(self.hass, user_input, [])
            if not errors:
                self._pending = deepcopy(ZONE_DEFAULTS) | user_input | {"id": uuid4().hex[:12]}
                return await self.async_step_zone_media()
        return self.async_show_form(step_id="zone", data_schema=zone_schema(user_input or {}), errors=errors)

    async def async_step_zone_media(self, user_input=None):
        errors = {}
        if user_input is not None:
            zone = self._pending | user_input
            errors = validate(self.hass, zone, [])
            if not errors:
                return self.async_create_entry(title="Haunted House", data={}, options=self._settings | {"zones": [zone]})
        return self.async_show_form(step_id="zone_media", errors=errors,
                                   data_schema=media_schema(self._pending | (user_input or {})))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return HauntedOptionsFlow()


class HauntedOptionsFlow(config_entries.OptionsFlow):
    """Changes are saved once, using Save, rather than on every zone edit."""
    async def async_step_init(self, user_input=None):
        if not hasattr(self, "_draft"):
            self._draft = normalize(self.config_entry.options)
        return self.async_show_menu(step_id="init", menu_options=["settings", "story", "add_zone", "edit_zone", "remove_zone", "test_scene", "save"])

    async def async_step_settings(self, user_input=None):
        errors = {}
        if user_input is not None:
            self._draft.update(user_input)
            return await self.async_step_init()
        return self.async_show_form(step_id="settings", errors=errors,
                                   data_schema=global_schema(user_input if user_input is not None else self._draft))

    async def async_step_story(self, user_input=None):
        errors = {}
        if user_input is not None:
            tts = user_input.get("tts_entity", "").strip()
            if tts and not tts.startswith("tts."):
                errors["tts_entity"] = "invalid_entity"
            else:
                self._draft.update(user_input | {"tts_entity": tts})
                return await self.async_step_init()
        return self.async_show_form(step_id="story", errors=errors,
                                   data_schema=story_schema(self._draft | (user_input or {}), self._draft["zones"]))

    async def async_step_add_zone(self, user_input=None):
        self._editing = None
        return await self.async_step_zone()

    async def _select_zone(self, step, user_input):
        zones = self._draft["zones"]
        if not zones:
            return await self.async_step_init()
        if user_input is not None:
            return None
        return self.async_show_form(step_id=step, data_schema=vol.Schema({
            vol.Required("zone_id"): choose([{"value": z["id"], "label": z["name"]} for z in zones])}))

    async def async_step_edit_zone(self, user_input=None):
        form = await self._select_zone("edit_zone", user_input)
        if form is not None:
            return form
        self._editing = user_input["zone_id"]
        return await self.async_step_zone()

    async def async_step_remove_zone(self, user_input=None):
        form = await self._select_zone("remove_zone", user_input)
        if form is not None:
            return form
        if len(self._draft["zones"]) == 1:
            return self.async_show_form(step_id="remove_zone", data_schema=vol.Schema({
                vol.Required("zone_id"): choose([{
                    "value": z["id"], "label": z["name"]} for z in self._draft["zones"]])}),
                errors={"base": "last_zone"})
        deleted = user_input["zone_id"]
        self._draft["zones"] = [z for z in self._draft["zones"] if z["id"] != deleted]
        self._draft["ghost_route"] = [z for z in self._draft["ghost_route"] if z != deleted]
        for zone in self._draft["zones"]:
            for key in ("next_zone", "return_zone"):
                if zone[key] == deleted:
                    zone[key] = ""
        return await self.async_step_init()

    async def async_step_zone(self, user_input=None):
        editing = getattr(self, "_editing", None)
        old = next((z for z in self._draft["zones"] if z["id"] == editing), {})
        errors = {}
        if user_input is not None:
            others = [z for z in self._draft["zones"] if z["id"] != editing]
            errors = validate(self.hass, user_input, others)
            if not errors:
                self._pending = deepcopy(ZONE_DEFAULTS) | old | user_input | {"id": editing or uuid4().hex[:12]}
                return await self.async_step_zone_media()
        return self.async_show_form(step_id="zone", errors=errors,
                                   data_schema=zone_schema(user_input if user_input is not None else old, self._draft["zones"]))

    async def async_step_zone_media(self, user_input=None):
        errors = {}
        if user_input is not None:
            zone = self._pending | user_input
            others = [z for z in self._draft["zones"] if z["id"] != zone["id"]]
            errors = validate(self.hass, zone, others)
            if not errors:
                self._draft["zones"] = others + [zone]
                return await self.async_step_init()
        return self.async_show_form(step_id="zone_media", errors=errors,
                                   data_schema=media_schema(self._pending | (user_input or {})))

    async def async_step_test_scene(self, user_input=None):
        engine = self.hass.data[DOMAIN][self.config_entry.entry_id]
        if user_input is not None:
            self._test_selection = user_input
            self._preview = engine.preview(user_input["zone_id"], user_input["scene"])
            return await self.async_step_test_preview()
        return self.async_show_form(step_id="test_scene", data_schema=vol.Schema({
            vol.Required("zone_id"): choose([{"value": z["id"], "label": z["name"]} for z in engine.zones.values()]),
            vol.Required("scene", default="candle"): choose(SCENES, translation_key="scenes")}))

    async def async_step_test_preview(self, user_input=None):
        errors = {}
        engine = self.hass.data[DOMAIN][self.config_entry.entry_id]
        if user_input is not None:
            if not user_input["run_test"]:
                return await self.async_step_init()
            try:
                report = await engine.test_scene(**self._test_selection)
            except ValueError:
                errors["base"] = "test_busy"
            else:
                return self.async_show_form(step_id="test_result", data_schema=vol.Schema({}),
                    description_placeholders={"report": str({k: v for k, v in report.items() if k != "preview"})})
        details = "\n".join(f"- {key}: {', '.join(ids) or '—'}" for key, ids in self._preview["entities"].items())
        return self.async_show_form(step_id="test_preview", errors=errors,
            data_schema=vol.Schema({vol.Required("run_test", default=False): selector.BooleanSelector()}),
            description_placeholders={"zone": self._preview["zone_name"], "scene": self._preview["effective_scene"], "devices": details})

    async def async_step_test_result(self, user_input=None):
        return await self.async_step_init()

    async def async_step_save(self, user_input=None):
        if not self._draft["zones"]:
            return self.async_show_form(step_id="save", data_schema=vol.Schema({}), errors={"base": "no_zones"})
        return self.async_create_entry(title="", data=self._draft)
