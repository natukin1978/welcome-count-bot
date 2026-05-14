import unittest

from zenkaku_helper import kanji_to_int


class TestZenkakuHelper(unittest.TestCase):

    def test_normal_digit(self):
        """半角数値のテスト"""
        self.assertEqual(kanji_to_int("29"), 29)
        self.assertEqual(kanji_to_int("0"), 0)

    def test_zenkaku_digit(self):
        """全角数値のテスト"""
        self.assertEqual(kanji_to_int("１２"), 12)
        self.assertEqual(kanji_to_int("０"), 0)

    def test_kanji_simple(self):
        """シンプルな漢数字のテスト"""
        self.assertEqual(kanji_to_int("五"), 5)
        self.assertEqual(kanji_to_int("十"), 10)

    def test_kanji_complex(self):
        """複雑な漢数字のテスト"""
        self.assertEqual(kanji_to_int("二十九"), 29)
        self.assertEqual(kanji_to_int("百五"), 105)
        self.assertEqual(kanji_to_int("十一"), 11)

    def test_with_katakana(self):
        """カタカナ表記のテスト"""
        self.assertEqual(kanji_to_int("ゼロ"), 0)

    def test_voice_recognition_fix(self):
        """音声認識の誤変換対応テスト"""
        # 「中」を「十」として処理できているか
        self.assertEqual(kanji_to_int("中九"), 19)
        self.assertEqual(kanji_to_int("中"), 10)

    def test_with_punctuation(self):
        """句読点などが含まれる場合のテスト"""
        self.assertEqual(kanji_to_int("二十九。"), 29)
        self.assertEqual(kanji_to_int("！三"), 3)

    def test_invalid_input(self):
        """無効な入力のテスト"""
        self.assertIsNone(kanji_to_int("あいうえお"))
        self.assertIsNone(kanji_to_int(""))
