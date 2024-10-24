from plugins.sandcat.app.sand_svc import SandService

name = 'Sandcat'
description = 'A custom multi-platform RAT'
address = 'address'


async def enable(services):
    app = services.get('app_svc').application
    file_svc = services.get('file_svc')
    sand_svc = SandService(services)
    await file_svc.add_special_payload('sandcat.go', sand_svc.dynamically_compile_executable)
    await file_svc.add_special_payload('shared.go', sand_svc.dynamically_compile_library)
    app.router.add_static('/sandcat', 'plugins/sandcat/static', append_version=True)
    await sand_svc.load_sandcat_extension_modules()
