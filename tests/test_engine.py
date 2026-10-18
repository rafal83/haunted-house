"""Behavior tests against HA API doubles. Full HA installation tests are separate."""
import asyncio
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'custom_components' / 'haunted_house'


def module(name):
    obj = types.ModuleType(name)
    sys.modules[name] = obj
    return obj


module('homeassistant')
module('homeassistant.helpers')
module('homeassistant.core').Context = lambda: types.SimpleNamespace(id="haunted-context", parent_id=None)
module('homeassistant.helpers.dispatcher').async_dispatcher_send = lambda *a: None
module('homeassistant.helpers.entity_registry').async_get = lambda hass: types.SimpleNamespace(async_get=lambda entity: None)


class MemoryStore:
    def __init__(self, *a):
        self.data = None
        self.fail = False

    async def async_load(self):
        return deepcopy(self.data)

    def async_delay_save(self, data_func, delay=0):
        self.data = deepcopy(data_func())

    async def async_save(self, data):
        if self.fail:
            raise OSError('cannot save')
        self.data = deepcopy(data)


module('homeassistant.helpers.storage').Store = MemoryStore
package = module('haunted_house_test')
package.__path__ = [str(ROOT)]
spec = importlib.util.spec_from_file_location('haunted_house_test.engine', ROOT / 'engine.py')
engine_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine_mod)
from haunted_house_test.model import normalize, validate_zone, trigger_fired


class State:
    def __init__(self, state, **attributes):
        self.state, self.attributes = state, attributes


class FakeHA:
    def __init__(self, states):
        self.states = types.SimpleNamespace(get=states.get)
        self.calls = []
        self.events = []
        self.bus = types.SimpleNamespace(async_fire=lambda event, data: self.events.append((event, data)))
        self.fail = set()
        self.services = types.SimpleNamespace(async_call=self.call)
        self.tasks = []

    async def call(self, domain, service, data, **kwargs):
        self.calls.append((domain, service, data))
        if data['entity_id'] in self.fail:
            raise RuntimeError('offline')

    def async_create_background_task(self, coro, name):
        task = asyncio.create_task(coro)
        self.tasks.append(task)
        return task

    def async_create_task(self, coro):
        task = asyncio.create_task(coro)
        self.tasks.append(task)
        return task


async def standby():
    await asyncio.Event().wait()


async def fast_pause(seconds):
    await asyncio.sleep(0)


def make(options=None):
    states = {
        'light.a': State('on', brightness=142, color_mode='rgb', rgb_color=[1, 2, 3], supported_color_modes=['rgb']),
        'light.off': State('off', supported_color_modes=['onoff']),
        'light.b': State('on', brightness=99, color_mode='brightness', supported_color_modes=['brightness']),
        'cover.good': State('open', device_class='shutter', supported_features=4, current_position=80),
        'cover.gate': State('open', device_class='gate', supported_features=4, current_position=100),
        'cover.unknown': State('closed', supported_features=4, current_position=0),
        'switch.prop': State('off'),
        'media_player.a': State('idle', volume_level=.4),
    }
    opts = {'lights': ['light.a', 'light.off'], 'covers': ['cover.good', 'cover.gate', 'cover.unknown'],
            'switches': ['switch.prop'], 'media_players': ['media_player.a'], 'sounds': 'http://example.test/ghost.mp3'}
    opts.update(options or {})
    hass = FakeHA(states)
    engine = engine_mod.HauntedEngine(hass, types.SimpleNamespace(options=opts, entry_id='test'))
    engine._real_run = engine._run
    engine._run = standby
    engine.pause = fast_pause
    return engine, hass, states


async def complete(engine, zone='maison'):
    task = engine._effects.get(zone)
    if task:
        await task


class ModelTests(unittest.TestCase):
    def test_v1_migration(self):
        old = {'lights': ['light.a'], 'duration': 17, 'sounds': 'http://example.test/a.mp3'}
        new = normalize(old)
        self.assertEqual(new['zones'][0]['id'], 'maison')
        self.assertEqual(new['zones'][0]['lights'], ['light.a'])
        self.assertEqual(new['duration'], 17)
        self.assertEqual(new['sounds'], old['sounds'])
        new['zones'][0]['lights'].append('light.b')
        self.assertEqual(old['lights'], ['light.a'])
        self.assertEqual(normalize(new), new)

    def test_duplicate_entity_rejected(self):
        zone = normalize({'lights': ['light.a']})['zones'][0]
        self.assertEqual(validate_zone(zone, [zone]), {'lights': 'duplicate_entity'})
        other = deepcopy(zone)
        other['lights'] = ['light.b']
        self.assertFalse(validate_zone(other, [zone]))

    def test_validation_empty_wrong_domain_bad_audio(self):
        zone = normalize({'lights': ['light.a']})['zones'][0]
        self.assertEqual(validate_zone(zone | {'name': ' '}, []), {'name': 'empty_name'})
        self.assertEqual(validate_zone(zone | {'lights': []}, []), {'base': 'empty_zone'})
        self.assertEqual(validate_zone(zone | {'lights': ['switch.x']}, []), {'lights': 'invalid_entity'})
        self.assertEqual(validate_zone(zone | {'sounds': 'file:///tmp/x'}, []), {'sounds': 'invalid_sound'})
        self.assertEqual(validate_zone(zone | {'scenes': []}, []), {'scenes': 'invalid_scene'})

    def test_triggers_only_on_real_transitions(self):
        self.assertTrue(trigger_fired(State('off'), State('on'), 'binary_sensor.motion'))
        self.assertFalse(trigger_fired(None, State('on'), 'binary_sensor.motion'))
        self.assertFalse(trigger_fired(State('unavailable'), State('on'), 'binary_sensor.motion'))
        self.assertFalse(trigger_fired(State('on'), State('on'), 'binary_sensor.motion'))
        self.assertFalse(trigger_fired(State('on'), State('off'), 'binary_sensor.motion'))
        self.assertTrue(trigger_fired(State('time1'), State('time2'), 'input_button.a'))
        self.assertTrue(trigger_fired(State('time1'), State('time2'), 'event.doorbell'))


class EngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_snapshot_and_stop_restore(self):
        engine, hass, states = make()
        await engine.start()
        task = engine._task
        await engine.start()
        self.assertIs(engine._task, task)
        self.assertNotIn('cover.gate', engine.snapshot)
        self.assertNotIn('cover.unknown', engine.snapshot)
        await engine.stop()
        self.assertFalse(engine.running)
        self.assertFalse(engine.snapshot)
        self.assertIn(('cover', 'set_cover_position', {'entity_id': 'cover.good', 'position': 80}), hass.calls)
        self.assertIn(('light', 'turn_on', {'entity_id': 'light.a', 'brightness': 142, 'rgb_color': [1, 2, 3]}), hass.calls)
        self.assertIn(('light', 'turn_off', {'entity_id': 'light.off'}), hass.calls)
        self.assertFalse(any('gate' in c[2]['entity_id'] for c in hass.calls))

    async def test_restore_failure_retained_then_retry(self):
        engine, hass, states = make()
        await engine.start()
        hass.fail.add('light.a')
        with self.assertLogs(engine_mod.__name__, level='ERROR'):
            await engine.stop()
        self.assertEqual(list(engine.snapshot), ['light.a'])
        with self.assertRaises(ValueError):
            await engine.start()
        hass.fail.clear()
        await engine.stop()
        self.assertFalse(engine.snapshot)

    async def test_scare_rate_limit_and_audio_restore(self):
        engine, hass, states = make()
        await engine.start()
        self.assertTrue(await engine.effect(scare=True))
        self.assertFalse(await engine.effect(scare=True))
        await complete(engine)
        self.assertEqual(sum(c[1] == 'play_media' for c in hass.calls), 1)
        await engine.stop()
        self.assertTrue(any(c[1] == 'media_stop' for c in hass.calls))
        self.assertIn(('media_player', 'volume_set', {'entity_id': 'media_player.a', 'volume_level': .4}), hass.calls)

    async def test_newly_available_entity_not_mutated(self):
        engine, hass, states = make()
        states['light.a'].state = 'unavailable'
        await engine.start()
        states['light.a'].state = 'on'
        self.assertNotIn('light.a', engine.usable('lights'))
        await engine.stop()

    async def test_cover_cooldown_and_intensity(self):
        engine, hass, states = make({'lights': [], 'media_players': [], 'switches': []})
        await engine.start()
        await engine._cover('maison')
        self.assertFalse(hass.calls)
        engine._last_cover['maison'] = 0
        await engine._cover('maison')
        self.assertIn(hass.calls[-1][2]['position'], [75, 85])
        count = len(hass.calls)
        await engine._cover('maison')
        self.assertEqual(len(hass.calls), count)
        await engine.stop()

    async def test_cover_skips_are_explained_and_tests_bypass_cooldown(self):
        engine, hass, states = make({'lights': [], 'media_players': [], 'switches': []})
        await engine.start()
        reasons = {e['entity_id']: e['reason'] for e in engine.history if e['kind'] == 'cover_ignored'}
        self.assertEqual(reasons['cover.gate'], 'device_class_not_blind_curtain_shade_shutter')
        self.assertEqual(reasons['cover.unknown'], 'device_class_not_blind_curtain_shade_shutter')
        await engine._cover('maison')
        self.assertEqual(engine.history[-1]['kind'], 'cover_skipped')
        self.assertEqual(engine.history[-1]['reason'], 'cooldown')
        self.assertFalse(hass.calls)
        engine._testing = True
        await engine._cover('maison')
        self.assertEqual(hass.calls[-1][1], 'set_cover_position')
        await engine.stop()

    async def test_recovery_after_restart(self):
        engine, hass, states = make()
        await engine.start()
        saved = deepcopy(engine._store.data)
        await engine.stop()
        recovered, recovered_hass, _ = make()
        recovered._store.data = saved
        await recovered.load()
        self.assertFalse(recovered.running)
        self.assertEqual(recovered.last_effect, 'recovery_pending')
        with self.assertRaises(ValueError):
            await recovered.start()
        await recovered.stop()
        self.assertFalse(recovered.snapshot)

    async def test_no_eligible_entities(self):
        engine, hass, states = make({'lights': [], 'covers': ['cover.gate'], 'switches': [], 'media_players': []})
        with self.assertRaises(ValueError):
            await engine.start()
        self.assertFalse(hass.calls)

    async def test_persist_failure_prevents_show(self):
        engine, hass, states = make()
        engine._store.fail = True
        with self.assertRaises(OSError):
            await engine.start()
        self.assertFalse(engine.running)
        self.assertFalse(engine.snapshot)
        self.assertFalse(hass.calls)

    async def test_stop_during_prop_effect(self):
        engine, hass, states = make({'lights': [], 'covers': [], 'media_players': []})
        entered = asyncio.Event()
        async def hold(seconds):
            entered.set()
            await asyncio.Event().wait()
        engine.pause = hold
        await engine.start()
        await engine.effect(scene='haunted')
        await entered.wait()
        await engine.stop()
        self.assertFalse(engine.running)
        self.assertEqual(hass.calls[-1][1], 'turn_off')
        self.assertTrue(all(t.done() for t in hass.tasks))

    async def test_preempt_only_target_zone(self):
        opts = normalize({'lights': ['light.a']})
        opts['zones'].append(normalize({'lights': ['light.b']})['zones'][0] | {'id': 'salon', 'name': 'Salon'})
        engine, hass, states = make(opts)
        started = {'maison': asyncio.Event(), 'salon': asyncio.Event()}
        async def hold(zone, scene):
            started[zone].set()
            await asyncio.Event().wait()
        engine._scene = hold
        await engine.start()
        await engine.effect(zone_id='maison')
        await engine.effect(zone_id='salon')
        await started['maison'].wait()
        await started['salon'].wait()
        a, b = engine._effects['maison'], engine._effects['salon']
        await engine.effect(scare=True, zone_id='maison')
        self.assertTrue(a.cancelled())
        self.assertFalse(b.done())
        self.assertIs(engine._effects['salon'], b)
        await engine.stop()

    async def test_zone_isolation_and_zone_sound(self):
        opts = normalize({'lights': ['light.a'], 'media_players': ['media_player.a']})
        opts['zones'][0]['sounds'] = 'http://example.test/zone.mp3'
        opts['zones'].append(normalize({'lights': ['light.b']})['zones'][0] | {'id': 'salon'})
        engine, hass, states = make(opts)
        await engine.start()
        await engine.effect(zone_id='maison', scene='storm')
        await complete(engine)
        self.assertFalse(any(c[2]['entity_id'] == 'light.b' for c in hass.calls))
        plays = [c for c in hass.calls if c[1] == 'play_media']
        self.assertEqual(plays[0][2]['media_content_id'], 'http://example.test/zone.mp3')
        await engine.stop()

    async def test_intensity_caps(self):
        engine, hass, states = make({'volume': .9, 'intensity': 'family'})
        await engine.start()
        await engine.effect(scene='storm')
        await complete(engine)
        self.assertTrue(all(c[2]['brightness'] <= 90 for c in hass.calls if 'brightness' in c[2]))
        self.assertTrue(all(c[2]['volume_level'] <= .2 for c in hass.calls if c[1] == 'volume_set'))
        await engine.stop()

    async def test_all_scenes_execute_and_restore(self):
        for scene in engine_mod.SCENES:
            with self.subTest(scene=scene):
                engine, hass, states = make()
                await engine.start()
                await engine.effect(scene=scene)
                await complete(engine)
                self.assertEqual(engine.errors, 0)
                self.assertTrue(hass.calls)
                await engine.stop()
                self.assertFalse(engine.snapshot)

    async def test_invalid_requests_and_inactive_triggers(self):
        engine, hass, states = make()
        self.assertFalse(await engine.effect(scare=True))
        await engine.start()
        with self.assertRaises(ValueError):
            await engine.effect(zone_id='missing')
        with self.assertRaises(ValueError):
            await engine.effect(scene='invalid')
        await engine.stop()

    async def test_automatic_timeout_cancels_and_restores(self):
        engine, hass, states = make({'duration': .0001})
        engine._run = engine._real_run
        await engine.start()
        await asyncio.sleep(.03)
        await asyncio.gather(*(t for t in hass.tasks if not t.done()))
        self.assertFalse(engine.running)
        self.assertFalse(engine.snapshot)

    async def test_scene_failure_cancels_siblings(self):
        engine, hass, states = make()
        cleaned = asyncio.Event()
        async def failing_sound(zone):
            await asyncio.sleep(0)
            raise OSError('save failed')
        async def slow_prop(zone):
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()
        engine._sound, engine._prop = failing_sound, slow_prop
        await engine.start()
        with self.assertLogs(engine_mod.__name__, level='ERROR'):
            await engine.effect(scene='haunted')
            await complete(engine)
        self.assertTrue(cleaned.is_set())
        self.assertEqual(engine.errors, 1)
        await engine.stop()


if __name__ == '__main__':
    unittest.main()
