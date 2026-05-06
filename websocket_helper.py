import asyncio
import logging
from typing import Awaitable, Callable

import websockets

logger = logging.getLogger(__name__)

HandleMessage = Callable[[str], Awaitable[None]]
HandleSetWebsocket = Callable[[websockets.ClientConnection], None]


async def websocket_listen_forever(
    websocket_uri: str,
    handle_message: HandleMessage,
    handle_set_websocket: HandleSetWebsocket = None,
) -> None:
    reply_timeout = 60
    ping_timeout = 15
    sleep_time = 5
    last_error: str | None = None

    while True:
        # outer loop restarted every time the connection fails
        try:
            async with websockets.connect(websocket_uri) as ws:
                if handle_set_websocket:
                    handle_set_websocket(ws)
                logger.info("接続成功しました。%s", websocket_uri, extra={'force': True})
                last_error = None

                while True:
                    # listener loop
                    try:
                        message = await asyncio.wait_for(
                            ws.recv(), timeout=reply_timeout
                        )
                        if handle_message:
                            await handle_message(message)
                    except (
                        asyncio.TimeoutError,
                        websockets.exceptions.ConnectionClosed,
                    ):
                        try:
                            pong = await ws.ping()
                            await asyncio.wait_for(pong, timeout=ping_timeout)
                            continue
                        except Exception:
                            await asyncio.sleep(sleep_time)
                            break
        except Exception as e:
            current_error = str(e)

            # 前回のエラーと異なる場合のみログを出力
            if current_error != last_error:
                logger.error(f"{e} {websocket_uri}")
                last_error = current_error

            await asyncio.sleep(sleep_time)
            continue
        finally:
            if handle_set_websocket:
                handle_set_websocket(None)
