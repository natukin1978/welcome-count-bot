import re

from kanjize import kanji2number


def kanji_to_int(text):
    """
    純粋な数値・漢数字のみを変換対象とし、
    余計な文字（助数詞や文章）が含まれる場合はNoneを返す。
    """
    if not text:
        return None

    # 1. 全角数字を半角に、不要な記号（句読点）を削除
    text = text.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    text = text.replace('。', '').replace('！', '').replace('？', '').strip()

    # 2. 変換テーブル（カタカナや誤認識の正規化）
    replacement_table = {
        "ゼロ": "0",
        "零": "0",
        "二位": "2",
        "ゴー": "5",
        "中": "10",
        "軸": "19",
    }
    for key, value in replacement_table.items():
        text = text.replace(key, value)

    # 3. 厳格なバリデーション
    # 数字、漢数字（一〜九, 十, 百）以外の文字が含まれていたら無効
    if not re.fullmatch(r'[\d一二三四五六七八九十百]+', text):
        return None

    # 4. 数値変換処理
    if text.isdigit():
        return int(text)

    try:
        # kanjizeを利用して漢数字を数値へ
        return kanji2number(text)
    except Exception:
        return None
