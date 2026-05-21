def sort_dict_by_schema(data, schema):
    """
    schema の定義順に従って data (dict または list) を再構成する
    """
    # 配列（list）の場合は各要素に対して再帰的に処理を行う
    if isinstance(data, list):
        item_schema = schema.get("items", {})
        return [sort_dict_by_schema(item, item_schema) for item in data]

    # オブジェクト（dict）かつスキーマにプロパティ定義がある場合
    if isinstance(data, dict) and "properties" in schema:
        props = schema.get("properties", {})

        # propertyOrder または記述順に基づいてキーの並び順を決定する
        sorted_keys = sorted(
            props.keys(),
            key=lambda k: props[k].get("propertyOrder", 999)
        )

        result = {}
        for key in sorted_keys:
            if key in data:
                # 子要素に対してもスキーマを適用しつつ再帰的に処理
                result[key] = sort_dict_by_schema(data[key], props[key])

        # スキーマに定義されていない未知のキーがデータにある場合は末尾に保持する
        for key in data:
            if key not in result:
                result[key] = data[key]
        return result

    # 辞書でも配列でもない値はそのまま返す
    return data
