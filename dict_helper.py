def get_first_non_none_value(data, priority_keys):
    """
    指定された優先度リストに従って辞書から値を取得します。
    値が None でない最初のキーに対応する値を返します。

    Args:
        data (dict): 値を取得する対象の辞書。
        priority_keys (list): キーの優先度リスト (例: ["displayName", "id"])。

    Returns:
        str or None: None でない値が見つかった場合はその値。
                     すべてのキーが None または存在しない場合は None。
    """
    for key in priority_keys:
        # 辞書にキーが存在し、かつその値が None でないかを確認
        if key in data and data[key] is not None:
            return data[key]
    # すべてのキーを試しても None でない値が見つからなかった場合
    return None
