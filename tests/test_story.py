"""v3 behavioral tests: stories, branching, preview/test isolation and media."""
import asyncio
from copy import deepcopy
import time
import types
import sys
import unittest
from test_engine import make, State, complete
from haunted_house_test.model import normalize, validate_zone
from haunted_house_test.story import CURRENT_ZONE, CURRENT_SCENE


def two_zones():
    opts = normalize({'lights': ['light.a'], 'media_players': ['media_player.a']})
    opts['zones'][0]['triggers'] = ['binary_sensor.entry']
    opts['zones'][0]['branch_enabled'] = True
    opts['zones'][0]['next_zone'] = 'salon'
    opts['zones'][0]['sound_footsteps'] = 'http://example.test/steps.wav'
    opts['zones'].append(normalize({'lights': ['light.b']})['zones'][0] | {'id': 'salon', 'name': 'Salon', 'triggers': ['binary_sensor.salon']})
    return opts


class StoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_phase_progression_and_ceiling(self):
        engine, hass, states = make({'duration': 10})
        await engine.start()
        now = time.monotonic()
        engine._started_at = now
        self.assertEqual(engine.phase, 'calm')
        calm = engine.zone_profile('maison')['brightness']
        engine._started_at = now - 300
        self.assertEqual(engine.phase, 'rising')
        rising = engine.zone_profile('maison')['brightness']
        engine._started_at = now - 550
        self.assertEqual(engine.phase, 'finale')
        self.assertLess(calm, rising)
        self.assertLess(rising, engine.zone_profile('maison')['brightness'])
        await engine.stop()

    async def test_profile_per_zone_does_not_leak(self):
        opts = two_zones()
        opts['zones'][1]['intensity'] = 'haunted'
        opts['zones'][0]['kids_mode'] = True
        engine, hass, states = make(opts)
        self.assertEqual(engine.zone_profile('maison')['brightness'], 65)
        self.assertEqual(engine.zone_profile('salon')['brightness'], 210)
        await engine.start()
        await engine.effect(zone_id='maison', scene='storm')
        await engine.effect(zone_id='salon', scene='storm')
        await asyncio.gather(*engine._effects.values())
        self.assertEqual(CURRENT_ZONE.get(), None)
        self.assertEqual(CURRENT_SCENE.get(), 'haunted')
        await engine.stop()

    async def test_children_never_fall_back_to_scary_audio_or_video(self):
        opts = normalize({'lights': ['light.a'], 'media_players': ['media_player.a'], 'sounds': 'http://example.test/scary.wav'})
        opts['zones'][0].update(kids_mode=True, videos='http://example.test/scary.mp4', video_players=['media_player.tv'])
        engine, hass, states = make(opts)
        states['media_player.tv'] = State('idle')
        await engine.start()
        await engine.effect(scene='apparition')
        await complete(engine)
        self.assertFalse(any(c[1] == 'play_media' for c in hass.calls))
        self.assertFalse(any(c[0] == 'cover' for c in hass.calls))
        await engine.stop()

    async def test_kids_tts_uses_low_volume(self):
        opts = normalize({'media_players': ['media_player.a']})
        opts['tts_entity'] = 'tts.piper'
        opts['zones'][0]['kids_mode'] = True
        engine, hass, states = make(opts)
        await engine.start()
        await engine.effect(scene='kids')
        await complete(engine)
        self.assertTrue(any(c[0] == 'tts' and c[1] == 'speak' for c in hass.calls))
        self.assertTrue(all(c[2]['volume_level'] <= .12 for c in hass.calls if c[1] == 'volume_set'))
        await engine.stop()

    async def test_scene_sound_bank_wins(self):
        opts = normalize({'media_players': ['media_player.a'], 'sounds': 'http://example.test/default.wav'})
        opts['zones'][0]['sound_storm'] = 'http://example.test/thunder.wav'
        engine, hass, states = make(opts)
        await engine.start()
        await engine.effect(scene='storm')
        await complete(engine)
        self.assertEqual([c[2]['media_content_id'] for c in hass.calls if c[1] == 'play_media'], ['http://example.test/thunder.wav'])
        await engine.stop()

    async def test_empty_bank_falls_back_to_bundled_sound(self):
        network = types.ModuleType('homeassistant.helpers.network')
        network.NoURLAvailableError = type('NoURLAvailableError', (Exception,), {})
        network.get_url = lambda hass, prefer_external=False: 'http://ha.local:8123'
        sys.modules['homeassistant.helpers.network'] = network
        try:
            opts = normalize({'media_players': ['media_player.a']})
            opts['tts_entity'] = 'tts.piper'
            opts['zones'].append(normalize({'media_players': ['media_player.b']})['zones'][0] | {'id': 'kids', 'name': 'Kids', 'kids_mode': True})
            engine, hass, states = make(opts)
            states['media_player.b'] = State('idle', volume_level=.4)
            await engine.start()
            await engine.effect(zone_id='maison', scene='storm')
            await complete(engine)
            urls = [c[2]['media_content_id'] for c in hass.calls if c[1] == 'play_media']
            self.assertEqual(urls, ['http://ha.local:8123/haunted_house_media/thunder.wav'])
            hass.calls.clear()
            await engine.effect(zone_id='kids', scene='kids')
            await complete(engine, 'kids')
            self.assertTrue(any(c[0] == 'tts' for c in hass.calls))  # TTS keeps priority over the bundled chime
            self.assertFalse(any(c[1] == 'play_media' for c in hass.calls))
            await engine.stop()
        finally:
            del sys.modules['homeassistant.helpers.network']

    async def test_none_attributes_are_not_restored_and_discard_unblocks(self):
        engine, hass, states = make({'lights': ['light.a'], 'media_players': ['media_player.a']})
        states['light.a'].attributes['effect'] = None
        states['media_player.a'].attributes['source'] = None
        await engine.start()
        self.assertNotIn('effect', engine.snapshot['light.a']['attributes'])
        self.assertNotIn('source', engine.snapshot['media_player.a']['attributes'])
        await engine.stop()
        self.assertFalse(engine.snapshot)
        # A legacy snapshot with None values is restored without sending them.
        engine.snapshot = {'light.a': {'state': 'on', 'attributes': {'brightness': 10, 'effect': None}}}
        hass.calls.clear()
        await engine._restore()
        self.assertEqual(hass.calls, [('light', 'turn_on', {'entity_id': 'light.a', 'brightness': 10})])
        # A device that always fails keeps the snapshot until it is discarded.
        hass.fail.add('light.a')
        engine.snapshot = {'light.a': {'state': 'on', 'attributes': {}}}
        await engine.stop()
        self.assertTrue(engine.snapshot)
        await engine.discard_restoration()
        self.assertFalse(engine.snapshot)
        self.assertEqual(engine.last_effect, 'idle')

    async def test_ghost_visits_route_in_order(self):
        opts = two_zones()
        opts['ghost_route'] = ['salon', 'maison']
        engine, hass, states = make(opts)
        await engine.start()
        self.assertTrue(await engine.walk())
        await engine._story_task
        self.assertEqual([e['zone_id'] for e in engine.history if e['kind'] == 'ghost_step'], ['salon', 'maison'])
        self.assertFalse(engine._reserved_zones)
        await engine.stop()

    async def test_trigger_preempts_ghost_and_stop_joins_tasks(self):
        engine, hass, states = make(two_zones())
        entered = asyncio.Event()
        async def hold(seconds):
            entered.set()
            await asyncio.Event().wait()
        engine.pause = hold
        await engine.start()
        await engine.walk()
        task = engine._story_task
        await entered.wait()
        await engine.effect(scare=True, zone_id='maison')
        self.assertTrue(task.cancelled())
        self.assertFalse(engine._reserved_zones)
        await engine.stop()
        self.assertTrue(all(t.done() for t in hass.tasks))

    async def test_presence_advances_to_pursuit_branch(self):
        engine, hass, states = make(two_zones())
        await engine.start()
        await engine.handle_event('binary_sensor.entry', State('off'), State('on'))
        await engine.handle_event('binary_sensor.salon', State('off'), State('on'))
        self.assertTrue(any(e['kind'] == 'branch_advance' for e in engine.history))
        self.assertEqual(engine.zone_last_effect['salon'], 'pursuit')
        await engine.stop()

    async def test_departure_plays_retreat_when_no_progress(self):
        engine, hass, states = make(two_zones())
        states['binary_sensor.entry'] = State('off')
        await engine.start()
        await engine.handle_event('binary_sensor.entry', State('on'), State('off'))
        await engine._branch_tasks['maison']
        self.assertTrue(any(e['kind'] == 'branch_retreat' for e in engine.history))
        await engine.stop()

    async def test_departure_cancelled_by_new_presence_revision(self):
        engine, hass, states = make(two_zones())
        states['binary_sensor.entry'] = State('off')
        await engine.start()
        engine._presence_revision = 10
        await engine._departure('maison', 9)
        self.assertFalse(any(e['kind'] == 'branch_retreat' for e in engine.history))
        await engine.stop()

    async def test_manual_reaction_is_opt_in_and_ignores_own_context(self):
        opts = normalize({'lights': ['light.a', 'light.off']})
        opts['zones'][0]['reactive_lights'] = ['light.a']
        engine, hass, states = make(opts)
        await engine.start()
        await engine.handle_event('light.off', State('on'), State('off'))
        self.assertFalse(engine._reaction_tasks)
        own = State('off')
        own.context = types.SimpleNamespace(id=engine._context.id, parent_id=None)
        await engine.handle_event('light.a', State('on'), own)
        self.assertFalse(engine._reaction_tasks)
        await engine.handle_event('light.a', State('on'), State('off'))
        await engine._reaction_tasks['light.a']
        self.assertTrue(any(e['kind'] == 'lamp_answered' for e in engine.history))
        await engine.stop()

    async def test_preview_changes_no_device(self):
        engine, hass, states = make(two_zones())
        preview = engine.preview('salon', 'storm')
        self.assertEqual(preview['entities']['lights'], ['light.b'])
        self.assertFalse(hass.calls)
        self.assertFalse(engine.running)

    async def test_isolated_scene_test_restores_only_target_zone(self):
        engine, hass, states = make(two_zones())
        result = await engine.test_scene('salon', 'storm')
        self.assertEqual(result['outcome'], 'completed')
        self.assertFalse(result['restoration_pending'])
        self.assertFalse(engine.running)
        self.assertTrue(all(c[2]['entity_id'] == 'light.b' for c in hass.calls))

    async def test_scene_test_refuses_active_session(self):
        engine, hass, states = make()
        await engine.start()
        with self.assertRaises(ValueError):
            await engine.test_scene('maison', 'candle')
        self.assertTrue(engine.running)
        await engine.stop()

    async def test_video_power_and_source_restoration(self):
        opts = normalize({'lights': ['light.a']})
        opts['zones'][0].update(video_players=['media_player.tv'], videos='http://example.test/ghost.mp4', video_power_on=True)
        engine, hass, states = make(opts)
        states['media_player.tv'] = State('off', source='HDMI 1', volume_level=.3)
        await engine.start()
        await engine.effect(scene='apparition')
        await complete(engine)
        self.assertIn('media_player.tv', engine._powered_media)
        self.assertTrue(any(c[1] == 'play_media' and c[2].get('media_content_type') == 'video' for c in hass.calls))
        await engine.stop()
        self.assertIn(('media_player', 'turn_off', {'entity_id': 'media_player.tv'}), hass.calls)
        self.assertIn(('media_player', 'select_source', {'entity_id': 'media_player.tv', 'source': 'HDMI 1'}), hass.calls)

    async def test_history_bounded_and_persisted(self):
        engine, hass, states = make()
        for i in range(230):
            engine.record('sample', index=i)
        self.assertEqual(len(engine.history), 200)
        recovered, _, _ = make()
        recovered._history_store.data = deepcopy(engine._history_store.data)
        await recovered.load()
        self.assertEqual(recovered.history[-1]['index'], 229)
        self.assertEqual(len(recovered.history), 200)

    async def test_global_stop_during_isolated_test(self):
        engine, hass, states = make(two_zones())
        entered = asyncio.Event()
        async def hold(seconds):
            entered.set()
            await asyncio.Event().wait()
        engine.pause = hold
        test = asyncio.create_task(engine.test_scene('salon', 'storm'))
        await entered.wait()
        await engine.stop()
        report = await test
        self.assertEqual(report['outcome'], 'cancelled')
        self.assertFalse(engine.snapshot)
        self.assertFalse(engine.running)
        self.assertTrue(all(t.done() for t in hass.tasks))

    def test_reactive_lights_and_duplicate_media_validation(self):
        zone = normalize({'lights': ['light.a'], 'media_players': ['media_player.a']})['zones'][0]
        self.assertEqual(validate_zone(zone | {'reactive_lights': ['light.other']}, []), {'reactive_lights': 'reactive_subset'})
        self.assertEqual(validate_zone(zone | {'video_players': ['media_player.a']}, []), {'video_players': 'duplicate_entity'})
