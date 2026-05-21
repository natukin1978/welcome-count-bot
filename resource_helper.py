import os
import sys


def get_resource_path(relative_path: str):
    """ 同梱ファイル(HTML/Schema)用：exe内部の一時フォルダを参照 """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)
