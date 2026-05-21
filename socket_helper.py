import socket


# ポート 0 を指定して空きポートを探す関数
def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))  # OSに空きポートを割り当てさせる
        return s.getsockname()[1]
