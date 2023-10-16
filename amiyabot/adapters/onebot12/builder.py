import base64

from amiyabot.adapters import MessageCallback
from amiyabot.adapters._adapterApi import BotAdapterAPI
from amiyabot.builtin.messageChain import Chain
from amiyabot.builtin.messageChain.element import *
from amiyabot.util import is_valid_url
from amiyabot import log


class OneBot12MessageCallback(MessageCallback):
    async def recall(self):
        if not self.response:
            log.warning('can not recall message because the response is None.')
            return False

        response = json.loads(self.response)

        if isinstance(response['data'], dict):
            await self.instance.recall_message(response['data']['message_id'])


async def build_message_send(api: BotAdapterAPI, chain: Chain, chain_only: bool = False):
    chain_list = chain.chain
    chain_data = []

    if chain_list:
        for item in chain_list:
            # At
            if isinstance(item, At):
                chain_data.append({'type': 'mention', 'data': {'user_id': item.target or chain.data.user_id}})

            # AtAll
            if isinstance(item, AtAll):
                chain_data.append({'type': 'mention_all', 'data': {}})

            # Face
            if isinstance(item, Face):
                ...

            # Text
            if isinstance(item, Text):
                chain_data.append({'type': 'text', 'data': {'text': item.content}})

            # Image
            if isinstance(item, Image):
                img = await item.get()
                res = await append_image(api, img)
                if res:
                    chain_data.append(res)

            # Voice
            if isinstance(item, Voice):
                ...

            # Html
            if isinstance(item, Html):
                result = await item.create_html_image()
                if result:
                    res = await append_image(api, result)
                    if res:
                        chain_data.append(res)
                else:
                    log.warning('html convert fail.')

            # Extend
            if isinstance(item, Extend):
                chain_data.append(item.get())

    if chain_only:
        return chain_data

    return {
        'detail_type': chain.data.message_type,
        'user_id': chain.data.user_id,
        'group_id': chain.data.channel_id,
        'message': chain_data,
    }


async def append_image(api: BotAdapterAPI, img_data: Union[bytes, str]):
    if isinstance(img_data, bytes):
        data = {'type': 'data', 'data': 'base64://' + base64.b64encode(img_data).decode()}
    elif is_valid_url(img_data):
        data = {'type': 'url', 'url': img_data}
    else:
        return None

    res = await api.post('/upload_file', data)
    if res:
        return {'type': 'image', 'data': {'file_id': res.data['file_id']}}
