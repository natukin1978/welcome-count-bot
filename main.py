import asyncio
import json
import logging
import os
import re
import sys

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

import global_value as g
from config_helper import read_config
from input_helper import input_with_timeout
from logging_setup import setup_app_logging

is_testing = os.environ.get("APP_TESTING") == "True"

g.app_name = "welcome_count_bot"
g.base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

if not is_testing:
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
from zenkaku_helper import kanji_to_int

g.set_exclude_name = read_text_set("exclude_name.txt")

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.save_file = get_cache_filepath(f"{g.app_name}_app_state.json")

        self.map_user_comment_on_stream = {}
        self.list_user_first = []
        self.total = 0
        self.undone = 0

        self.is_voice_mode = False
        self.last_number = None

    # --- 状態を保存するメソッド ---
    def save_state(self):
        if is_testing:
            # テスト中は保存させない
            return
        state = {
            "map_user_comment_on_stream": self.map_user_comment_on_stream,
            "list_user_first": self.list_user_first,
            "total": self.total,
            "undone": self.undone,
        }
        with open(self.save_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    # --- 状態を復元するメソッド ---
    def load_state(self):
        """保存ファイルからデータを読み込み、自身の変数を更新する"""
        if not os.path.exists(self.save_file):
            return False

        try:
            with open(self.save_file, "r", encoding="utf-8") as f:
                state = json.load(f)

            # 各変数をファイルの内容で上書き
            # 辞書の get(キー, デフォルト値) を使うことで、キーがなくても壊れないようにします
            self.map_user_comment_on_stream = state.get("map_user_comment_on_stream", {})
            self.list_user_first = state.get("list_user_first", [])
            self.total = state.get("total", 0)
            self.undone = state.get("undone", 0)

            return True
        except (json.JSONDecodeError, IOError):
            # ファイルが壊れている場合などのエラーハンドリング
            print("警告: 状態ファイルの読み込みに失敗しました。")
            return False

    async def update_and_broadcast(self, msg_type: str, total: int = None, undone: int = None, diff: int = 0, value: int = None):
        """数値を更新し、保存し、全クライアントへ通知する"""
        if total is not None:
            self.total = total
        if undone is not None:
            self.undone = undone

        # 直接数値を指定する場合（UIからのリクエストなど）
        if value is not None:
            if "TOTAL" in msg_type:
                self.total = value
            if "UNDONE" in msg_type:
                if "ADD" in msg_type:
                    self.undone += value
                else:
                    self.undone = value

        # 状態をファイルに保存
        self.save_state()

        # 通知用ペイロード作成
        payload = {"type": msg_type, "total": self.total, "undone": self.undone}
        if diff > 0:
            payload["diff"] = diff
        if value is not None:
            payload["value"] = value

        await self.broadcast(payload)

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
        # 配信中に接続が切れたクライアントを掃除しながら送信
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
            if data.get("type") == "SET_MODE":
                new_mode = data["value"]
                manager.is_voice_mode = (new_mode == "voice")
                if not manager.is_voice_mode:
                    manager.last_number = None # 記録をリセット
                # 他の全クライアント（オーバーレイ等）にモード変更を同期
                await manager.broadcast({
                    "type": "MODE_CHANGE",
                    "value": new_mode
                })

            elif data.get("type") == "REQUEST_ADD_UNDONE":
                # 未消化加算
                val = data.get("value", 0)
                await manager.update_and_broadcast("ADD_UNDONE", value=val)

            elif data.get("type") == "REQUEST_UPDATE_TOTAL":
                # 総数直接更新
                val = data.get("value", 0)
                await manager.update_and_broadcast("UPDATE_TOTAL", value=val)

            elif data.get("type") == "REQUEST_UPDATE_UNDONE":
                # 未消化直接更新
                val = data.get("value", 0)
                await manager.update_and_broadcast("UPDATE_UNDONE", value=val)

    except WebSocketDisconnect:
        logger.info("Disconnected normally")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        manager.disconnect(websocket)
        logger.info("Cleanup for Client completed")

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

        if get_first_non_none_value(data, ["isFirst"]):
            # この配信中のみで良いので、初見という事を記録しておく
            manager.list_user_first.append(name)

        isFirst = name in manager.list_user_first

        if name in g.set_exclude_name:
            # 無視する名前
            return
        if not text:
            # 空文字は集計しない
            return

        comment_on_stream = 1
        if name in manager.map_user_comment_on_stream:
            comment_on_stream = manager.map_user_comment_on_stream[name]
            comment_on_stream += 1
        manager.map_user_comment_on_stream[name] = comment_on_stream
        manager.save_state()

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

        waudc = g.config["welcomeAddUndoneCount"]
        if not waudc["enable"]:
            return

        value = 0
        if isFirst:
            value = waudc["first"]
        else:
            value = waudc["normal"]
        if value != 0:
            await manager.broadcast({
                "type": "ADD_UNDONE",
                "value": value,
            })

    except json.JSONDecodeError:
        pass

async def recv_talk_text(message: str) -> None:
    try:
        data = json.loads(message)
        if type(data) is not dict:
            raise json.JSONDecodeError("result value was not dict", "", 0)
        # JSONとして処理する
        # もし取り込む値があるなら取り込む
    except json.JSONDecodeError:
        # プレーンテキストとして処理する
        text = message.strip()

        # if not text or text.endswith("..."):
        if not text:
            return

        # 1. モード開始判定
        if re.search(r'筋トレ.*(消化|始め|開始|します|やります)', text):
            manager.is_voice_mode = True
            manager.last_number = None
            await manager.broadcast({"type": "MODE_CHANGE", "value": "voice"})
            return # 開始した回は数値処理をスキップ（誤作動防止）

        # 2. 数値解析と音声モード処理
        val = kanji_to_int(text)
        if val is None or not manager.is_voice_mode:
            return

        # 初回数値受信
        if manager.last_number is None:
            if val < manager.undone:
                manager.last_number = val
                await manager.update_and_broadcast("DIGEST", total=manager.total + 1, undone=max(0, manager.undone - 1))
            return

        # 2回目以降の差分計算
        if val < manager.last_number:
            diff = manager.last_number - val
            manager.last_number = val

            await manager.update_and_broadcast("DIGEST_MULTI",
                                               total=manager.total + diff,
                                               undone=max(0, manager.undone - diff),
                                               diff=diff)

            # モード終了判定
            if val == 0:
                manager.is_voice_mode = False
                manager.last_number = None
                await manager.broadcast({"type": "MODE_CHANGE", "value": "normal"})

async def main():
    def get_workoutApi_port() -> int:
        conf_fa = g.config["workoutApi"]
        if not conf_fa:
            return 0
        return conf_fa["port"]

    def get_fuyukaApi_baseUrl() -> str:
        conf_fa = g.config["fuyukaApi"]
        if not conf_fa:
            return ""
        if not get_first_non_none_value(conf_fa, ["enable"]):
            return ""
        return conf_fa["baseUrl"]

    def get_neoInnerApi_baseUrl() -> str:
        conf_nia = g.config["neoInnerApi"]
        if not conf_nia:
            return ""
        if not get_first_non_none_value(conf_nia, ["enable"]):
            return ""
        return conf_nia["baseUrl"]

    if is_continue and manager.load_state():
        print("状態を復元しました。")

    config = uvicorn.Config(app, host="0.0.0.0", port=get_workoutApi_port(), log_level=g.config["logLevel"])
    server = uvicorn.Server(config)
    asyncio.create_task(server.serve())

    fuyukaApi_baseUrl = get_fuyukaApi_baseUrl()
    if fuyukaApi_baseUrl:
        websocket_uri = f"{fuyukaApi_baseUrl}/chat/{g.app_name}"
        asyncio.create_task(websocket_listen_forever(websocket_uri, recv_fuyuka_response))

    neoInnerApi_baseUrl = get_neoInnerApi_baseUrl()
    if neoInnerApi_baseUrl:
        websocket_uri = f"{neoInnerApi_baseUrl}/textonly"
        asyncio.create_task(websocket_listen_forever(websocket_uri, recv_talk_text))

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        pass
    finally:
        pass


if __name__ == "__main__":
    asyncio.run(main())
