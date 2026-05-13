
def kanji_to_int(text):
    """漢数字や全角数字を数値に変換する"""
    # 記号（。や！）を除去し、全角数字を半角に変換
    text = text.translate(str.maketrans('０１２３４５６７８９', '0123456789')).replace('。', '').strip()

    # すでに半角数値のみの場合はそのまま返す
    if text.isdigit():
        return int(text)

    # 簡易的な漢数字変換（1〜99想定）
    kanji_dict = {'一':1, '二':2, '三':3, '四':4, '五':5, '六':6, '七':7, '八':8, '九':9, '十':10}

    # 「二十九」などのパターンを解析
    res = 0
    temp = 0
    for char in text:
        if char in kanji_dict:
            val = kanji_dict[char]
            if val == 10:
                res += (temp if temp != 0 else 1) * 10
                temp = 0
            else:
                temp = val
    res += temp
    return res if res > 0 or text == '0' or text == '零' or text == 'ゼロ' else None
