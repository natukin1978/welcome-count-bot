import asyncio
import json
import logging
import os
import pickle
import sys

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

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

FILENAME_MAP_USER_COMMENT_ON_STREAM = get_cache_filepath(
    f"{g.app_name}_map_user_comment_on_stream.pkl"
)
g.map_user_comment_on_stream = {}

g.set_exclude_name = read_text_set("exclude_name.txt")
g.websocket_fuyuka = None

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        # サーバー側で数値を管理（初期値）
        self.total = 0
        self.undone = 0

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

        # 接続した瞬間に、現在の最新状態をそのクライアントだけに送る
        await websocket.send_json({
            "type": "SYNC_STATE",
            "total": self.total,
            "undone": self.undone,
        })

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        # ブロードキャストされる内容に基づいて、サーバー側の数値も更新しておく
        if message["type"] == "ADD_UNDONE":
            self.undone += message["value"]
        elif message["type"] == "UPDATE_TOTAL":
            self.total = message["value"]
        elif message["type"] == "UPDATE_UNDONE":
            self.undone = message["value"]

        for connection in self.active_connections[:]:
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

@app.websocket("/workout")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # ブラウザからのメッセージを受け取る
            data = await websocket.receive_json()

            # 受け取ったメッセージのタイプに応じて処理を分岐
            if data.get("type") == "REQUEST_ADD_UNDONE":
                # 加算リクエスト
                await manager.broadcast({
                    "type": "ADD_UNDONE",
                    "value": data.get("value", 0)
                })
            elif data.get("type") == "REQUEST_UPDATE_TOTAL":
                # 総数更新リクエスト
                await manager.broadcast({
                    "type": "UPDATE_TOTAL",
                    "value": data.get("value", 0)
                })
            elif data.get("type") == "REQUEST_UPDATE_UNDONE":
                # 未消化数更新リクエスト
                await manager.broadcast({
                    "type": "UPDATE_UNDONE",
                    "value": data.get("value", 0)
                })

    except WebSocketDisconnect:
        logger.info("Disconnected normally")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        manager.disconnect(websocket)
        logger.info("Cleanup for Client completed")

def load_user_comment_on_stream() -> bool:
    if not os.path.isfile(FILENAME_MAP_USER_COMMENT_ON_STREAM):
        return False
    with open(FILENAME_MAP_USER_COMMENT_ON_STREAM, "rb") as f:
        g.map_user_comment_on_stream = pickle.load(f)
        return True

def save_user_comment_on_stream() -> None:
    with open(FILENAME_MAP_USER_COMMENT_ON_STREAM, "wb") as f:
        pickle.dump(g.map_user_comment_on_stream, f)

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

            logger.info(json_data)
            data = json_data["request"]
            name = get_first_non_none_value(data, ["displayName", "id"])
            text = data["content"]

            if name in g.set_exclude_name:
                # 無視する名前
                return
            if not text:
                # 空文字は集計しない
                return

            comment_on_stream = 1
            if name in g.map_user_comment_on_stream:
                comment_on_stream = g.map_user_comment_on_stream[name]
                comment_on_stream += 1
            g.map_user_comment_on_stream[name] = comment_on_stream
            save_user_comment_on_stream()

            is_user_comment_on_stream = False
            if json_data["id"] == "showroom_chat_bot":
                if comment_on_stream == 2:
                    # SHOWROOMのみ2カウント目が初見
                    is_user_comment_on_stream = True
            elif comment_on_stream == 1:
                is_user_comment_on_stream = True

            if not is_user_comment_on_stream:
                # 集計済み
                return

            logger.info("%s", name, extra={'force': True})
            welcome_add_undone_count = g.config["welcomeAddUndoneCount"]
            if welcome_add_undone_count != 0:
                await manager.broadcast({
                    "type": "ADD_UNDONE",
                    "value": welcome_add_undone_count,
                })

        except json.JSONDecodeError:
            pass

    if is_continue and load_user_comment_on_stream():
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
