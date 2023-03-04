import aiohttp
import requests

from io import BytesIO
from amiyabot import log

default_headers = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 10_3_1 like Mac OS X) '
                  'AppleWebKit/603.1.30 (KHTML, like Gecko) Version/10.0 Mobile/14E304 Safari/602.1'
}


def download_sync(url: str, headers=None, stringify=False, progress=False, **kwargs):
    try:
        stream = requests.get(url, headers={**default_headers, **(headers or {})}, stream=True, **kwargs)
        container = BytesIO()

        if stream.status_code == 200:
            iter_content = stream.iter_content(chunk_size=1024)
            if progress and 'content-length' in stream.headers:
                iter_content = log.download_progress(url.split('/')[-1],
                                                     max_size=int(stream.headers['content-length']),
                                                     chunk_size=1024,
                                                     iter_content=iter_content)
            for chunk in iter_content:
                if chunk:
                    container.write(chunk)

            content = container.getvalue()

            if stringify:
                return str(content, encoding='utf-8')
            else:
                return content
    except requests.exceptions.ConnectionError:
        pass
    except Exception as e:
        log.error(e, desc='download error:')


async def download_async(url, headers=None, stringify=False, **kwargs):
    async with log.catch('download error:', ignore=[requests.exceptions.SSLError]):
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={**default_headers, **(headers or {})}, **kwargs) as res:
                if res.status == 200:
                    if stringify:
                        return await res.text()
                    else:
                        return await res.read()
