"""
main.py

Discord Botのエントリーポイント
アプリケーションの起動処理を担当
"""

from bot.core import run_bot


def main():
    """
    アプリケーションのメイン関数。
    Bot を初期化して実行する。
    """
    run_bot()


if __name__ == "__main__":
    main()