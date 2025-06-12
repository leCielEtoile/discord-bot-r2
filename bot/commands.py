"""
commands.py

Discord のスラッシュコマンドを定義するモジュール。
ユーザーによる動画保存、削除、閲覧、管理者による制限変更などの機能を提供。
"""

import discord
from discord import app_commands
import logging
from datetime import datetime
import os
import re
import subprocess

from bot.db import (
    save_mapping,
    get_mapping,
    log_upload,
    list_user_files,
    delete_upload,
)
from bot.r2 import upload_to_r2, generate_public_url, delete_from_r2
from bot.utils import is_valid_filename, has_permission, is_admin
from bot.config import ALLOWED_GUILD_ID, DEFAULT_UPLOAD_LIMIT, ADMIN_ROLE
from bot.ui import PagedFileView

logger = logging.getLogger(__name__)


def register_commands(tree: app_commands.CommandTree):
    """
    Discord Bot に登録するすべてのスラッシュコマンドを定義する。
    管理者専用コマンドと一般ユーザー向けコマンドを含む。
    """

    @tree.command(name="setlimit", description="指定ユーザーのアップロード上限を設定（管理者のみ）")
    @app_commands.describe(user="対象のユーザー", limit="新しいアップロード上限（0で無制限）")
    async def setlimit(interaction: discord.Interaction, user: discord.Member, limit: int):
        """
        管理者が対象ユーザーのアップロード可能数（上限）を設定する。
        0 を指定した場合は無制限として扱う。
        """
        logger.info(f"/setlimit invoked by {interaction.user} for {user} with limit={limit}")
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ 管理者権限がありません。", ephemeral=True)
            logger.warning(f"Permission denied for setlimit by {interaction.user}")
            return

        mapping = get_mapping(str(user.id))
        if not mapping:
            await interaction.response.send_message("⚠️ 対象ユーザーは設定されていません。", ephemeral=True)
            logger.warning(f"setlimit failed: no mapping found for {user}")
            return

        # 上限を更新して保存
        save_mapping(str(user.id), mapping[0], mapping[1], limit)
        logger.info(f"Upload limit updated: {user} = {limit}")
        await interaction.response.send_message(
            f"✅ {user.display_name} のアップロード上限を {limit if limit > 0 else '無制限'} に設定しました。",
            ephemeral=True,
        )

    @tree.command(name="changefolder", description="対象フォルダを変更します（管理者のみ）")
    @app_commands.describe(user="対象ユーザー（指定しない場合は自身の名前に戻す）")
    async def changefolder(interaction: discord.Interaction, user: discord.Member = None):
        """
        管理者が現在のアップロード先フォルダ名（folder_name）を変更できるコマンド。
        引数なしで実行した場合、自分自身のユーザー名に戻す。
        """
        logger.info(f"/changefolder invoked by {interaction.user} for {user or interaction.user}")
        if not is_admin(interaction.user):
            await interaction.response.send_message("❌ 管理者権限がありません。", ephemeral=True)
            logger.warning(f"Permission denied for changefolder by {interaction.user}")
            return

        target = user or interaction.user
        discord_id = str(target.id)
        new_folder_name = target.name

        # マッピングがない場合は新規作成、あれば更新
        mapping = get_mapping(discord_id)
        if not mapping:
            save_mapping(discord_id, new_folder_name, "", DEFAULT_UPLOAD_LIMIT)
            logger.info(f"Folder mapping created for {target}: {new_folder_name}")
        else:
            save_mapping(discord_id, new_folder_name, mapping[1], mapping[2])
            logger.info(f"Folder mapping updated for {target}: {new_folder_name}")

        await interaction.response.send_message(
            f"✅ `{target.display_name}` のフォルダ名を `{new_folder_name}` に設定しました。", ephemeral=True
        )

    @tree.command(name="upload", description="YouTube動画をダウンロードしてR2に保存します")
    @app_commands.describe(
        url="YouTube動画のURL",
        filename="保存するファイル名（拡張子なし）"
    )
    async def upload(interaction: discord.Interaction, url: str, filename: str):
        """
        YouTube 動画をダウンロードし、Cloudflare R2 にアップロードする。
        - 設定された folder_name に保存される。
        - 上限チェック、ファイル名検証、重複確認を行う。
        """
        logger.info(f"/upload invoked by {interaction.user} with url={url} filename={filename}")
        discord_id = str(interaction.user.id)
        member = interaction.guild.get_member(interaction.user.id)

        # コマンド使用権限チェック
        if not has_permission(member):
            await interaction.response.send_message("❌ このコマンドを使用する権限がありません。", ephemeral=True)
            logger.warning(f"Permission denied for upload by {interaction.user}")
            return

        # URLがYouTubeのものか確認
        if not re.match(r"^(https?://)?(www\.)?(youtube\.com|youtu\.be)/", url):
            await interaction.response.send_message("❌ 有効なYouTubeのURLを入力してください。", ephemeral=True)
            logger.warning(f"Invalid URL by {interaction.user}: {url}")
            return

        # 保存先フォルダの取得または初期化
        mapping = get_mapping(discord_id)
        if mapping:
            folder_name, _, upload_limit = mapping
            limit = upload_limit if upload_limit > 0 else DEFAULT_UPLOAD_LIMIT
        else:
            folder_name = interaction.user.name
            limit = DEFAULT_UPLOAD_LIMIT
            save_mapping(discord_id, folder_name, "", limit)
            logger.info(f"Default folder '{folder_name}' registered for {interaction.user}")

        # ファイル名重複チェック
        existing = list_user_files(discord_id)
        if any(f == filename for f, _, _ in existing):
            await interaction.response.send_message(
                f"⚠️ `{filename}.mp4` は既に存在します。別名を指定してください。", ephemeral=True
            )
            logger.warning(f"Duplicate filename for {interaction.user}: {filename}")
            return

        # アップロード上限チェック
        if limit > 0 and len(existing) >= limit:
            await interaction.response.send_message(
                "📦 アップロード上限に達しました。古いファイルを削除してください。", ephemeral=True
            )
            logger.warning(f"Upload limit exceeded for {interaction.user}")
            return

        # ファイル名の安全性確認
        if not is_valid_filename(filename):
            await interaction.response.send_message(
                "⚠️ ファイル名に不正な文字が含まれています。", ephemeral=True
            )
            logger.warning(f"Invalid filename by {interaction.user}: {filename}")
            return

        await interaction.response.send_message("📥 ダウンロードを開始します...", ephemeral=True)

        local_path = f"/tmp/{filename}.mp4"
        r2_path = f"{folder_name}/{filename}.mp4"

        # YouTube動画タイトル取得
        try:
            title_result = subprocess.run(
                ["yt-dlp", "--get-title", url],
                capture_output=True, text=True, check=True, timeout=30
            )
            video_title = title_result.stdout.strip()
        except Exception as e:
            logger.warning(f"Title fetch failed: {e}")
            video_title = "無題"

        # yt-dlpで動画を720p以下でダウンロード
        try:
            subprocess.run([
                "yt-dlp",
                "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]",
                "--merge-output-format", "mp4",
                "-o", local_path,
                url
            ], check=True, timeout=120)
        except subprocess.TimeoutExpired:
            await interaction.followup.send("⌛ ダウンロードがタイムアウトしました。", ephemeral=True)
            logger.error("yt-dlp timeout")
            return
        except subprocess.CalledProcessError:
            await interaction.followup.send("⚠️ ダウンロードに失敗しました。", ephemeral=True)
            logger.error("yt-dlp failed")
            return

        # R2へのアップロードおよびDB記録
        try:
            upload_to_r2(local_path, r2_path)
            log_upload(discord_id, folder_name, filename, r2_path, datetime.utcnow(), video_title)
            await interaction.followup.send(
                f"✅ アップロード完了！\n🔗 公開URL: {generate_public_url(r2_path)}", ephemeral=True
            )
            logger.info(f"Upload success: {interaction.user} -> {r2_path}")
        except Exception as e:
            await interaction.followup.send(f"⚠️ アップロードに失敗しました: {e}", ephemeral=True)
            logger.error(f"Upload failed: {e}")
        finally:
            if os.path.exists(local_path):
                os.remove(local_path)

    @tree.command(name="myfiles", description="アップロード済みのファイル一覧を表示します")
    async def myfiles(interaction: discord.Interaction):
        """
        自分の保存フォルダにアップロードされた動画を一覧表示する。
        ページネーションと削除UIが含まれる。
        """
        logger.info(f"/myfiles invoked by {interaction.user}")

        # ユーザーID取得
        user_id = str(interaction.user.id)

        # ファイル一覧をDBから取得
        try:
            rows = list_user_files(user_id)
        except Exception as e:
            logger.error(f"DB取得に失敗: {e}")
            await interaction.response.send_message("⚠️ ファイル一覧の取得に失敗しました。", ephemeral=True)
            return

        # ファイルが存在しない場合の応答
        if not rows:
            await interaction.response.send_message("📂 アップロード履歴がありません。", ephemeral=True)
            logger.info(f"No files found for {interaction.user}")
            return

        # ページビューUIを表示
        try:
            view = PagedFileView(user_id, rows)
            embed = view.get_current_embed()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

            try:
                view.message = await interaction.original_response()
                logger.debug("view.message successfully assigned")
            except Exception as e:
                logger.warning(f"view.message 設定に失敗: {e}")

            logger.info(f"Displayed file list to {interaction.user}")
        except Exception as e:
            logger.error(f"/myfiles UI生成中エラー: {e}")
            await interaction.followup.send("⚠️ 表示に失敗しました。", ephemeral=True)
