import json
import unittest
from unittest.mock import AsyncMock

import main  # main.pyをインポート


class TestWorkoutLogic(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager = main.ConnectionManager()
        self.manager.broadcast = AsyncMock()
        # テスト用の初期状態を設定
        self.manager.undone = 50
        self.manager.total = 100
        main.manager = self.manager

    async def test_add_undone_is_first(self):
        """初見コメントで未消化が送信されるかテスト"""
        waudc = main.g.config["welcomeAddUndoneCount"]
        waudc["enable"] = True
        waudc["first"] = 2
        waudc["normal"] = 1

        # 初回(さらに初見)
        data = {
            "id": "twitch_chat_bot",
            "request": {
                "id": "a",
                "content": "1",
                "isFirst": True,
            }
        }
        await main.recv_fuyuka_response(json.dumps(data))
        self.manager.broadcast.assert_any_call({
            "type": "ADD_UNDONE",
            "value": 2,
        })

        # 2回目
        self.manager.broadcast.reset_mock()
        data["request"]["isFirst"] = False
        await main.recv_fuyuka_response(json.dumps(data))
        self.manager.broadcast.assert_not_called()

    async def test_add_undone_is_not_first(self):
        """コメントで未消化が送信されるかテスト"""
        waudc = main.g.config["welcomeAddUndoneCount"]
        waudc["enable"] = True
        waudc["first"] = 2
        waudc["normal"] = 1

        # 初回(常連)
        data = {
            "id": "twitch_chat_bot",
            "request": {
                "id": "a",
                "content": "1",
                "isFirst": False,
            }
        }
        await main.recv_fuyuka_response(json.dumps(data))
        self.manager.broadcast.assert_any_call({
            "type": "ADD_UNDONE",
            "value": 1,
        })

        # 2回目
        self.manager.broadcast.reset_mock()
        await main.recv_fuyuka_response(json.dumps(data))
        self.manager.broadcast.assert_not_called()

    async def test_add_undone_showroom_is_first(self):
        """SHOWROOMの初見コメントで未消化が送信されるかテスト"""
        waudc = main.g.config["welcomeAddUndoneCount"]
        waudc["enable"] = True
        waudc["first"] = 2
        waudc["normal"] = 1

        # 初回(さらに初見)
        data = {
            "id": "showroom_chat_bot",
            "request": {
                "id": "a",
                "content": "1",
                "isFirst": True,
            }
        }
        await main.recv_fuyuka_response(json.dumps(data))
        self.manager.broadcast.assert_not_called()

        # 2回目
        self.manager.broadcast.reset_mock()
        data["request"]["isFirst"] = False
        await main.recv_fuyuka_response(json.dumps(data))
        self.manager.broadcast.assert_any_call({
            "type": "ADD_UNDONE",
            "value": 2,
        })

        # 3回目
        self.manager.broadcast.reset_mock()
        await main.recv_fuyuka_response(json.dumps(data))
        self.manager.broadcast.assert_not_called()

    async def test_add_undone_showroom_is_not_first(self):
        """SHOWROOMのコメントで未消化が送信されるかテスト"""
        waudc = main.g.config["welcomeAddUndoneCount"]
        waudc["enable"] = True
        waudc["first"] = 2
        waudc["normal"] = 1

        # 初回(常連)
        data = {
            "id": "showroom_chat_bot",
            "request": {
                "id": "a",
                "content": "1",
                "isFirst": False,
            }
        }
        await main.recv_fuyuka_response(json.dumps(data))
        self.manager.broadcast.assert_not_called()

        # 2回目
        self.manager.broadcast.reset_mock()
        await main.recv_fuyuka_response(json.dumps(data))
        self.manager.broadcast.assert_any_call({
            "type": "ADD_UNDONE",
            "value": 1,
        })

        # 3回目
        self.manager.broadcast.reset_mock()
        await main.recv_fuyuka_response(json.dumps(data))
        self.manager.broadcast.assert_not_called()

    async def test_voice_add_undone(self):
        """音声による筋トレ回数の追加リクエストをテスト（last_numberは維持）"""
        await main.recv_talk_text("筋トレ開始")
        self.manager.undone = 10
        self.manager.total = 100

        # 1. 基準値を確定させるために一度カウントダウンを発話
        await main.recv_talk_text("9")
        self.assertEqual(self.manager.undone, 9)
        self.assertEqual(self.manager.last_number, 9)

        # 2. 音声で「筋トレ 15回 追加」と発話
        # undoneは 9 + 15 = 24 に増えるが、音声の基準値(last_number)は9のまま動かない
        await main.recv_talk_text("筋トレを15回分追加しまーす。")
        self.assertEqual(self.manager.undone, 24)
        self.assertEqual(self.manager.last_number, 9)
        self.assertEqual(self.manager.total, 101)

        # 3. 追加後に「7」と発話（基準値9からの差分は2なので、3以内制限をクリアして消化される）
        # undone: 24 - 2 = 22
        # last_number: 7 に更新
        await main.recv_talk_text("7")
        self.assertEqual(self.manager.undone, 22)
        self.assertEqual(self.manager.last_number, 7)

    async def test_mode_start(self):
        """「筋トレ開始」でモードが切り替わるかテスト"""
        await main.recv_talk_text("筋トレ始めます")
        self.assertTrue(self.manager.is_voice_mode)
        # MODE_CHANGEメッセージが送られたか確認
        self.manager.broadcast.assert_called()

    async def test_voice_digest_flow(self):
        """音声による消化の数値遷移をテスト"""
        # 1. モード開始
        await main.recv_talk_text("筋トレ開始")

        # 2. 初回の数値（基準値）を受信
        # 未消化50に対して「49」と言った場合、1つ消化されるはず
        await main.recv_talk_text("四十九")
        self.assertEqual(self.manager.undone, 49)
        self.assertEqual(self.manager.total, 101)
        self.assertEqual(self.manager.last_number, 49)

        # 3. 2回目の数値（カウントダウン）
        # 「46」と言った場合、さらに3つ消化されるはず
        await main.recv_talk_text("46")
        self.assertEqual(self.manager.undone, 46)
        self.assertEqual(self.manager.total, 104)

    async def test_undone_increase_after_last_number_set(self):
        """基準値決定後にundoneを10加算し、3以内のカウントダウンが継続できるかテスト"""
        # 1. 音声モード開始と初期状態の設定
        await main.recv_talk_text("筋トレ開始")
        self.manager.undone = 40
        self.manager.total = 100

        # 2. 初回の数値「39」を受信（1回消化、基準値が39になる）
        await main.recv_talk_text("39")
        self.assertEqual(self.manager.undone, 39)
        self.assertEqual(self.manager.total, 101)
        self.assertEqual(self.manager.last_number, 39)

        # 3. 外部要因で undone を 10 加算（39 + 10 = 49 になる）
        self.manager.undone += 10
        self.assertEqual(self.manager.undone, 49)

        # 4. 次の数値「36」を受信（39 - 36 = 3 なので、3以内セーフティを通過）
        # 期待される計算:
        # 差分: 基準値(39) - 今回の値(36) = 3 消化
        # undone: 49(加算後) - 3 = 46
        # total: 101(前回) + 3 = 104
        await main.recv_talk_text("36")

        self.assertEqual(self.manager.undone, 46)
        self.assertEqual(self.manager.total, 104)
        self.assertEqual(self.manager.last_number, 36)

    async def test_far_number_is_ignored_after_undone_increase(self):
        """undone加算後であっても、3より大きく離れた数値が正しく無視されるかテスト"""
        # 1. 初期状態を設定（基準値を39にする）
        await main.recv_talk_text("筋トレ開始")
        self.manager.undone = 40
        await main.recv_talk_text("39")

        # 2. 外部要因で undone を 10 加算（39 + 10 = 49 になる）
        self.manager.undone += 10

        # 3. 3より大きく離れた数値「35」を受信（39 - 35 = 4 でアウト）
        # 期待される挙動:
        # 安全機能が働き、処理がスキップされる。
        # undone(49), total(101), last_number(39) のすべてが変化しないこと。
        await main.recv_talk_text("35")

        self.assertEqual(self.manager.undone, 49)       # 49のまま（消化されない）
        self.assertEqual(self.manager.total, 101)      # 101のまま
        self.assertEqual(self.manager.last_number, 39)  # 基準値も39のまま

    async def test_mode_end_at_zero(self):
        """「0」でモードが終了するかテスト"""
        self.manager.is_voice_mode = True
        self.manager.last_number = 1

        await main.recv_talk_text("ゼロ")
        self.assertFalse(self.manager.is_voice_mode)
        self.manager.broadcast.assert_any_call({"type": "MODE_CHANGE", "value": "normal"})
