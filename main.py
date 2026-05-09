import asyncio
import json
import logging
import os
import pickle
import sys
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

import global_value as g
from config_helper import read_config
from input_helper import input_with_timeout
from logging_setup import setup_app_logging

g.app_name = "welcome_count_bot"
g.base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

res = input_with_timeout("前回の続きですか？(y/n) [10秒以内に未入力なら 'n']: ", timeout=10)
is_continue = (res == "y")

g.config = read_config()

# ロガーの設定
setup_app_logging(g.config["logLevel"], log_file_path=f"{g.app_name}.log")
logger = logging.getLogger(__name__)

from cache_helper import get_cache_filepath
from dict_helper import get_first_non_none_value
from text_helper import read_text_set
from websocket_helper import websocket_listen_forever

FILENAME_MAP_IS_FIRST_ON_STREAM = get_cache_filepath(
    f"{g.app_name}_map_is_first_on_stream.pkl"
)
g.list_is_first_on_stream = []

g.set_exclude_name = read_text_set("exclude_name.txt")
g.websocket_fuyuka = None

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

@app.websocket("/workout")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text() # 接続維持のため
    except WebSocketDisconnect:
        manager.disconnect(websocket)

def load_is_first_on_stream() -> bool:
    if not os.path.isfile(FILENAME_MAP_IS_FIRST_ON_STREAM):
        return False
    with open(FILENAME_MAP_IS_FIRST_ON_STREAM, "rb") as f:
        g.list_is_first_on_stream = pickle.load(f)
        return True

def save_is_first_on_stream() -> None:
    with open(FILENAME_MAP_IS_FIRST_ON_STREAM, "wb") as f:
        pickle.dump(g.list_is_first_on_stream, f)

async def main():
    def get_fuyukaApi_baseUrl() -> str:
        conf_fa = g.config["fuyukaApi"]
        if not conf_fa:
            return ""
        return conf_fa["baseUrl"]

    def set_ws_fuyuka(ws) -> None:
        g.websocket_fuyuka = ws

    async def recv_fuyuka_response(message: str) -> None:
        try:
            json_data = json.loads(message)
            if "response" in json_data:
                # レスポンス付きなら処理しない
                return

            data = json_data["request"]
            name = get_first_non_none_value(data, ["displayName", "id"])
            text = data["content"]

            if name in g.set_exclude_name:
                # 無視する名前
                return

            if json_data["id"] == "showroom_chat_bot" and "ギフトをプレゼント" in text:
                # SHOWROOM ギフトならスキップ
                return

            if name in g.list_is_first_on_stream:
                # 集計済み
                return
            g.list_is_first_on_stream.append(name)
            save_is_first_on_stream()

            count = len(g.list_is_first_on_stream)
            logger.info("%s, count: %d", name, count, extra={'force': True})
            await manager.broadcast({
                "type": "ADD_UNDONE",
                "value": 5,
            })

        except json.JSONDecodeError:
            pass

    if is_continue and load_is_first_on_stream():
        print("挨拶キャッシュを復元しました。")

    config = uvicorn.Config(app, host="0.0.0.0", port=38696, log_level="info")
    server = uvicorn.Server(config)
    asyncio.create_task(server.serve())

    fuyukaApi_baseUrl = get_fuyukaApi_baseUrl()
    if fuyukaApi_baseUrl:
        websocket_uri = f"{fuyukaApi_baseUrl}/chat/{g.app_name}"
        asyncio.create_task(
            websocket_listen_forever(websocket_uri, recv_fuyuka_response, set_ws_fuyuka)
        )

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        pass
    finally:
        pass


if __name__ == "__main__":
    asyncio.run(main())
