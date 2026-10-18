"""v3 behavioral tests: stories, branching, preview/test isolation and media."""
import asyncio
from copy import deepcopy
import time
import types
import unittest
from test_engine import make, State, complete, engine_mod
from haunted_house_test.model import normalize, validate_zone
from haunted_house_test.story import CURRENT_ZONE, CURRENT_SCENE


def two_zones():
    opts = normalize({'lights': ['light.a'], 'media_players': ['media_player.a']})
    opts['zones'][0]['triggers'] = ['binary_sensor.entry']
    opts['zones'][0]['branch_enabled'] = True
    opts['zones'][0]['next_zone'] = 'salon'
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

    async def test_children_only_get_the_gentle_chime_and_pumpkin(self):
        opts = normalize({'lights': ['light.a'], 'media_players': ['media_player.a']})
        opts['zones'][0].update(kids_mode=True, video_players=['media_player.tv'], video_power_on=True)
        engine, hass, states = make(opts)
        states['media_player.tv'] = State('idle')
        await engine.start()
        await engine.effect(scene='apparition')
        await complete(engine)
        played = [c[2]['media_content_id'] for c in hass.calls if c[1] == 'play_media']
        self.assertEqual(sorted(p.rsplit('/', 1)[1] for p in played), ['kids.mp4', 'kids.wav'])
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

    async def test_scene_uses_its_bundled_sound(self):
        opts = normalize({'media_players': ['media_player.a']})
        engine, hass, states = make(opts)
        await engine.start()
        await engine.effect(scene='storm')
        await complete(engine)
        self.assertEqual([c[2]['media_content_id'] for c in hass.calls if c[1] == 'play_media'],
                         ['http://ha.local:8123/haunted_house_media/thunder.wav'])
        await engine.stop()

    async def test_screams_only_from_the_frightening_profiles(self):
        for intensity, harsh in (('family', False), ('haunted', True)):
            opts = normalize({'media_players': ['media_player.a'], 'intensity': intensity})
            engine, hass, states = make(opts)
            await engine.start()
            names = {engine.bundled_audio_url('scream').rsplit('/', 1)[1] for _ in range(40)}
            self.assertEqual(any(n.startswith('scream') for n in names), harsh)
            await engine.stop()

    async def test_kids_tts_beats_the_bundled_chime(self):
        opts = normalize({'media_players': ['media_player.a']})
        opts['tts_entity'] = 'tts.piper'
        opts['zones'][0]['kids_mode'] = True
        engine, hass, states = make(opts)
        await engine.start()
        await engine.effect(zone_id='maison', scene='kids')
        await complete(engine)
        self.assertTrue(any(c[0] == 'tts' for c in hass.calls))
        self.assertFalse(any(c[1] == 'play_media' for c in hass.calls))
        await engine.stop()

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
        states['light.a'].attributes['brightness'] = 10  # the bulb obeys, so no retry is needed
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

    async def test_chosen_scene_overrides_trigger_scene_for_tests(self):
        engine, hass, states = make({'lights': ['light.a']})
        self.assertEqual(engine.chosen_scene('maison'), engine.zones['maison']['trigger_scene'])
        engine.choose_scene('maison', 'storm')
        self.assertEqual(engine.chosen_scene('maison'), 'storm')
        with self.assertRaises(ValueError):
            engine.choose_scene('maison', 'nope')
        report = await engine.test_scene('maison', engine.chosen_scene('maison'))
        self.assertEqual(report['preview']['scene'], 'storm')

    async def test_lights_return_to_normal_between_scenes_when_enabled(self):
        for enabled in (True, False):
            engine, hass, states = make({'lights': ['light.a'], 'restore_between_scenes': enabled})
            await engine.start()
            await engine.effect(scene='candle')
            await complete(engine)
            last = [c for c in hass.calls if c[0] == 'light'][-1]
            restored = last[2].get('brightness') == 142 and last[2].get('rgb_color') == [1, 2, 3]
            self.assertEqual(restored, enabled)
            self.assertTrue(engine.running)
            await engine.stop()

    async def test_player_that_refuses_video_is_left_alone_and_not_retried(self):
        opts = normalize({'lights': ['light.a']})
        opts['zones'][0].update(video_players=['media_player.tv'])
        engine, hass, states = make(opts)
        states['media_player.tv'] = State('idle', volume_level=.3)
        hass.fail.add('media_player.tv')
        await engine.start()
        with self.assertLogs(engine_mod.__name__, level='ERROR'):
            await engine._video('maison')
        self.assertNotIn('media_player.tv', engine._touched_media)
        self.assertEqual(engine.history[-1]['reason'], 'player_refused_video')
        count = len(hass.calls)
        await engine._video('maison')
        self.assertEqual(len(hass.calls), count)  # no second attempt, no media_stop
        await engine.stop()
        self.assertFalse(any(c[1] == 'media_stop' and c[2]['entity_id'] == 'media_player.tv' for c in hass.calls))

    async def test_video_falls_back_to_plain_video_type(self):
        opts = normalize({'lights': ['light.a']})
        opts['zones'][0].update(video_players=['media_player.tv'])
        engine, hass, states = make(opts)
        states['media_player.tv'] = State('idle')
        original = hass.services.async_call

        async def picky(domain, service, data, **kwargs):
            if data.get('media_content_type') == 'video/mp4':
                raise RuntimeError('mime not accepted')
            await original(domain, service, data, **kwargs)
        hass.services.async_call = picky
        await engine.start()
        with self.assertLogs(engine_mod.__name__, level='ERROR'):
            await engine._video('maison')
        plays = [c for c in hass.calls if c[1] == 'play_media']
        self.assertEqual([c[2]['media_content_type'] for c in plays], ['video'])
        self.assertEqual(engine._video_type['media_player.tv'], 'video')
        await engine.stop()

    async def test_sound_only_scenes_leave_the_lights_alone(self):
        for scene in ('spatial', 'whispers', 'knocks'):
            with self.subTest(scene=scene):
                engine, hass, states = make({'lights': ['light.a'], 'media_players': ['media_player.a']})
                await engine.start()
                await engine.effect(scene=scene)
                await complete(engine)
                self.assertFalse([c for c in hass.calls if c[0] == 'light'])
                self.assertTrue([c for c in hass.calls if c[1] == 'play_media'])
                await engine.stop()

    async def test_candle_is_silent_and_pursuit_turns_lights_off(self):
        engine, hass, states = make({'lights': ['light.a'], 'media_players': ['media_player.a']})
        await engine.start()
        await engine.effect(scene='candle')
        await complete(engine)
        self.assertFalse([c for c in hass.calls if c[1] == 'play_media'])
        hass.calls.clear()
        await engine.effect(zone_id='maison', scene='pursuit')
        await complete(engine)
        self.assertTrue([c for c in hass.calls if c[0] == 'light' and c[1] == 'turn_off'])
        self.assertEqual(len([c for c in hass.calls if c[1] == 'play_media']), 2)  # footsteps, then a knock
        await engine.stop()

    async def test_poltergeist_moves_covers_without_waiting_for_the_cooldown(self):
        engine, hass, states = make({'lights': ['light.a'], 'covers': ['cover.good'], 'switches': ['switch.prop'],
                                     'media_players': ['media_player.a']})
        await engine.start()
        await engine.effect(scene='poltergeist')
        await complete(engine)
        moves = [c for c in hass.calls if c[1] == 'set_cover_position']
        self.assertEqual(len(moves), 1)
        self.assertGreaterEqual(abs(moves[0][2]['position'] - 80), 20)
        self.assertFalse([c for c in hass.calls if c[0] == 'light'])
        await engine.stop()

    async def test_automatic_draw_skips_scenes_the_zone_cannot_play(self):
        engine, hass, states = make(normalize({'lights': ['light.a']}))
        zone = engine.zones['maison']
        self.assertFalse(engine.scene_feasible(zone, 'knocks'))
        self.assertFalse(engine.scene_feasible(zone, 'screen'))
        self.assertTrue(engine.scene_feasible(zone, 'candle'))
        await engine.start()
        for _ in range(30):
            engine._last_scare.clear()
            await engine.effect(source='automatic')
            await complete(engine)
        started = {e['scene'] for e in engine.history if e['kind'] == 'scene_started'}
        self.assertFalse(started & {'knocks', 'whispers', 'spatial', 'screen', 'poltergeist', 'retreat'})
        await engine.stop()

    async def test_zones_with_the_old_full_scene_list_get_the_new_scenes(self):
        from haunted_house_test.const import LEGACY_SCENES, SCENES
        old = normalize({'lights': ['light.a']})
        old['zones'][0]['scenes'] = list(LEGACY_SCENES)
        self.assertEqual(normalize(old)['zones'][0]['scenes'], list(SCENES))
        custom = normalize({'lights': ['light.a']})
        custom['zones'][0]['scenes'] = ['candle', 'storm']
        self.assertEqual(normalize(custom)['zones'][0]['scenes'], ['candle', 'storm'])

    async def test_light_that_drops_the_restore_command_is_retried_and_reported(self):
        engine, hass, states = make({'lights': ['light.a']})
        await engine.start()
        states['light.a'].state = 'off'  # The bulb never reacts: every restore command is "lost".
        hass.calls.clear()
        await engine.stop()
        restores = [c for c in hass.calls if c[0] == 'light' and c[2]['entity_id'] == 'light.a']
        self.assertEqual(len(restores), 2)  # first attempt, then one retry
        kinds = [e['kind'] for e in engine.history]
        self.assertIn('light_restore_retry', kinds)
        self.assertIn('light_not_restored', kinds)
        self.assertIn('is off, expected on', [e for e in engine.history if e['kind'] == 'light_not_restored'][0]['reasons']['light.a'])

    async def test_white_mode_light_is_restored_with_the_white_parameter(self):
        engine, hass, states = make({'lights': ['light.w']})
        states['light.w'] = State('on', brightness=120, color_mode='white', supported_color_modes=['white', 'rgb'])
        opts = normalize({'lights': ['light.w']})
        engine, hass, states = make(opts)
        states['light.w'] = State('on', brightness=120, color_mode='white', supported_color_modes=['white', 'rgb'])
        await engine.start()
        await engine.stop()
        last = [c for c in hass.calls if c[0] == 'light'][-1]
        self.assertEqual(last[2].get('white'), 120)
        self.assertNotIn('brightness', last[2])

    async def test_video_is_stopped_only_after_the_clip_has_played(self):
        opts = normalize({'lights': ['light.a']})
        opts['zones'][0].update(video_players=['media_player.tv'])
        engine, hass, states = make(opts)
        states['media_player.tv'] = State('idle')
        ticks, log = {'n': 0}, []
        original, fast = hass.services.async_call, engine.pause

        async def traced(domain, service, data, **kwargs):
            if service == 'play_media':
                ticks['n'] = 0
                states['media_player.tv'].state = 'buffering'  # a TV needs a moment to start
            if service == 'media_stop':
                log.append(ticks['n'])
            await original(domain, service, data, **kwargs)

        async def counting(seconds):
            ticks['n'] += 1
            if ticks['n'] == 4:
                states['media_player.tv'].state = 'playing'
            if ticks['n'] == 20:  # the clip ends by itself, 8 s after it started playing
                states['media_player.tv'].state = 'idle'
            await fast(seconds)
        hass.services.async_call, engine.pause = traced, counting
        await engine.start()
        await engine._video('maison')
        self.assertEqual(len(log), 1)
        self.assertGreaterEqual(log[0], 20)  # not cut after a fixed few seconds (6 s = 12 ticks)
        await engine.stop()

    async def test_tv_is_woken_and_put_to_sleep_by_a_separate_power_entity(self):
        opts = normalize({'lights': ['light.a']})
        opts['zones'][0].update(video_players=['media_player.cast'], video_power_entity='media_player.atv', video_power_on=True)
        engine, hass, states = make(opts)
        states['media_player.cast'] = State('unavailable')  # asleep: the Cast player is offline
        states['media_player.atv'] = State('off')
        original = hass.services.async_call

        async def wired(domain, service, data, **kwargs):
            if data['entity_id'] == 'media_player.atv' and service == 'turn_on':
                states['media_player.atv'].state = 'on'
                states['media_player.cast'].state = 'idle'  # the TV booted, Cast is back
            await original(domain, service, data, **kwargs)
        hass.services.async_call = wired
        await engine.start()
        await engine._video('maison')
        seen = [(c[2]['entity_id'], c[1]) for c in hass.calls if c[2]['entity_id'] in ('media_player.atv', 'media_player.cast')]
        self.assertEqual(seen[0], ('media_player.atv', 'turn_on'))
        self.assertIn(('media_player.cast', 'play_media'), seen)
        self.assertEqual(seen[-1], ('media_player.atv', 'turn_off'))
        self.assertEqual(seen.count(('media_player.atv', 'turn_off')), 1)
        self.assertFalse(engine._powered_extra)
        await engine.stop()
        self.assertEqual(sum(1 for c in hass.calls if c[1] == 'turn_off' and c[2]['entity_id'] == 'media_player.atv'), 1)

    async def test_sleeping_tv_is_left_alone_unless_power_on_is_allowed(self):
        opts = normalize({'lights': ['light.a']})
        opts['zones'][0].update(video_players=['media_player.cast'], video_power_entity='media_player.atv')
        engine, hass, states = make(opts)
        states['media_player.cast'] = State('unavailable')
        states['media_player.atv'] = State('off')
        await engine.start()
        await engine._video('maison')
        self.assertEqual(engine.history[-1]['reason'], 'power_on_disabled')
        self.assertFalse([c for c in hass.calls if c[2]['entity_id'] in ('media_player.atv', 'media_player.cast')])
        await engine.stop()

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

    async def test_tv_switched_on_by_the_show_is_switched_off_right_after_the_video(self):
        opts = normalize({'lights': ['light.a']})
        opts['zones'][0].update(video_players=['media_player.tv'], video_power_on=True)
        engine, hass, states = make(opts)
        states['media_player.tv'] = State('off', source='HDMI 1', volume_level=.3)
        await engine.start()
        await engine.effect(scene='screen')
        await complete(engine)
        tv = [c[1] for c in hass.calls if c[2].get('entity_id') == 'media_player.tv']
        self.assertEqual(tv[:2], ['turn_on', 'play_media'])
        self.assertLess(tv.index('media_stop'), tv.index('select_source'))
        self.assertLess(tv.index('select_source'), tv.index('turn_off'))
        self.assertEqual(tv.count('turn_off'), 1)  # off already, before the session ends
        self.assertFalse(engine._powered_media | engine._video_media)
        self.assertTrue(engine.running)
        await engine.stop()
        self.assertEqual([c[1] for c in hass.calls if c[2].get('entity_id') == 'media_player.tv'].count('turn_off'), 1)
        self.assertFalse(engine.snapshot)

    async def test_tv_that_was_already_on_is_left_on(self):
        opts = normalize({'lights': ['light.a']})
        opts['zones'][0].update(video_players=['media_player.tv'], video_power_on=True)
        engine, hass, states = make(opts)
        states['media_player.tv'] = State('idle', source='HDMI 1')
        await engine.start()
        await engine.effect(scene='screen')
        await complete(engine)
        await engine.stop()
        self.assertFalse([c for c in hass.calls if c[1] in ('turn_on', 'turn_off') and c[2].get('entity_id') == 'media_player.tv'])

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
