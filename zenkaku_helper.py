import re

from kanjize import kanji2number


def kanji_to_int(text):
    """
    漢数字、カタカナ、誤変換しやすい文字を数値に変換する。
    """
    if not text:
        return None

    # 1. 全角数字を半角に変換
    text = text.translate(str.maketrans('０１２３４５６７８９', '0123456789'))

    # 2. 変換テーブル（音声認識の揺れをカバー）
    # 必要に応じてここに追加してください
    replacement_table = {
        "ゼロ": "0",
        "零": "0",
        "中": "十", # 「じゅう」が「ちゅう」と誤認されるケース
    }

    for key, value in replacement_table.items():
        text = text.replace(key, value)

    # 3. 不要な記号を除去（数字、漢数字以外）
    text = re.sub(r'[^\d一二三四五六七八九十百]', '', text)

    if not text:
        return None

    # 4. すでに半角数値のみの場合はそのまま数値化
    if text.isdigit():
        return int(text)

    # 5. 漢数字のパース
    try:
        return kanji2number(text)
    except Exception:
        return None
