import os

from app.utility.base_world import BaseWorld
from plugins.emu.app.emu_svc import EmuService

name = 'Emu'
description = 'The collection of abilities from the CTID Adversary Emulation Plans'
data_dir = os.path.join('plugins', name.lower(), 'data')


async def enable(services):
    BaseWorld.apply_config('emu', BaseWorld.strip_yml('plugins/emu/conf/default.yml')[0])
    plugin_svc = EmuService()
