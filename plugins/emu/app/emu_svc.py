import json

from aiohttp import web

from app.utility.base_service import BaseService
from app.utility.base_world import BaseWorld


class EmuService(BaseService):
    _dynamicically_compiled_payloads = {'sandcat.go-linux', 'sandcat.go-darwin', 'sandcat.go-windows'}
    _emu_config_path = "conf/default.yml"

    def __init__(self):
        self.log = self.add_service('emu_svc', self)
        BaseWorld.apply_config('emu', BaseWorld.strip_yml(self._emu_config_path)[0])
        self.evals_c2_host = self.get_config(name='emu', prop='evals_c2_host')
        self.evals_c2_port = self.get_config(name='emu', prop='evals_c2_port')
        self.app_svc = self.get_service('app_svc')
        self.contact_svc = self.get_service('contact_svc')
        if not self.app_svc:
            self.log.error('App svc not found.')
        else:
            self.app_svc.application.router.add_route('POST', '/plugins/emu/beacons', self.handle_forwarded_beacon)

    async def handle_forwarded_beacon(self, request):
        try:
            forwarded_profile = json.loads(await request.read())
            profile = dict()
            profile['paw'] = forwarded_profile.get('guid')
            profile['contact'] = 'http'
            profile['group'] = 'evals'
            if 'platform' in forwarded_profile:
                profile['platform'] = forwarded_profile.get('platform')
            else:
                profile['platform'] = 'evals'
            if 'hostName' in forwarded_profile:
                profile['host'] = forwarded_profile.get('hostName')
            if 'user' in forwarded_profile:
                profile['username'] = forwarded_profile.get('user')
            if 'pid' in forwarded_profile:
                profile['pid'] = forwarded_profile.get('pid')
            if 'ppid' in forwarded_profile:
                profile['ppid'] = forwarded_profile.get('ppid')
            await self.contact_svc.handle_heartbeat(**profile)
            response = 'Successfully processed forwarded beacon with session ID %s' % profile['paw']
            return web.Response(text=response)
        except Exception as e:
            error_msg = 'Server error when processing forwarded beacon: %s' % e
            self.log.error(error_msg)
            raise web.HTTPBadRequest(error_msg)
