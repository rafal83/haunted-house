"""Per-zone choreographies, tracked cancellation and persistent recovery."""
import asyncio
import logging
import random
import time
from homeassistant.core import Context
from homeassistant.helpers.storage import Store
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from .const import DOMAIN, ENTITY_KEYS, INTENSITIES, SCENES
from .model import normalize
from .story import StoryFeatures, CURRENT_ZONE, CURRENT_SCENE, WALK_SOUND

_LOGGER = logging.getLogger(__name__)
ATTRS = ("brightness", "color_mode", "rgb_color", "rgbw_color", "rgbww_color", "xy_color", "hs_color",
         "color_temp_kelvin", "effect", "current_position", "volume_level", "source")


class HauntedEngine(StoryFeatures):
    def __init__(self, hass, entry):
        self.hass, self.entry = hass, entry
        self.options = normalize(entry.options)
        self.zones = {z["id"]: z for z in self.options["zones"]}
        self.running = False
        self.last_effect = "idle"
        self.last_zone = None
        self.zone_last_effect = {}
        self.errors = 0
        self.snapshot = {}
        self._task = None
        self._effects = {}
        self._lock = asyncio.Lock()
        self._store_lock = asyncio.Lock()
        self._commands = asyncio.Semaphore(4)
        self._last_cover = {}
        self._last_scare = {}
        self._touched_media = set()
        self._context = Context()
        self._store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self.init_story()

    @property
    def signal(self):
        return f"{DOMAIN}_{self.entry.entry_id}"

    @property
    def profile(self):
        return self.zone_profile()

    def notify(self):
        async_dispatcher_send(self.hass, self.signal)

    async def load(self):
        saved = await self._store.async_load() or {}
        self.snapshot = saved.get("snapshot", {})
        self._touched_media = set(saved.get("media", []))
        self._powered_media = set(saved.get("powered", []))
        self._video_media = set(saved.get("video", []))
        self.history = (await self._history_store.async_load() or {}).get("events", [])[-200:]
        if self.snapshot:
            self.last_effect = "recovery_pending"

    async def save(self):
        async with self._store_lock:
            await self._store.async_save({"snapshot": self.snapshot, "media": sorted(self._touched_media), "powered": sorted(self._powered_media), "video": sorted(self._video_media)})

    async def call(self, domain, service, entity_id, **data):
        try:
            async with self._commands:
                async with asyncio.timeout(10):
                    await self.hass.services.async_call(domain, service,
                        {"entity_id": entity_id, **data}, blocking=True, context=self._context)
            return True
        except Exception:
            self.errors += 1
            _LOGGER.exception("Haunted House: %s.%s failed for %s", domain, service, entity_id)
            self.record("device_error", entity_id=entity_id, action=f"{domain}.{service}", zone_id=CURRENT_ZONE.get())
            return False

    def usable(self, key, zone_id=None):
        ids = self.zones[zone_id][key] if zone_id is not None else [e for z in self.zones.values() for e in z[key]]
        registry = er.async_get(self.hass)
        result = []
        for entity_id in dict.fromkeys(ids):
            registered = registry.async_get(entity_id)
            if registered and registered.platform == DOMAIN:
                continue
            if self.running and entity_id not in self.snapshot:
                continue
            state = self.hass.states.get(entity_id)
            if state and state.state not in ("unavailable", "unknown"):
                result.append(entity_id)
        return result

    async def start(self, test_zone=None):
        async with self._lock:
            if self.running:
                if test_zone is not None:
                    raise ValueError("A session is already active")
                return
            if self.snapshot:
                raise ValueError("Restore the previous session before starting a new one")
            if test_zone is not None and test_zone not in self.zones:
                raise ValueError("Unknown test zone")
            for key in ENTITY_KEYS:
                for entity_id in self.usable(key, test_zone):
                    state = self.hass.states.get(entity_id)
                    attrs = state.attributes
                    if key == "covers" and (attrs.get("device_class") not in ("blind", "curtain", "shade", "shutter")
                            or not attrs.get("supported_features", 0) & 4
                            or not isinstance(attrs.get("current_position"), (int, float))
                            or state.state in ("opening", "closing")):
                        continue
                    self.snapshot[entity_id] = {"state": state.state,
                                               "attributes": {k: attrs[k] for k in ATTRS if attrs.get(k) is not None}}
            if not self.snapshot:
                raise ValueError("No available eligible entity selected")
            self._touched_media.clear()
            self._powered_media.clear()
            self._video_media.clear()
            try:
                await self.save()
            except BaseException:
                self.snapshot = {}
                raise
            self.running = True
            self._testing = test_zone is not None
            self._started_at = self._last_walk = time.monotonic()
            self._last_presence = None
            self._presence_revision = 0
            self._last_reaction.clear()
            self._finale_started = False
            self._last_cover = {z: time.monotonic() for z in self.zones}
            self._last_scare.clear()
            self.last_effect = "started"
            self.record("session_started", test_zone=test_zone)
            if not self._testing:
                self._task = self.hass.async_create_background_task(self._run(), "Haunted House scheduler")
            self.notify()

    async def stop(self):
        async with self._lock:
            self.running = False
            tasks = [t for t in [self._task, self._story_task, *self._effects.values(), *self._branch_tasks.values(), *self._reaction_tasks.values()] if t and t is not asyncio.current_task()]
            self._task = None
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            self._effects.clear()
            self._story_task = None
            self._branch_tasks.clear()
            self._reaction_tasks.clear()
            self._reserved_zones.clear()
            self._testing = False
            await self._restore()
            self.record("session_stopped", restoration_pending=bool(self.snapshot))
            await self._history_store.async_save({"events": self.history})
            self.last_effect = "recovery_pending" if self.snapshot else "idle"
            self.notify()

    async def _restore_one(self, entity_id, saved):
        domain = entity_id.split(".", 1)[0]
        # Older snapshots may hold None values (e.g. effect, volume_level) that service schemas reject.
        attrs = {k: v for k, v in saved["attributes"].items() if v is not None}
        if domain == "media_player":
            ok = True
            if entity_id in self._touched_media:
                ok = await self.call(domain, "media_stop", entity_id)
            if "volume_level" in attrs:
                ok = await self.call(domain, "volume_set", entity_id, volume_level=attrs["volume_level"]) and ok
            if entity_id in self._video_media and "source" in attrs:
                ok = await self.call(domain, "select_source", entity_id, source=attrs["source"]) and ok
            if entity_id in self._powered_media:
                ok = await self.call(domain, "turn_off", entity_id) and ok
            return ok
        if domain == "cover":
            return await self.call(domain, "set_cover_position", entity_id, position=attrs["current_position"])
        if domain == "light" and saved["state"] == "on":
            data = {}
            if "brightness" in attrs:
                data["brightness"] = attrs["brightness"]
            color_key = {"rgb": "rgb_color", "rgbw": "rgbw_color", "rgbww": "rgbww_color", "xy": "xy_color",
                         "hs": "hs_color", "color_temp": "color_temp_kelvin"}.get(attrs.get("color_mode"))
            if color_key and color_key in attrs:
                data[color_key] = attrs[color_key]
            if "effect" in attrs:
                data["effect"] = attrs["effect"]
            return await self.call(domain, "turn_on", entity_id, **data)
        return await self.call(domain, "turn_on" if saved["state"] == "on" else "turn_off", entity_id)

    async def discard_restoration(self):
        """Forget devices that cannot be restored, so a new session or test can start."""
        async with self._lock:
            if self.running:
                raise ValueError("Stop the session before discarding the restoration")
            dropped = list(self.snapshot)
            self.snapshot = {}
            self._touched_media.clear()
            self._powered_media.clear()
            self._video_media.clear()
            await self.save()
            self.record("restoration_discarded", entity_ids=dropped)
            self.last_effect = "idle"
            self.notify()

    async def _restore(self):
        items = list(self.snapshot.items())
        results = await asyncio.gather(*(self._restore_one(e, s) for e, s in items))
        self.snapshot = {e: s for (e, s), ok in zip(items, results) if not ok}
        self._touched_media.intersection_update(self.snapshot)
        self._powered_media.intersection_update(self.snapshot)
        self._video_media.intersection_update(self.snapshot)
        await self.save()

    async def _run(self):
        deadline = time.monotonic() + self.options["duration"] * 60
        try:
            while self.running and time.monotonic() < deadline:
                if self.phase == "finale" and not self._finale_started:
                    self._finale_started = True
                    self.record("finale_started")
                    for zone_id in self.zones:
                        await self.effect(scare=True, zone_id=zone_id, scene="haunted" if "haunted" in self.zones[zone_id]["scenes"] else self.zones[zone_id]["scenes"][-1], source="finale")
                if self.options["auto_walk"] and time.monotonic() - self._last_walk >= self.options["walk_interval"]:
                    await self.walk()
                # Start a scene in each free zone; slow hardware cannot block other zones.
                for zone_id in self.zones:
                    await self.effect(zone_id=zone_id, source="automatic")
                pace = {"calm": 1.6, "rising": 1, "finale": .7}.get(self.phase, 1)
                self.notify()
                await asyncio.sleep(min(max(8, random.uniform(.7, 1.3) * self.options["interval"] * pace),
                                        max(0, deadline - time.monotonic())))
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.exception("Haunted House scheduler failed")
            self.hass.async_create_task(self.stop())
        else:
            if self.running:
                self.hass.async_create_task(self.stop())

    async def effect(self, scare=False, zone_id=None, scene=None, source="manual"):
        """Schedule and return immediately. Triggered scenes preempt their own zone."""
        async with self._lock:
            if not self.running or (self._testing and source != "test"):
                return False
            if zone_id is not None and zone_id not in self.zones:
                raise ValueError("Unknown zone ID")
            if scene is not None and scene not in SCENES:
                raise ValueError("Unknown scene")
            zone_id = zone_id or random.choice(list(self.zones))
            zone = self.zones[zone_id]
            now = time.monotonic()
            if scare and now - self._last_scare.get(zone_id, float('-inf')) < self.options["trigger_cooldown"]:
                return False
            if zone_id in self._reserved_zones:
                if not scare:
                    return False
                if self._story_task and not self._story_task.done():
                    self._story_task.cancel()
                    await asyncio.gather(self._story_task, return_exceptions=True)
            previous = self._effects.get(zone_id)
            if previous and not previous.done():
                if not scare:
                    return False
                previous.cancel()
                await asyncio.gather(previous, return_exceptions=True)
            if scare:
                self._last_scare[zone_id] = now
            candidates = zone["scenes"]
            if source == "automatic" and self.phase == "calm":
                candidates = [s for s in candidates if s in ("candle", "graveyard", "kids")] or candidates
            scene = scene or (zone["trigger_scene"] if scare else random.choice(candidates))
            self._effects[zone_id] = self.hass.async_create_background_task(
                self._scene(zone_id, scene), f"Haunted House {zone_id} {scene}")
            self._effects[zone_id].add_done_callback(lambda task: self.notify())
            effective_scene = "kids" if self.is_kids(zone_id) else scene
            self.record("scene_started", zone_id=zone_id, scene=effective_scene, requested_scene=scene, trigger=source, phase=self.phase)
            self.last_zone, self.last_effect = zone_id, effective_scene
            self.zone_last_effect[zone_id] = effective_scene
            self.notify()
            return True

    async def _scene(self, zone_id, scene):
        scene = "kids" if self.is_kids(zone_id) else scene
        zone_token = CURRENT_ZONE.set(zone_id)
        scene_token = CURRENT_SCENE.set(scene)
        outcome = "completed"
        try:
            await self._scene_body(zone_id, scene)
        except asyncio.CancelledError:
            outcome = "cancelled"
            raise
        except Exception:
            outcome = "failed"
            self.errors += 1
            _LOGGER.exception("Haunted House scene failed in %s", zone_id)
        finally:
            self.record("scene_finished", zone_id=zone_id, scene=scene, outcome=outcome)
            CURRENT_ZONE.reset(zone_token)
            CURRENT_SCENE.reset(scene_token)

    async def _scene_body(self, zone_id, scene):
        try:
            if scene == "candle":
                for _ in range(3):
                    await self._lights(zone_id, (255, 65, 0), random.uniform(.25, .55))
                    await self.pause(self.profile["pulse"])
            elif scene == "graveyard":
                await self._lights(zone_id, (0, 100, 60), .25)
                await self.pause(2)
                await self._lights(zone_id, (15, 25, 160), .20)
            elif scene == "storm":
                await self._lights(zone_id, (20, 30, 100), .12)
                await self.pause(1)
                await self._parallel(self._lights(zone_id, (210, 225, 255), 1), self._sound(zone_id))
                await self.pause(self.profile["pulse"])
                await self._lights(zone_id, (20, 30, 100), .15)
            elif scene == "apparition":
                await self._lights(zone_id, (90, 0, 150), .15)
                await self.pause(1)
                await self._parallel(self._lights(zone_id, (0, 160, 75), .65),
                                     self._sound(zone_id), self._cover(zone_id), self._prop(zone_id), self._video(zone_id))
                await self._lights(zone_id, (90, 0, 150), .20)
            elif scene == "haunted":
                await self._parallel(self._sweep(zone_id), self._sound(zone_id), self._prop(zone_id), self._video(zone_id))
            elif scene == "spatial":
                await self._parallel(self._lights(zone_id, (70, 0, 100), .25), self._spatial(zone_id))
            elif scene == "kids":
                await self._lights(zone_id, (255, 100, 10), .5)
                await self._parallel(self._play_audio(zone_id, "kids"), self._video(zone_id))
                await self.pause(2)
                await self._lights(zone_id, (180, 30, 100), .4)
            elif scene == "walk_step":
                await self._lights(zone_id, (20, 130, 80), .5)
                await self._play_audio(zone_id, WALK_SOUND.get())
                await self.pause(3)
                for entity_id in self.usable("media_players", zone_id):
                    if entity_id in self._touched_media:
                        await self.call("media_player", "media_stop", entity_id)
                await self._lights(zone_id, (30, 0, 90), .1)
            elif scene == "pursuit":
                await self._lights(zone_id, (0, 140, 60), .6)
                await self._play_audio(zone_id, "footsteps")
                await self.pause(2)
                await self._play_audio(zone_id, "knock")
                await self._lights(zone_id, (80, 0, 140), .25)
            elif scene == "retreat":
                await self._parallel(self._lights(zone_id, (90, 0, 140), .25), self._play_audio(zone_id, "laugh"))
        except asyncio.CancelledError:
            raise

    async def pause(self, seconds):
        await asyncio.sleep(seconds)

    async def _parallel(self, *coros):
        # TaskGroup cancels and joins sibling branches if a scene branch fails.
        async with asyncio.TaskGroup() as group:
            for coro in coros:
                group.create_task(coro)

    async def _light(self, entity_id, color, level):
        if not self.running or entity_id not in self.snapshot:
            return
        state = self.hass.states.get(entity_id)
        if not state or state.state in ("unknown", "unavailable"):
            return
        attrs = state.attributes
        modes = set(attrs.get("supported_color_modes", []))
        data = {}
        if modes - {"onoff"}:
            data["brightness"] = max(1, min(255, round(self.profile["brightness"] * level)))
        if modes & {"rgb", "rgbw", "rgbww", "xy", "hs"}:
            data["rgb_color"] = list(color)
        if attrs.get("supported_features", 0) & 32:
            data["transition"] = 1
        await self.call("light", "turn_on", entity_id, **data)

    async def _lights(self, zone_id, color, level):
        await asyncio.gather(*(self._light(e, color, level) for e in self.usable("lights", zone_id)))

    async def _sweep(self, zone_id):
        for entity_id in self.usable("lights", zone_id):
            await self._light(entity_id, random.choice([(255, 65, 0), (110, 0, 200), (0, 100, 55)]), .55)
            await self.pause(self.profile["pulse"])

    async def _sound(self, zone_id):
        await self._play_audio(zone_id, CURRENT_SCENE.get())

    async def _cover(self, zone_id):
        if self.is_kids(zone_id):
            return
        now = time.monotonic()
        if now - self._last_cover.get(zone_id, now) < self.options["cover_cooldown"]:
            return
        ids = self.usable("covers", zone_id)
        if not ids:
            return
        entity_id = random.choice(ids)
        attrs = self.hass.states.get(entity_id).attributes
        if attrs.get("device_class") not in ("blind", "curtain", "shade", "shutter"):
            return
        pos = attrs.get("current_position")
        if not isinstance(pos, (int, float)):
            return
        self._last_cover[zone_id] = now
        offset = random.choice([-1, 1]) * self.profile["cover_step"]
        await self.call("cover", "set_cover_position", entity_id, position=max(0, min(100, pos + offset)))

    async def _prop(self, zone_id):
        ids = self.usable("switches", zone_id)
        if not ids:
            return
        entity_id = random.choice(ids)
        before = self.hass.states.get(entity_id).state
        try:
            await self.call("switch", "turn_on", entity_id)
            await self.pause(2)
        finally:
            # Preemption returns the prop to its state before the scene. Stop also restores the session state.
            await self.call("switch", "turn_on" if before == "on" else "turn_off", entity_id)
