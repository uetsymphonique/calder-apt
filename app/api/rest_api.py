import base64
import logging
import os
import uuid

from aiohttp import web

from app.utility.base_world import BaseWorld


class RestApi(BaseWorld):

    def __init__(self, services):
        self.log = logging.getLogger('rest_api')
        self.data_svc = services.get('data_svc')
        self.app_svc = services.get('app_svc')
        self.file_svc = services.get('file_svc')
        self.rest_svc = services.get('rest_svc')

    async def enable(self):
        # unauthorized API endpoints
        self.app_svc.application.router.add_route('*', '/file/download', self.download_file)
        self.app_svc.application.router.add_route('POST', '/file/upload', self.upload_file)
        self.app_svc.application.router.add_route('GET', '/file/download_exfil', self.download_exfil_file)

    async def upload_file(self, request):
        dir_name = request.headers.get('Directory', None)
        if dir_name:
            return await self.file_svc.save_multipart_file_upload(request, 'data/payloads/')
        agent = request.headers.get('X-Request-ID', str(uuid.uuid4()))
        created_dir = os.path.normpath('/' + agent).lstrip('/')
        saveto_dir = await self.file_svc.create_exfil_sub_directory(dir_name=created_dir)
        operation_dir = await self.file_svc.create_exfil_operation_directory(dir_name=saveto_dir, agent_name=agent[-6:])
        return await self.file_svc.save_multipart_file_upload(request, operation_dir)

    async def download_file(self, request):
        try:
            payload, content, display_name = await self.file_svc.get_file(request.headers)
            headers = dict([('CONTENT-DISPOSITION', 'attachment; filename="%s"' % display_name),
                            ('FILENAME', display_name)])
            return web.Response(body=content, headers=headers)
        except FileNotFoundError:
            return web.HTTPNotFound(body='File not found')
        except Exception as e:
            return web.HTTPNotFound(body=str(e))

    async def download_exfil_file(self, request):
        def is_in_exfil_dir(f):
            return f.startswith(self.get_config('exfil_dir'))

        if request.query.get('file'):
            try:
                file = base64.b64decode(request.query.get('file')).decode('ascii')
                file = os.path.normpath(
                    file)  # normalize path to remove all directory traversal attempts then check for presence in exfil dir
                if not is_in_exfil_dir(file):
                    return web.HTTPNotFound(body="File not found in exfil dir")
                filename = file.split(os.sep)[-1]
                path = os.sep.join(file.split(os.sep)[:-1])
                _, content = await self.file_svc.read_file(filename, location=path)
                headers = dict([('CONTENT-DISPOSITION', 'attachment; filename="%s"' % filename),
                                ('FILENAME', filename)])
                return web.Response(body=content, headers=headers)
            except FileNotFoundError:
                return web.HTTPNotFound(body='File not found')
            except Exception as e:
                return web.HTTPNotFound(body=str(e))
        return web.HTTPBadRequest(body='A file needs to be specified for download')

    @staticmethod
    def _request_errors(request):
        errors = []
        return errors
