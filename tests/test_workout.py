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
        # 「45」と言った場合、さらに4つ消化されるはず
        await main.recv_talk_text("45")
        self.assertEqual(self.manager.undone, 45)
        self.assertEqual(self.manager.total, 105)

    async def test_undone_increase_after_last_number_set(self):
        """基準値決定(初回の1回消化)後にundoneを10加算した場合の計算テスト"""
        # 1. 音声モード開始と初期状態の設定
        await main.recv_talk_text("筋トレ開始")
        self.manager.undone = 40
        self.manager.total = 100

        # 2. 初回の数値「39」を受信
        # 40 -> 39 への変化（1回消化）が発生し、基準値(last_number)が39になる
        await main.recv_talk_text("39")
        self.assertEqual(self.manager.undone, 39)
        self.assertEqual(self.manager.total, 101)
        self.assertEqual(self.manager.last_number, 39)

        # 3. 外部要因（UIの追加ボタンなど）で undone を 10 加算
        # 39 + 10 = 49 になる
        self.manager.undone += 10
        self.assertEqual(self.manager.undone, 49)

        # 4. 次の数値「35」を受信
        # 期待される計算:
        # 差分: 基準値(39) - 今回の値(35) = 4 消化
        # undone: 49(加算後) - 4 = 45
        # total: 101(前回) + 4 = 105
        await main.recv_talk_text("35")

        self.assertEqual(self.manager.undone, 45)
        self.assertEqual(self.manager.total, 105)
        self.assertEqual(self.manager.last_number, 35)

    async def test_mode_end_at_zero(self):
        """「0」でモードが終了するかテスト"""
        self.manager.is_voice_mode = True
        self.manager.last_number = 1

        await main.recv_talk_text("ゼロ")
        self.assertFalse(self.manager.is_voice_mode)
        self.manager.broadcast.assert_any_call({"type": "MODE_CHANGE", "value": "normal"})
