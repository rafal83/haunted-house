"""Narrative, reactions, media and preview/test features for the v3 engine."""
import asyncio
from contextvars import ContextVar
from datetime import datetime, timezone
import random
import time
from homeassistant.helpers.storage import Store
from .const import BUNDLED_AUDIO, ENTITY_KEYS, INTENSITIES, MEDIA_URL_PATH, SCENES
from .model import trigger_fired

CURRENT_ZONE = ContextVar("haunted_zone", default=None)
CURRENT_SCENE = ContextVar("haunted_scene", default="haunted")
WALK_SOUND = ContextVar("haunted_walk_sound", default="footsteps")


class StoryFeatures:
    def init_story(self):
        self._story_task = None
        self._reserved_zones = set()
        self._branch_tasks = {}
        self._reaction_tasks = {}
        self._last_reaction = {}
        self._presence_revision = 0
        self._last_presence = None
        self._started_at = 0
        self._last_walk = 0
        self._testing = False
        self._test_lock = asyncio.Lock()
        self._powered_media = set()
        self._video_media = set()
        self.history = []
        self.last_preview = {}
        self._history_store = Store(self.hass, 1, f"haunted_house.{self.entry.entry_id}.history")

    def record(self, kind, **details):
        event = {"time": datetime.now(timezone.utc).isoformat(), "kind": kind, **details}
        self.history = (self.history + [event])[-200:]
        self._history_store.async_delay_save(lambda: {"events": self.history}, 3)
        self.hass.bus.async_fire("haunted_house_event", event)
        self.notify()

    @property
    def phase(self):
        if not self.running:
            return "idle"
        if self._testing or not self.options["progression"]:
            return "steady"
        fraction = (time.monotonic() - self._started_at) / max(1, self.options["duration"] * 60)
        return "calm" if fraction < .4 else "rising" if fraction < .8 else "finale"

    def zone_profile(self, zone_id=None):
        zone = self.zones.get(zone_id or CURRENT_ZONE.get(), {})
        name = zone.get("intensity", "inherit")
        name = self.options["intensity"] if name == "inherit" else name
        if zone.get("kids_mode") or CURRENT_SCENE.get() == "kids":
            name = "kids"
        profile = dict(INTENSITIES[name])
        scale = {"calm": .45, "rising": .75}.get(self.phase, 1)
        profile["brightness"] = round(profile["brightness"] * scale)
        profile["volume"] *= scale
        return profile

    def is_kids(self, zone_id):
        zone = self.zones[zone_id]
        profile = zone["intensity"] if zone["intensity"] != "inherit" else self.options["intensity"]
        return zone["kids_mode"] or profile == "kids" or CURRENT_SCENE.get() == "kids"

    def preview(self, zone_id, scene):
        if zone_id not in self.zones or scene not in SCENES:
            raise ValueError("Unknown zone or scene")
        zone = self.zones[zone_id]
        effective = "kids" if self.is_kids(zone_id) else scene
        self.last_preview = {
            "zone_id": zone_id, "zone_name": zone["name"], "scene": scene,
            "effective_scene": effective, "profile": dict(INTENSITIES["kids"]) if effective == "kids" else self.zone_profile(zone_id),
            "entities": {k: list(zone[k]) for k in ENTITY_KEYS},
            "unavailable": [e for k in ENTITY_KEYS for e in zone[k]
                            if not self.hass.states.get(e) or self.hass.states.get(e).state in ("unknown", "unavailable")],
            "reactive_lights": zone["reactive_lights"], "maximum_test_seconds": 20,
            "audio_restoration": "volume_only", "requires_idle_session": True,
        }
        self.notify()
        return self.last_preview

    async def test_scene(self, zone_id, scene):
        """Isolated session; a global stop cancels its tracked scene and restores."""
        async with self._test_lock:
            if self.running or self.snapshot:
                raise ValueError("Stop and restore the current session before testing")
            preview = self.preview(zone_id, scene)
            errors = self.errors
            await self.start(test_zone=zone_id)
            outcome = "completed"
            try:
                await self.effect(zone_id=zone_id, scene=scene, source="test")
                task = self._effects[zone_id]
                async with asyncio.timeout(20):
                    await task
            except TimeoutError:
                outcome = "timeout"
            except asyncio.CancelledError:
                outcome = "cancelled"
            finally:
                await self.stop()
            if outcome == "completed" and self.errors > errors:
                outcome = "partial_failure"
            report = {"outcome": outcome, "preview": preview, "errors": self.errors - errors,
                      "restoration_pending": bool(self.snapshot)}
            self.record("test_finished", zone_id=zone_id, scene=scene,
                        outcome=outcome, errors=report["errors"], restoration_pending=bool(self.snapshot))
            return report

    async def walk(self, zone_ids=None):
        route = list(zone_ids or self.options["ghost_route"] or self.zones)
        if not route or any(z not in self.zones for z in route) or len(route) != len(set(route)):
            raise ValueError("Invalid ghost route")
        async with self._lock:
            if not self.running or self._testing or (self._story_task and not self._story_task.done()):
                return False
            tasks = [self._effects[z] for z in route if z in self._effects and not self._effects[z].done()]
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            self._reserved_zones = set(route)
            self._last_walk = time.monotonic()
            self.record("ghost_started", route=route)
            self._story_task = self.hass.async_create_background_task(self._walk(route), "Haunted House ghost route")
            return True

    async def _walk(self, route):
        try:
            for index, zone_id in enumerate(route):
                tag = "footsteps" if index == 0 else "knock" if index == len(route) - 1 else "whisper"
                self.last_zone = zone_id
                self.zone_last_effect[zone_id] = "ghost_walk"
                self.record("ghost_step", zone_id=zone_id, audio_tag=tag)
                token = WALK_SOUND.set(tag)
                try:
                    await self._scene(zone_id, "walk_step")
                finally:
                    WALK_SOUND.reset(token)
            self.record("ghost_finished", route=route)
        except asyncio.CancelledError:
            self.record("ghost_cancelled", route=route)
            raise
        finally:
            self._reserved_zones.clear()
            self.notify()

    async def handle_event(self, entity_id, old, new):
        if not self.running or self._testing:
            return
        for zone_id, zone in self.zones.items():
            if entity_id in zone["reactive_lights"] and old and new and old.state == "on" and new.state == "off":
                context = getattr(new, "context", None)
                if context and (context.id == self._context.id or context.parent_id == self._context.id):
                    continue
                if time.monotonic() - self._last_reaction.get(entity_id, float('-inf')) >= self.options["trigger_cooldown"]:
                    self._last_reaction[entity_id] = time.monotonic()
                    task = self._reaction_tasks.get(entity_id)
                    if task and not task.done():
                        task.cancel()
                        await asyncio.gather(task, return_exceptions=True)
                    self.record("reaction_scheduled", zone_id=zone_id, entity_id=entity_id)
                    self._reaction_tasks[entity_id] = self.hass.async_create_background_task(
                        self._react(zone_id, entity_id), "Haunted House lamp response")
            if entity_id not in zone["triggers"]:
                continue
            if trigger_fired(old, new, entity_id):
                self._presence_revision += 1
                previous = self._last_presence
                self._last_presence = (zone_id, time.monotonic())
                branch_scene = None
                if previous and previous[0] in self.zones:
                    previous_zone = self.zones[previous[0]]
                    if (previous_zone["branch_enabled"] and previous_zone["next_zone"] == zone_id
                            and time.monotonic() - previous[1] <= self.options["branch_window"]):
                        branch_scene = "pursuit"
                        self.record("branch_advance", from_zone=previous[0], zone_id=zone_id, trigger=entity_id)
                await self.effect(scare=True, zone_id=zone_id, scene=branch_scene, source=entity_id)
            elif (zone["branch_enabled"] and entity_id.startswith("binary_sensor.") and old and new
                  and old.state == "on" and new.state == "off"):
                previous = self._branch_tasks.get(zone_id)
                if previous and not previous.done():
                    previous.cancel()
                    await asyncio.gather(previous, return_exceptions=True)
                self._branch_tasks[zone_id] = self.hass.async_create_background_task(
                    self._departure(zone_id, self._presence_revision), "Haunted House departure branch")

    async def _react(self, zone_id, entity_id):
        token = CURRENT_ZONE.set(zone_id)
        try:
            await self.pause(2)
            if self.running and entity_id in self.snapshot:
                await self._light(entity_id, (255, 110, 20) if self.is_kids(zone_id) else (100, 0, 150), .35)
                self.record("lamp_answered", zone_id=zone_id, entity_id=entity_id)
        finally:
            CURRENT_ZONE.reset(token)

    async def _departure(self, zone_id, revision):
        await self.pause(self.options["branch_window"])
        if not self.running or revision != self._presence_revision:
            return
        zone = self.zones[zone_id]
        # Do not treat a momentary door closure as an empty room if another presence sensor remains on.
        if any((s := self.hass.states.get(e)) and s.state == "on" for e in zone["triggers"] if e.startswith("binary_sensor.")):
            return
        target = zone["return_zone"] or zone_id
        if target not in self.zones:
            return
        self.record("branch_retreat", from_zone=zone_id, zone_id=target)
        await self.effect(scare=True, zone_id=target, scene="retreat", source="departure")

    def audio_urls(self, zone_id, tag):
        zone = self.zones[zone_id]
        if self.is_kids(zone_id) or tag == "kids":
            text = zone["sound_kids"]  # Never fall back to a frightening bank for children.
        else:
            text = zone.get(f"sound_{tag}", "").strip() or zone["sounds"].strip() or self.options["sounds"]
        return [line.strip() for line in text.splitlines() if line.strip()]

    def bundled_url(self, name):
        """URL of a sound shipped with the integration, or None when no HA base URL is available."""
        if not name:
            return None
        try:  # Imported lazily so the module stays importable outside a full HA install.
            from homeassistant.helpers.network import NoURLAvailableError, get_url
        except ImportError:
            return None
        try:
            return f"{get_url(self.hass, prefer_external=False)}{MEDIA_URL_PATH}/{name}.wav"
        except NoURLAvailableError:
            return None

    async def _play_audio(self, zone_id, tag, entity_id=None):
        ids = self.usable("media_players", zone_id)
        if not ids:
            return
        entity_id = entity_id or random.choice(ids)
        urls = self.audio_urls(zone_id, tag)
        kids = self.is_kids(zone_id) or tag == "kids"
        messages = [s.strip() for s in self.options["kids_messages"].splitlines() if s.strip()]
        tts = kids and self.options["tts_entity"] and messages
        if not urls and not tts:
            bundled = self.bundled_url(BUNDLED_AUDIO.get(tag))
            urls = [bundled] if bundled else []
        if not urls and not tts:
            return
        self._touched_media.add(entity_id)
        await self.save()
        await self.call("media_player", "volume_set", entity_id,
                        volume_level=min(self.options["volume"], self.profile["volume"]))
        if urls:
            await self.call("media_player", "play_media", entity_id,
                            media_content_id=random.choice(urls), media_content_type="music")
        else:
            await self.call("tts", "speak", self.options["tts_entity"],
                            media_player_entity_id=entity_id, message=random.choice(messages))

    async def _spatial(self, zone_id):
        ids = self.usable("media_players", zone_id)
        if self.is_kids(zone_id):
            await self._play_audio(zone_id, "kids")
            return
        for index, tag in enumerate(["footsteps", "whisper", "knock"]):
            if not ids:
                return
            entity_id = ids[index % len(ids)]
            await self._play_audio(zone_id, tag, entity_id)
            await self.pause(2)
            if entity_id in self._touched_media:
                await self.call("media_player", "media_stop", entity_id)

    async def _video(self, zone_id):
        zone = self.zones[zone_id]
        text = zone["kids_videos"] if self.is_kids(zone_id) else zone["videos"]
        urls = [s.strip() for s in text.splitlines() if s.strip()]
        ids = self.usable("video_players", zone_id)
        if not urls or not ids:
            return
        entity_id = random.choice(ids)
        state = self.hass.states.get(entity_id)
        if state.state == "off" and not zone["video_power_on"]:
            self.record("video_skipped", zone_id=zone_id, entity_id=entity_id, reason="power_on_disabled")
            return
        self._touched_media.add(entity_id)
        self._video_media.add(entity_id)
        if state.state == "off":
            self._powered_media.add(entity_id)
        await self.save()
        if state.state == "off":
            if not await self.call("media_player", "turn_on", entity_id):
                return
            await self.pause(2)
        try:
            await self.call("media_player", "play_media", entity_id,
                            media_content_id=random.choice(urls), media_content_type="video")
            await self.pause(6)
        finally:
            await self.call("media_player", "media_stop", entity_id)
