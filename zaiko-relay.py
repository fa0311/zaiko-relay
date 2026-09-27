import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import TracebackType
from typing import Annotated, ClassVar, Self
from urllib.parse import urljoin

import httpx2
import typer
import uvicorn
from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask


class TokenResponse(BaseModel):
    playback_url: str


class Relay:
    HEADERS: ClassVar[dict[str, str]] = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "ja,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        "origin": "https://live.zaiko.services",
        "referer": "https://live.zaiko.services/",
    }

    def __init__(self, token_url: str) -> None:
        self.token_url = token_url
        self.user_agent_url = "https://raw.githubusercontent.com/fa0311/latest-user-agent/main/output.json"
        self.playback_url: str | None = None
        self.client: httpx2.AsyncClient | None = None
        self.headers: dict[str, str] | None = None
        self.refresh_lock = asyncio.Lock()

    async def __aenter__(self) -> Self:
        self.client = httpx2.AsyncClient(follow_redirects=True, http2=True)
        user_agents = (await self.client.get(self.user_agent_url)).json()
        self.headers = self.HEADERS | {"user-agent": user_agents["macos-chrome-xhr"]}
        await self.refresh()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        assert self.client is not None
        await self.client.aclose()

    async def refresh(self) -> None:
        assert self.client is not None
        response = await self.client.get(self.token_url, headers=self.headers)
        response.raise_for_status()
        self.playback_url = TokenResponse.model_validate(response.json()).playback_url

    async def fetch(self, path: str, request: Request) -> httpx2.Response:
        assert self.client is not None
        assert self.headers is not None
        assert self.playback_url is not None

        playback_url = self.playback_url
        url = urljoin(playback_url, path)
        if request.url.query:
            url = f"{url}?{request.url.query}"
        headers = self.headers | {
            key: value
            for key, value in request.headers.items()
            if key.lower() in {"range", "if-range"}
        }
        response = await self.client.send(
            self.client.build_request("GET", url, headers=headers), stream=True
        )
        if response.status_code == 401:
            await response.aclose()
            async with self.refresh_lock:
                if self.playback_url == playback_url:
                    await self.refresh()
            url = urljoin(self.playback_url, path)
            if request.url.query:
                url = f"{url}?{request.url.query}"
            response = await self.client.send(
                self.client.build_request("GET", url, headers=headers), stream=True
            )
        return response


cli = typer.Typer()


@cli.command()
def main(token_url: Annotated[str, typer.Argument()]) -> None:
    relay = Relay(token_url=token_url)

    def get_relay() -> Relay:
        return relay

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with relay:
            yield

    app = FastAPI(lifespan=lifespan)

    @app.get("/{path:path}")
    async def get_media(
        path: str,
        request: Request,
        current_relay: Annotated[Relay, Depends(get_relay)],
    ) -> Response:
        upstream = await current_relay.fetch(path, request)
        return StreamingResponse(
            upstream.aiter_raw(),
            status_code=upstream.status_code,
            headers={
                key: value
                for key, value in upstream.headers.items()
                if key.lower() not in {"connection", "transfer-encoding"}
            },
            background=BackgroundTask(upstream.aclose),
        )

    uvicorn.run(app, host="127.0.0.1", port=8765)


if __name__ == "__main__":
    cli()
