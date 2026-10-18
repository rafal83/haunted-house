"""Flow sequencing tests with HA/selector doubles; not a real frontend/schema test."""
from copy import deepcopy
import importlib.util
import sys
import types
import unittest
from test_engine import make, module, ROOT
from haunted_house_test.model import normalize


class Marker:
    def __init__(self, name, **kwargs):
        self.name = name


vol = module('voluptuous')
vol.Optional = vol.Required = Marker
vol.Schema = lambda fields: fields
selector = module('homeassistant.helpers.selector')
for name in ['SelectSelector', 'SelectSelectorConfig', 'EntitySelector', 'EntitySelectorConfig',
             'TextSelector', 'TextSelectorConfig', 'NumberSelector', 'NumberSelectorConfig', 'BooleanSelector']:
    setattr(selector, name, lambda *a, **kw: kw)
core = sys.modules['homeassistant.core']
core.callback = lambda fn: fn


class Flow:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()

    def async_show_form(self, **kwargs):
        return {'type': 'form', **kwargs}

    def async_show_menu(self, **kwargs):
        return {'type': 'menu', **kwargs}

    def async_create_entry(self, **kwargs):
        return {'type': 'create_entry', **kwargs}

    async def async_set_unique_id(self, unique):
        pass

    def _abort_if_unique_id_configured(self):
        pass


entries = module('homeassistant.config_entries')
entries.ConfigFlow = entries.OptionsFlow = Flow
spec = importlib.util.spec_from_file_location('haunted_house_test.config_flow', ROOT / 'config_flow.py')
flow_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flow_mod)


class FlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_setup_devices_then_media(self):
        engine, hass, _ = make()
        flow = flow_mod.HauntedHouseFlow()
        flow.hass = hass
        result = await flow.async_step_user({'intensity': 'family', 'duration': 10})
        self.assertEqual(result['step_id'], 'zone')
        zone = normalize({'lights': ['light.a']})['zones'][0]
        result = await flow.async_step_zone(zone)
        self.assertEqual(result['step_id'], 'zone_media')
        result = await flow.async_step_zone_media({'sound_storm': 'http://example.test/thunder.wav'})
        self.assertEqual(result['type'], 'create_entry')
        self.assertEqual(result['options']['zones'][0]['lights'], ['light.a'])
        self.assertEqual(result['options']['zones'][0]['sound_storm'], 'http://example.test/thunder.wav')

    async def test_options_keep_media_when_devices_edited(self):
        opts = normalize({'lights': ['light.a']})
        opts['zones'][0]['videos'] = 'http://example.test/video.mp4'
        engine, hass, _ = make(opts)
        flow = flow_mod.HauntedOptionsFlow()
        flow.config_entry = types.SimpleNamespace(options=opts, entry_id='test')
        flow.hass = hass
        await flow.async_step_init()
        await flow.async_step_edit_zone({'zone_id': 'maison'})
        changed = {k: deepcopy(v) for k,v in opts['zones'][0].items() if not k.startswith('sound_') and k != 'videos'}
        changed['name'] = 'Entrée'
        await flow.async_step_zone(changed)
        await flow.async_step_zone_media({})
        result = await flow.async_step_save()
        self.assertEqual(result['data']['zones'][0]['videos'], 'http://example.test/video.mp4')
        self.assertEqual(result['data']['zones'][0]['name'], 'Entrée')
        self.assertEqual(opts['zones'][0]['name'], 'Maison')

    async def test_delete_zone_cleans_route_and_branches(self):
        opts = normalize({'lights': ['light.a']})
        opts['zones'][0]['next_zone'] = 'salon'
        opts['zones'].append(normalize({'lights': ['light.b']})['zones'][0] | {'id': 'salon'})
        opts['ghost_route'] = ['maison', 'salon']
        engine, hass, _ = make(opts)
        flow = flow_mod.HauntedOptionsFlow()
        flow.hass = hass
        flow.config_entry = types.SimpleNamespace(options=opts)
        await flow.async_step_init()
        await flow.async_step_remove_zone({'zone_id': 'salon'})
        self.assertEqual(flow._draft['ghost_route'], ['maison'])
        self.assertEqual(flow._draft['zones'][0]['next_zone'], '')

    async def test_preview_form_has_no_device_effect(self):
        engine, hass, _ = make()
        hass.data = {'haunted_house': {'test': engine}}
        flow = flow_mod.HauntedOptionsFlow()
        flow.hass = hass
        flow.config_entry = types.SimpleNamespace(options=engine.options, entry_id='test')
        await flow.async_step_init()
        result = await flow.async_step_test_scene({'zone_id': 'maison', 'scene': 'storm'})
        self.assertEqual(result['step_id'], 'test_preview')
        self.assertIn('light.a', result['description_placeholders']['devices'])
        self.assertFalse(hass.calls)
        await flow.async_step_test_preview({'run_test': False})
        self.assertFalse(hass.calls)
