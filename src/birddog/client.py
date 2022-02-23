# from loguru import logger
import logging
logger = logging.getLogger(__name__)
import asyncio
import json
from urllib.parse import urlsplit, urlunsplit
import typing as tp

from bs4 import BeautifulSoup
import httpx

from . import models

class ClientBase:
    host_url: str

    session: tp.Optional[httpx.AsyncClient]
    _owns_session: bool
    is_open: bool
    def __init__(
        self,
        host_url: str,
        session: tp.Optional[httpx.AsyncClient] = None,
    ):
        if '//' not in host_url:
            host_url = f'http://{host_url}'
        sp = urlsplit(host_url)
        host_url = urlunsplit([sp.scheme, sp.netloc, '', '', ''])
        self.host_url = host_url
        self.session = session
        self._owns_session = session is None
        self.is_open = False

    def get_session(self) -> httpx.AsyncClient:
        s = self.session
        if s is None:
            logger.debug(f'{self.__class__.__name__} building session')
            s = self.session = httpx.AsyncClient(follow_redirects=True)
            self._owns_session = True
        return s

    # async def iter_responses(self, request):
    #     session = self.get_session()
    #     logger.debug(f'request start:')
    #     while request is not None:
    #         logger.debug(f'        ->: {request=}')
    #         resp = await session.send(request)
    #         logger.debug(f'        <-: {resp=}')
    #         request = resp.next_request
    #         has_more = request is not None
    #         yield resp, has_more

    def format_url(self, *paths) -> str:
        full_path = '/'.join(paths)
        return f'{self.host_url}/{full_path}'

    async def open(self):
        self.is_open = True

    async def close(self):
        session = self.session
        if session is not None and self._owns_session:
            self.session = None
            await session.aclose()
        self.is_open = False

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, *args):
        await self.close()

class ApiClient(ClientBase):
    def __init__(
        self,
        host_url: str,
        session: tp.Optional[httpx.AsyncClient] = None,
    ):
        super().__init__(host_url, session)
        sp = urlsplit(self.host_url)
        netloc = sp.netloc
        if ':' in netloc:
            netloc = netloc.split(':')[0]
        netloc = f'{netloc}:8080'
        self.host_url = urlunsplit([sp.scheme, netloc, '', '', ''])
        self.auth_client = None

    async def get(self, api_method: str, params=None) -> tp.Union[bytes, tp.Dict]:
        session = self.get_session()
        url = self.format_url(api_method)
        kw = {}
        if params is not None:
            kw['params'] = params
        resp = await session.get(url, **kw)
        resp.raise_for_status()
        content = resp.content
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            result = content
        return result

    async def post(
        self, api_method: str,
        data: tp.Optional[tp.Dict] = None, timeout: tp.Optional[float] = None,
        form_encoded: bool = False,
    ) -> tp.Union[bytes, tp.Dict]:
        session = self.get_session()
        if data is None:
            kw = {'headers':{'Accept':'text'}}
        elif form_encoded:
            kw = {'headers':{'Accept':'text'}, 'data':data}
        else:
            kw = {
                'headers':{'Content-Type': 'application/json'},
                'data':json.dumps(data),
            }

        if timeout is not None:
            kw['timeout'] = timeout

        url = self.format_url(api_method)
        resp = await session.post(url, **kw)
        resp.raise_for_status()
        content = resp.content

        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            result = content
        return result

    async def get_hostname(self) -> str:
        content = await self.get('hostname')
        if isinstance(content, bytes):
            content = content.decode()
        return content

    async def reboot(self):
        # Send a request to make sure the device is on the network
        # (since we're ignoring the reboot response)
        h = await self.get_hostname()

        try:
            r = await self.get('reboot')
        except httpx.HTTPError:
            pass

    async def restart(self):
        # Send a request to make sure the device is on the network
        # (since we're ignoring the reboot response)
        h = await self.get_hostname()

        try:
            r = await self.get('restart')
        except httpx.HTTPError:
            raise

    async def get_operation_mode(self) -> models.OperationMode:
        content = await self.get('operationmode')
        if isinstance(content, dict):
            try:
                mode = content['mode']
            except KeyError:
                print(f'{content=}')
                raise
        else:
            mode = content.decode()
        return getattr(models.OperationMode, mode)

    async def set_operation_mode(self, mode: tp.Union[str, models.OperationMode]):
        if isinstance(mode, str):
            mode = getattr(models.OperationMode, mode)
        await self._proxy_through_auth_client('set_operation_mode', mode)

    async def get_audio_setup(self) -> models.AudioOutputSetup:
        content = await self.get('analogaudiosetup')
        return models.AudioOutputSetup.from_api(content)

    async def list_sources(self) -> tp.Iterable[models.NdiSource]:
        current_src = await self.get_source()
        content = await self.get('List')
        results = []
        for i, key in enumerate(content.keys()):
            val = content[key]
            is_current = key == current_src.name
            results.append(models.NdiSource(
                name=key, address=val, index=i, is_current=is_current,
            ))
        return results

    async def get_source(self) -> models.NdiSource:
        content = await self.get('connectTo')
        return models.NdiSource(name=content['sourceName'])

    async def set_source(self, source: tp.Union[str, models.NdiSource, int]):
        if isinstance(source, int):
            source_index = source
            source_iter = await self.list_sources()
            sources = {src.index:src for src in source_iter}
            source = sources[source_index]
        if isinstance(source, models.NdiSource):
            source = source.name
        content = await self.post('connectTo', {'sourceName':source})
        assert content == b'success'

    async def _proxy_through_auth_client(self, method_name: str, *args):
        client = self.auth_client
        if not client.is_open:
            await client.open()
        m = getattr(client, method_name)
        if len(args):
            result = await m(*args)
        else:
            result = await m()
        return result

    async def get_settings(self) -> models.DeviceSettings:
        return await self._proxy_through_auth_client('get_settings')

    async def get_video_output(self) -> models.VideoOutput:
        settings = await self.get_settings()
        return settings.video_output

    async def set_video_output(self, video_output: tp.Union[str, models.VideoOutput]):
        if isinstance(video_output, str):
            video_output = getattr(models.VideoOutput, video_output)
        await self._proxy_through_auth_client('set_video_output', video_output)

    async def refresh_sources(self):
        await self._proxy_through_auth_client('refresh_sources')

    async def open(self):
        if self.auth_client is None:
            if self.session is None:
                self.get_session()
            self.auth_client = AuthClient(
                host_url=self.host_url, session=self.session, api_client=self,
            )
        await super().open()

    async def close(self):
        c = self.auth_client
        try:
            if c is not None:
                self.auth_client = None
                if c.is_open:
                    await c.close()
        finally:
            await super().close()


class AuthClient(ClientBase):
    settings: tp.Optional[models.DeviceSettings]
    password: str = 'birddog'
    api_client: tp.Optional[ApiClient]
    _logged_in: bool
    def __init__(
        self,
        host_url: str,
        session: tp.Optional[httpx.AsyncClient] = None,
        password: str = 'birddog',
        api_client: tp.Optional[ApiClient] = None,
    ):
        super().__init__(host_url, session)
        sp = urlsplit(self.host_url)
        netloc = sp.netloc
        if ':' in netloc:
            netloc = netloc.split(':')[0]
        self.host_url = urlunsplit([sp.scheme, netloc, '', '', ''])
        self.password = password
        self.api_client = api_client

        self.settings = None
        self._logged_in = False

    # @logger.catch
    async def get(self, *paths, num_attempts=0):
        # if not self._logged_in:
        #     await self._login()
        assert self._logged_in
        url = self.format_url(*paths)
        session = self.get_session()
        resp = await session.get(url)
        resp.raise_for_status()
        return resp.text

    # @logger.catch
    async def post(self, *paths, data=None, num_attempts=0) -> str:
        """Perform a "POST" request on the given sub paths

        If ``data`` is given, it will be sent form encoded
        """
        # if not self._logged_in:
        #     await self._login()
        assert self._logged_in
        url = self.format_url(*paths)
        session = self.get_session()
        kw = {}
        if data is not None:
            kw = {'data':data}
        resp = await session.post(url, **kw)
        resp.raise_for_status()
        return resp.text

    async def get_settings(self) -> models.DeviceSettings:
        r = await self.get('videoset')
        soup = BeautifulSoup(r, 'html5lib')
        mode_form = soup.find(id='mod_sel')
        op_mode = None
        for input_id in ['encode', 'decode']:
            in_el = mode_form.find(id=input_id)
            if 'checked' in in_el.attrs:
                op_mode = input_id
        assert op_mode is not None
        op_mode = getattr(models.OperationMode, op_mode)

        vout = None
        for input_id in ['sdi', 'hdmi']:
            in_el = mode_form.find(id=input_id)
            if 'checked' in in_el.attrs:
                vout = input_id
        assert vout is not None
        vout = getattr(models.VideoOutput, vout)

        if self.api_client is not None:
            audio_setup = await self.api_client.get_audio_setup()
        else:
            async with ApiClient(self.host_url, self.session) as client:
                audio_setup = await client.get_audio_setup()

        self.settings = models.DeviceSettings(
            operation_mode=op_mode,
            video_output=vout,
            audio_setup=audio_setup,
        )

        return self.settings

    async def set_operation_mode(self, mode: models.OperationMode):
        settings = await self.get_settings()
        settings.operation_mode = mode
        form_data = settings.to_form_data()
        await self.post('videoset', data=form_data)

    async def set_video_output(self, video_output: models.VideoOutput):
        settings = await self.get_settings()
        settings.video_output = video_output
        form_data = settings.to_form_data()
        await self.post('videoset', data=form_data)

    async def refresh_sources(self):
        await self.post('videoset', data={'add_new_sources':'new_sources'})

    async def _logout(self):
        session = self.get_session()
        url = self.format_url('logout')
        resp = await session.post(url)
        resp.raise_for_status()
        self._logged_in = False

    # @logger.catch
    async def _login(self):
        session = self.get_session()
        url = self.format_url('login')
        resp = await session.post(url, data={'auth_password':self.password})
        resp.raise_for_status()
        self._logged_in = True

    async def open(self):
        await super().open()
        await self._login()

    async def close(self):
        try:
            if self._logged_in:
                await self._logout()
        finally:
            self.login_cookie = None
            await super().close()
