"""
utils.py

バリデーションおよび Discord メンバーの権限チェックを提供するユーティリティ関数群。
"""

import re
import discord

from bot.config import ALLOWED_ROLE

def is_valid_filename(name: str) -> bool:
    """
    ファイル名が英数字、アンダースコア、ハイフンのみで構成されているかを検証する。

    Args:
        name: 検証対象のファイル名文字列

    Returns:
        True: 許可された形式
        False: 禁止された形式
    """
    return re.fullmatch(r"[a-zA-Z0-9_\-]+", name) is not None

def has_permission(member: discord.Member) -> bool:
    """
    Discord メンバーが設定された許可ロールを保有しているかを判定する。

    Args:
        member: Discord メンバーオブジェクト

    Returns:
        True: 権限あり
        False: 権限なし
    """
    return any(role.name == ALLOWED_ROLE for role in member.roles)

def is_admin(user: discord.abc.User | discord.Member) -> bool:
    """
    ユーザーが管理者ロール（ADMIN_ROLE）を持っているかを判定。

    Args:
        user: チェック対象の Discord ユーザー or メンバー

    Returns:
        True: 管理者
        False: 一般ユーザー
    """
    from bot.config import ADMIN_ROLE

    # メンバー型でロール確認ができる場合のみ
    if hasattr(user, "roles"):
        return any(role.name == ADMIN_ROLE for role in user.roles)
    return False