"""
bot/youtube.py

YouTube動画のダウンロードと処理を行うモジュール
yt-dlpとFFmpegを使用してH.264/AACコーデックに最適化
"""

import subprocess
import logging
import os
import json
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

def get_video_title(url: str) -> str:
    """
    YouTube動画のタイトルを取得
    
    Args:
        url: YouTube動画のURL
        
    Returns:
        str: 動画タイトル（取得失敗時は「無題」を返す）
    """
    try:
        result = subprocess.run(
            ["yt-dlp", "--get-title", url],
            capture_output=True, text=True, check=True, timeout=30
        )
        return result.stdout.strip()
    except Exception as e:
        logger.warning(f"Title fetch failed: {e}")
        return "無題"

def check_video_codec(file_path: str) -> Tuple[str, str]:
    """
    動画ファイルのコーデック情報をFFprobeで取得
    
    Args:
        file_path: 検査する動画ファイルのパス
        
    Returns:
        Tuple[str, str]: (動画コーデック名, 音声コーデック名)
    """
    try:
        # FFprobeでメディア情報をJSON形式で取得
        result = subprocess.run([
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", file_path
        ], capture_output=True, text=True, check=True)
        
        info = json.loads(result.stdout)
        
        video_codec = "unknown"
        audio_codec = "unknown"
        
        # ストリーム情報を解析してコーデックを特定
        for stream in info.get("streams", []):
            if stream.get("codec_type") == "video":
                video_codec = stream.get("codec_name", "unknown")
            elif stream.get("codec_type") == "audio":
                audio_codec = stream.get("codec_name", "unknown")
        
        logger.info(f"Detected codecs: video={video_codec}, audio={audio_codec}")
        return video_codec, audio_codec
    
    except Exception as e:
        logger.error(f"Failed to check video codec: {e}")
        return "unknown", "unknown"

def convert_to_h264(input_path: str, output_path: str) -> bool:
    """
    動画ファイルをH.264（映像）/AAC（音声）形式に変換
    Web再生に最適化されたMP4ファイルを生成
    
    Args:
        input_path: 変換元ファイルのパス
        output_path: 変換後ファイルの保存パス
        
    Returns:
        bool: 変換成功時True
    """
    try:
        # 安全な一時ファイル名を使用
        temp_output = f"{output_path}.temp.mp4"
        
        # FFmpegによる変換（Web再生最適化設定）
        subprocess.run([
            "ffmpeg", "-i", input_path, 
            "-c:v", "libx264", "-crf", "23",      # H.264コーデック、品質設定
            "-c:a", "aac", "-b:a", "128k",        # AACコーデック、ビットレート
            "-movflags", "+faststart",            # Web再生開始の高速化
            "-y",                                 # 既存ファイル上書き確認をスキップ
            temp_output
        ], check=True)
        
        # 変換成功時は一時ファイルを最終ファイル名にリネーム
        os.rename(temp_output, output_path)
        
        logger.info(f"Successfully converted video to H.264/AAC: {output_path}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to convert video: {e}")
        
        # 失敗時は一時ファイルをクリーンアップ
        if os.path.exists(f"{output_path}.temp.mp4"):
            os.remove(f"{output_path}.temp.mp4")
            
        return False

def download_video(url: str, output_path: str, max_height: int = 720) -> bool:
    """
    YouTube動画をダウンロードしてMP4形式で保存
    H.264/AACコーデックを優先的に選択し、必要に応じて変換
    
    Args:
        url: ダウンロード対象のYouTube URL
        output_path: 保存先ファイルパス
        max_height: 最大解像度の高さ（ピクセル、デフォルト720p）
        
    Returns:
        bool: ダウンロード成功時True
    """
    try:
        # yt-dlpフォーマット指定：Web再生に適したコーデックを優先選択
        format_spec = (
            # 1. 720p以下のMP4コンテナ、H.264+AAC
            "bestvideo[height<=720][vcodec^=avc][ext=mp4]+bestaudio[acodec=aac][ext=m4a]/"\
            # 2. 720p以下のH.264+AAC（コンテナ問わず）
            "bestvideo[height<=720][vcodec^=avc]+bestaudio[acodec=aac]/"\
            # 3. 720p以下のMP4形式
            "best[height<=720][ext=mp4]/"\
            # 4. 720p以下の任意フォーマット（フォールバック）
            "best[height<=720]"
        )
        
        # yt-dlpでダウンロード実行
        subprocess.run([
            "yt-dlp",
            "-f", format_spec,
            "--merge-output-format", "mp4",  # 最終的にMP4に統合
            "-o", output_path,
            url
        ], check=True, timeout=240)  # 4分のタイムアウト
        
        # ダウンロード後のコーデック確認
        video_codec, audio_codec = check_video_codec(output_path)
        
        # H.264でない場合は変換を実行
        if video_codec != "h264":
            logger.info(f"Video codec is {video_codec}, converting to H.264...")
            
            # 元ファイルを一時的にリネーム
            temp_path = f"{output_path}.original"
            os.rename(output_path, temp_path)
            
            # H.264/AACに変換
            if convert_to_h264(temp_path, output_path):
                # 変換成功時は元ファイルを削除
                os.remove(temp_path)
            else:
                # 変換失敗時は元ファイルを復元
                os.rename(temp_path, output_path)
                logger.warning("Conversion failed, using original file")
        
        return True
    
    except subprocess.TimeoutExpired:
        logger.error("yt-dlp timeout")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"yt-dlp failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False

def validate_youtube_url(url: str) -> bool:
    """
    URLがYouTubeの有効なURLかどうかを検証
    
    Args:
        url: 検証対象のURL文字列
        
    Returns:
        bool: YouTubeのURLである場合True
    """
    import re
    # YouTube URLの正規表現パターンマッチング
    return bool(re.match(r"^(https?://)?(www\.)?(youtube\.com|youtu\.be)/", url))