"""
Aiohttp-based multipart client for Azure image edit requests.

Workaround for httpx multipart POST hanging in litellm proxy's PID 1 event loop.
aiohttp uses a different HTTP implementation that is not affected by this issue.
"""

import io
from typing import Any, Dict, List, Optional, Tuple, Union

import aiohttp
import httpx

from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler


class AiohttpMultipartResponse:
    """Mimics httpx.Response interface for litellm compatibility."""

    def __init__(self, status_code: int, headers: dict, body: bytes):
        self.status_code = status_code
        self.headers = headers
        self._body = body
        self.text = body.decode("utf-8", errors="replace")
        self.content = body

    def json(self):
        import orjson
        return orjson.loads(self._body)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=httpx.Request("POST", ""),
                response=httpx.Response(self.status_code, content=self._body),
            )


class AiohttpMultipartClient(AsyncHTTPHandler):
    """
    Drop-in replacement for AsyncHTTPHandler that uses aiohttp for multipart POST.
    Falls back to parent httpx implementation for non-multipart requests.
    """

    async def post(
        self,
        url: str,
        data: Optional[Union[dict, str, bytes]] = None,
        json: Optional[dict] = None,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        timeout: Optional[Union[float, httpx.Timeout]] = None,
        stream: bool = False,
        logging_obj: Optional[Any] = None,
        files: Optional[Any] = None,
        content: Any = None,
    ):
        if files is None:
            return await super().post(
                url=url, data=data, json=json, params=params,
                headers=headers, timeout=timeout, stream=stream,
                logging_obj=logging_obj, files=files, content=content,
            )

        timeout_val = 600.0
        if isinstance(timeout, (int, float)):
            timeout_val = float(timeout)
        elif isinstance(timeout, httpx.Timeout):
            timeout_val = timeout.read or 600.0

        form = aiohttp.FormData()

        if isinstance(data, dict):
            for k, v in data.items():
                if v is not None:
                    form.add_field(k, str(v))

        for file_entry in files:
            field_name = file_entry[0]
            file_tuple = file_entry[1]
            if isinstance(file_tuple, tuple):
                filename = file_tuple[0] if len(file_tuple) > 0 else "file"
                file_content = file_tuple[1] if len(file_tuple) > 1 else b""
                content_type = file_tuple[2] if len(file_tuple) > 2 else "application/octet-stream"

                if isinstance(file_content, io.IOBase):
                    file_content.seek(0)
                    raw_bytes = file_content.read()
                elif isinstance(file_content, (bytes, bytearray)):
                    raw_bytes = bytes(file_content)
                else:
                    raw_bytes = file_content

                form.add_field(
                    field_name,
                    raw_bytes,
                    filename=filename,
                    content_type=content_type,
                )
            else:
                form.add_field(field_name, file_tuple)

        clean_headers = {k: v for k, v in (headers or {}).items()
                        if k.lower() != "content-type"}

        aio_timeout = aiohttp.ClientTimeout(total=timeout_val)
        async with aiohttp.ClientSession(timeout=aio_timeout) as session:
            async with session.post(url, data=form, headers=clean_headers) as resp:
                body = await resp.read()
                resp_headers = dict(resp.headers)

        response = AiohttpMultipartResponse(
            status_code=resp.status,
            headers=resp_headers,
            body=body,
        )
        response.raise_for_status()
        return response
