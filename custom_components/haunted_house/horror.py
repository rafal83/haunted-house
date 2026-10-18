"""Frightening light choreography: irregular flicker, blackouts, lightning and jump flashes.

Safety: every light changes at most about three times per second (gaps of 0.3 s or more),
lights are never driven in a regular on/off pattern, and children's zones never use these scenes.
"""
import asyncio
import random
from .story import WALK_SOUND

WHITE = (215, 230, 255)
BLOOD = (255, 0, 0)


class HorrorEffects:
    @property
    def fear(self):
        return self.profile.get("fear", 1)

    async def _blackout(self, zone_id, seconds):
        await asyncio.gather(*(self._light(e, (0, 0, 0), 0, 0) for e in self.usable("lights", zone_id)))
        await self.pause(seconds)

    async def _flash(self, zone_id, color, level=1.0):
        await self._lights(zone_id, color, level, transition=0)

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

    async def _scare_scene(self, zone_id, scene):
        """Scenes that need the frightening choreography; returns False for any other scene."""
        f = self.fear
        if scene == "candle":
            await self._lights(zone_id, (255, 70, 0), .5)
            await self._parallel(self._flicker(zone_id, (255, 70, 0), 3 + 2 * f, low=(0, .2), high=(.3, .7)),
                                 self._sound(zone_id))
            await self._blackout(zone_id, 1 + .5 * f)
            await self._lights(zone_id, (200, 20, 0), .12)
        elif scene == "graveyard":
            await self._lights(zone_id, (0, 100, 60), .25)
            await self._parallel(self._sound(zone_id),
                                 self._flicker(zone_id, (0, 120, 70), 2 + 2 * f, gap=(.4, 1.0)))
            await self._blackout(zone_id, 1.5 + .5 * f)
            await self._flash(zone_id, WHITE, .9)
            await self.pause(.25)
            await self._lights(zone_id, (15, 25, 160), .15)
        elif scene == "storm":
            await self._lights(zone_id, (20, 30, 100), .1)
            await self.pause(1)
            await self._lightning(zone_id, 1 + (f > 1) + (f > 2))
            if f > 1:
                await self._blackout(zone_id, 1.5)
            await self._lights(zone_id, (20, 30, 100), .12)
        elif scene == "apparition":
            await self._lights(zone_id, (90, 0, 150), .12)
            await self._parallel(self._play_audio(zone_id, "whisper"),
                                 self._flicker(zone_id, (90, 0, 150), 3 + 2 * f, low=(0, .25), high=(.3, .8), gap=(.3, .7)))
            await self._blackout(zone_id, 1.5 + .5 * f)
            await self._flash(zone_id, BLOOD, 1.0)
            await self._parallel(self._sound(zone_id), self._cover(zone_id), self._prop(zone_id),
                                 self._video(zone_id),
                                 self._flicker(zone_id, BLOOD, 2 + f, low=(0, .3), high=(.5, 1.0), gap=(.3, .5)))
            await self._lights(zone_id, (90, 0, 150), .15)
        elif scene == "haunted":
            await self._parallel(self._flicker(zone_id, (255, 30, 0), 5 + 3 * f, gap=(.3, .8)),
                                 self._sound(zone_id), self._prop(zone_id), self._video(zone_id))
            await self._blackout(zone_id, 2)
            await self._flash(zone_id, BLOOD, 1.0)
            await self._parallel(self._play_audio(zone_id, "scream"),
                                 self._flicker(zone_id, (180, 0, 0), 3 + f, low=(0, .2), high=(.6, 1.0), gap=(.3, .45)))
            await self._lights(zone_id, (90, 0, 0), .15)
        elif scene == "spatial":
            await self._parallel(self._flicker(zone_id, (70, 0, 100), 4 + f, low=(0, .3), high=(.3, .6)),
                                 self._spatial(zone_id))
        elif scene == "walk_step":
            await self._lights(zone_id, (20, 130, 80), .5)
            await self._parallel(self._flicker(zone_id, (20, 130, 80), 2 + f, low=(0, .3), high=(.4, .7)),
                                 self._play_audio(zone_id, WALK_SOUND.get()))
            await self.pause(3)
            for entity_id in self.usable("media_players", zone_id):
                if entity_id in self._touched_media:
                    await self.call("media_player", "media_stop", entity_id)
            await self._lights(zone_id, (30, 0, 90), .1)
        elif scene == "pursuit":
            await self._lights(zone_id, (0, 140, 60), .6)
            await self._parallel(self._play_audio(zone_id, "footsteps"),
                                 self._flicker(zone_id, (0, 140, 60), 3 + f, low=(0, .3), high=(.4, .8)))
            await self._play_audio(zone_id, "knock")
            await self._blackout(zone_id, 1 + .3 * f)
            await self._lights(zone_id, (80, 0, 140), .2)
        elif scene == "retreat":
            await self._parallel(self._flicker(zone_id, BLOOD, 3 + f, low=(0, .25), high=(.4, .9)),
                                 self._play_audio(zone_id, "laugh"))
            await self._lights(zone_id, (90, 0, 140), .2)
        else:
            return False
        return True
