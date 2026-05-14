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

    async def test_mode_end_at_zero(self):
        """「0」でモードが終了するかテスト"""
        self.manager.is_voice_mode = True
        self.manager.last_number = 1

        await main.recv_talk_text("ゼロ")
        self.assertFalse(self.manager.is_voice_mode)
        self.manager.broadcast.assert_any_call({"type": "MODE_CHANGE", "value": "normal"})
