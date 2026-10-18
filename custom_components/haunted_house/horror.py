"""Frightening choreography. Every scene has its own signature and only uses the devices that fit it.

Safety: every light changes at most about three times per second (gaps of 0.3 s or more),
lights are never driven in a regular on/off pattern, and children's zones never use these scenes.

| Scene        | Signature                                                       | Devices              |
|--------------|-----------------------------------------------------------------|----------------------|
| candle       | Flames dying out, in silence                                    | lights               |
| graveyard    | Cold green mist, whispers and breath, no flicker                | lights + sound       |
| storm        | Lightning, then thunder                                         | lights + sound       |
| apparition   | Build-up, darkness, red flash, scream: the big jump scare       | everything           |
| haunted      | Oppressive red breathing glow, growls, props: never a scream    | lights, sound, TV    |
| spatial      | Someone walks through the house                                 | sound only           |
| pursuit      | Footsteps close in while the lights go out one by one           | sound + lights       |
| retreat      | A laugh right behind you                                        | sound (+ one lamp)   |
| blackout     | Power cut: darkness, a creak in the dark, the lights stutter on | lights + sound       |
| whispers     | Voices in the walls                                             | sound only           |
| knocks       | Someone is knocking                                             | sound only           |
| poltergeist  | Objects move by themselves                                      | props, covers, sound |
| screen       | The TV shows something it should not                            | TV only              |
"""
import asyncio
import random
from .story import WALK_SOUND

WHITE = (215, 230, 255)
BLOOD = (255, 0, 0)

# At least one of these device groups must be configured for a scene to be worth drawing at random.
SCENE_NEEDS = {
    "candle": ("lights",), "graveyard": ("media_players", "lights"), "storm": ("lights", "media_players"),
    "apparition": ("lights", "media_players", "video_players"), "haunted": ("lights", "media_players", "video_players"),
    "spatial": ("media_players",), "pursuit": ("media_players", "lights"), "retreat": ("media_players",),
    "blackout": ("lights",), "whispers": ("media_players",), "knocks": ("media_players",),
    "poltergeist": ("switches", "covers"), "screen": ("video_players",), "kids": ("lights", "media_players"),
}


class HorrorEffects:
    @property
    def fear(self):
        return self.profile.get("fear", 1)

    def scene_feasible(self, zone, scene):
        return any(zone.get(key) for key in SCENE_NEEDS.get(scene, ("lights", "media_players")))

    async def _blackout(self, zone_id, seconds):
        await asyncio.gather(*(self._light(e, (0, 0, 0), 0, 0) for e in self.usable("lights", zone_id)))
        await self.pause(seconds)

    async def _flash(self, zone_id, color, level=1.0):
        await self._lights(zone_id, color, level, transition=0)

    async def _after(self, delay, coro):
        await self.pause(delay)
        await coro

    async def _flicker(self, zone_id, color, steps, low=(0, .25), high=(.5, 1.0), gap=(.3, .9), dips=.6):
        """Each light flickers on its own random sequence, so the room never pulses in sync."""
        async def one(entity_id):
            for _ in range(steps):
                if random.random() < dips:
                    level = 0 if random.random() < .25 else random.uniform(*low)
                else:
                    level = random.uniform(*high)
                await self._light(entity_id, color, level, 0)
                await self.pause(random.uniform(*gap))
        await asyncio.gather(*(one(e) for e in self.usable("lights", zone_id)))

    async def _breathe(self, zone_id, color, cycles, high=.55, low=.1):
        """A slow swell and fade, like the house breathing."""
        for _ in range(cycles):
            await self._lights(zone_id, color, high, transition=1.5)
            await self.pause(1.7)
            await self._lights(zone_id, color, low, transition=1.5)
            await self.pause(1.7)

    async def _graveyard_mist(self, zone_id, waves):
        """Cold green light that slowly swells and ebbs; steady, never flickering."""
        for _ in range(waves):
            await self._lights(zone_id, (0, 120, 70), .35, transition=2)
            await self.pause(2.2)
            await self._lights(zone_id, (10, 40, 90), .12, transition=2)
            await self.pause(2.2)

    async def _lights_out_one_by_one(self, zone_id, seconds):
        ids = self.usable("lights", zone_id)
        random.shuffle(ids)
        for entity_id in ids:
            await self._light(entity_id, (0, 0, 0), 0, 0)
            await self.pause(seconds / max(1, len(ids)))
        if not ids:
            await self.pause(seconds)

    async def _lightning(self, zone_id, strikes):
        for strike in range(strikes):
            await self._flash(zone_id, WHITE, 1.0)
            await self.pause(.12)
            await self._lights(zone_id, (20, 30, 100), .06, transition=0)
            await self.pause(.3)
            await self._flash(zone_id, WHITE, .8)
            await self.pause(.15)
            await self._lights(zone_id, (20, 30, 100), .08, transition=0)
            if strike == 0:
                await self._sound(zone_id)
            await self.pause(random.uniform(1.2, 2.0))

    async def _two_speakers(self, zone_id, tag, gap):
        """The same kind of sound from two different speakers, a moment apart."""
        ids = self.usable("media_players", zone_id)
        random.shuffle(ids)
        await self._play_audio(zone_id, tag, ids[0] if ids else None)
        await self.pause(gap)
        await self._play_audio(zone_id, tag, ids[1] if len(ids) > 1 else None)

    async def _scare_scene(self, zone_id, scene):
        """Run one scene; returns False for a scene this mixin does not know."""
        f = self.fear
        if scene == "candle":  # silent, lights only
            await self._lights(zone_id, (255, 70, 0), .45)
            await self._flicker(zone_id, (255, 70, 0), 4 + 2 * f, low=(0, .2), high=(.25, .6), gap=(.35, .9))
            await self._lights(zone_id, (160, 20, 0), .06, transition=3)
            await self.pause(3)
            if f > 1:
                await self._blackout(zone_id, 1.5)
            await self._lights(zone_id, (200, 20, 0), .1, transition=2)
        elif scene == "graveyard":  # cold mist and voices, no flicker, no flash
            await self._lights(zone_id, (0, 100, 60), .15, transition=2)
            await self._parallel(self._sound(zone_id), self._graveyard_mist(zone_id, 2 + (f > 1)))
        elif scene == "storm":  # lightning, then thunder
            await self._lights(zone_id, (20, 30, 100), .1)
            await self.pause(1)
            await self._lightning(zone_id, 1 + (f > 1) + (f > 2))
            if f > 1:
                await self._blackout(zone_id, 1.5)
            await self._lights(zone_id, (20, 30, 100), .12)
        elif scene == "apparition":  # the big jump scare
            await self._lights(zone_id, (90, 0, 150), .12)
            await self._parallel(self._play_audio(zone_id, "whisper"),
                                 self._flicker(zone_id, (90, 0, 150), 3 + 2 * f, low=(0, .25), high=(.3, .8), gap=(.3, .7)))
            await self._blackout(zone_id, 1.5 + .5 * f)
            await self._flash(zone_id, BLOOD, 1.0)
            await self._parallel(self._sound(zone_id), self._cover(zone_id), self._prop(zone_id),
                                 self._video(zone_id),
                                 self._flicker(zone_id, BLOOD, 2 + f, low=(0, .3), high=(.5, 1.0), gap=(.3, .5)))
            await self._lights(zone_id, (90, 0, 150), .15)
        elif scene == "haunted":  # oppression, never a scream
            await self._parallel(self._breathe(zone_id, (170, 0, 0), 2 + (f > 2)),
                                 self._sound(zone_id), self._prop(zone_id), self._video(zone_id))
            await self._lights(zone_id, (60, 0, 0), .1, transition=2)
        elif scene == "spatial":  # sound only
            await self._spatial(zone_id)
        elif scene == "pursuit":  # footsteps close in while the lights die one by one
            await self._parallel(self._play_audio(zone_id, "footsteps"), self._lights_out_one_by_one(zone_id, 4))
            await self._play_audio(zone_id, "knock")
            await self.pause(2)
        elif scene == "retreat":  # a laugh right behind you
            await self._play_audio(zone_id, "laugh")
            ids = self.usable("lights", zone_id)
            if ids:
                lamp = random.choice(ids)
                for level in (0, .5, 0, .3):
                    await self._light(lamp, BLOOD, level, 0)
                    await self.pause(random.uniform(.3, .5))
            await self.pause(2)
        elif scene == "blackout":  # power cut
            await self._parallel(self._blackout(zone_id, 3 + f), self._after(1.2, self._play_audio(zone_id, "creak")))
            await self._flicker(zone_id, (255, 200, 140), 2 + f, low=(0, .3), high=(.4, .9), gap=(.3, .6), dips=.5)
        elif scene == "whispers":  # voices in the walls
            await self._two_speakers(zone_id, "whisper", 2.5)
            await self.pause(2)
        elif scene == "knocks":  # someone is knocking
            await self._play_audio(zone_id, "knock")
            await self.pause(3.5)
            await self._play_audio(zone_id, "knock")
            await self.pause(2)
        elif scene == "poltergeist":  # objects move by themselves
            await self._parallel(self._play_audio(zone_id, "knock"), self._prop(zone_id),
                                 self._cover(zone_id, force=True, step=max(20, self.profile["cover_step"])))
            await self.pause(1)
            await self._parallel(self._after(.5, self._play_audio(zone_id, "creak")), self._prop(zone_id))
        elif scene == "screen":  # the TV shows something it should not
            await self._video(zone_id)
        elif scene == "walk_step":  # ghost walk: one step per room
            await self._lights(zone_id, (20, 130, 80), .5)
            await self._parallel(self._flicker(zone_id, (20, 130, 80), 2 + f, low=(0, .3), high=(.4, .7)),
                                 self._play_audio(zone_id, WALK_SOUND.get()))
            await self.pause(3)
            for entity_id in self.usable("media_players", zone_id):
                if entity_id in self._touched_media:
                    await self.call("media_player", "media_stop", entity_id)
            await self._lights(zone_id, (30, 0, 90), .1)
        else:
            return False
        return True
