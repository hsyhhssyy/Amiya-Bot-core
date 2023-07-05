import json
import asyncio
import dataclasses

from typing import Optional
from dataclasses import dataclass
from amiyabot.network.httpRequests import http_requests, ResponseException
from amiyabot.adapters import BotAdapterProtocol, HANDLER_TYPE
from amiyabot.log import LoggerManager

log = LoggerManager('KOOK')


class KOOKBotInstance(BotAdapterProtocol):
    def __init__(self, appid: str, token: str):
        super().__init__(appid, token)

        self.ws_url = ''
        self.base_url = 'https://www.kookapp.cn/api/v3'
        self.headers = {
            'Authorization': f'Bot {token}'
        }
        self.connection = None

        self.pong = 0
        self.last_sn = 0

    def __str__(self):
        return 'KOOK'

    @property
    def __still_alive(self):
        return self.keep_run and self.connection

    async def connect(self, private: bool, handler: HANDLER_TYPE):
        while self.keep_run:
            await self.__connect(handler)
            await asyncio.sleep(10)

    async def __connect(self, handler: HANDLER_TYPE):
        try:
            if not self.ws_url:
                log.info(f'requesting appid {self.appid} gateway')

                resp = await self.get_request('/gateway/index', {'compress': 0})
                if not resp:
                    raise TimeoutError

                self.ws_url = resp['data']['url']

            log.info(f'connecting({self.appid})...')

            async with self.get_websocket_connection(self.appid, self.ws_url) as websocket:
                self.connection = websocket

                while self.__still_alive:
                    await asyncio.sleep(0)

                    recv = await websocket.recv()
                    payload = WSPayload(**json.loads(recv))

                    if payload.sn is not None:
                        self.last_sn = payload.sn

                    if payload.s == 0:
                        asyncio.create_task(handler('event', payload.d))

                    if payload.s == 1:
                        if payload.d['code'] != 0:
                            raise TimeoutError

                        if self.last_sn:
                            log.info(f'resuming({self.appid})...')
                            await self.connection.send(WSPayload(4, sn=self.last_sn).to_json())

                        self.session = payload.d['session_id']
                        asyncio.create_task(self.heartbeat_interval())

                    if payload.s == 3:
                        self.pong = 1

                    if payload.s == 5:
                        self.ws_url = ''
                        self.last_sn = 0
                        await self.close_connection()

                    if payload.s == 6:
                        log.info(f'resume({self.appid}) done.')

        finally:
            await self.close_connection()

    async def heartbeat_interval(self):
        sec = 0
        while self.__still_alive:
            await asyncio.sleep(1)
            sec += 1
            if sec >= 30:
                sec = 0
                await self.connection.send(WSPayload(2, sn=self.last_sn).to_json())

                asyncio.create_task(self.wait_heartbeat())

    async def wait_heartbeat(self):
        sec = 0
        while self.pong == 0 and self.__still_alive:
            await asyncio.sleep(1)
            sec += 1
            if sec >= 30:
                await self.close_connection()
        self.pong = 0

    async def close_connection(self):
        if self.connection:
            await self.connection.close()
        self.connection = None

    async def close(self):
        log.info(f'closing {self}(appid {self.appid})...')
        self.keep_run = False
        await self.close_connection()

    async def package_message(self, event: str, message: dict):

        print(message)

    async def get_request(self, url: str, params: dict = None):
        return self.__check_response(
            await http_requests.get(self.base_url + url, params, headers=self.headers)
        )

    async def post_request(self, url: str, payload: dict = None):
        return self.__check_response(
            await http_requests.post(self.base_url + url, payload, headers=self.headers)
        )

    @staticmethod
    def __check_response(response_text: Optional[str]) -> Optional[dict]:
        if response_text is None:
            return None

        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            raise ResponseException(-1, repr(e)) from e

        if 'code' in data and data['code'] != 0:
            raise ResponseException(**data)

        return data


@dataclass
class WSPayload:
    s: int
    d: dict = None
    sn: int = None
    extra: dict = None

    def to_json(self):
        return json.dumps(dataclasses.asdict(self), ensure_ascii=False)
