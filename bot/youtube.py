"""
bot/youtube.py

YouTube動画のダウンロードと情報取得を行うモジュール。
H.264/AACコーデックを優先的に使用。
"""

import subprocess
import logging
import os
import json
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

def get_video_title(url: str) -> str:
    """
    YouTube動画のタイトルを取得する
    
    Args:
        url: YouTube URL
        
    Returns:
        動画タイトル（取得失敗時は「無題」）
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
    動画ファイルのコーデック情報を取得
    
    Args:
        file_path: 動画ファイルパス
        
    Returns:
        (video_codec, audio_codec): 動画と音声のコーデック名
    """
    try:
        # FFprobeを使用してコーデック情報をJSON形式で取得
        result = subprocess.run([
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", file_path
        ], capture_output=True, text=True, check=True)
        
        info = json.loads(result.stdout)
        
        video_codec = "unknown"
        audio_codec = "unknown"
        
        # ストリーム情報からコーデックを抽出
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
    動画をH.264/AACに変換する
    
    Args:
        input_path: 入力ファイルパス
        output_path: 出力ファイルパス
        
    Returns:
        bool: 変換成功時True
    """
    try:
        # 一時ファイルパス
        temp_output = f"{output_path}.temp.mp4"
        
        # H.264/AACに変換
        subprocess.run([
            "ffmpeg", "-i", input_path, 
            "-c:v", "libx264", "-crf", "23", 
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",  # Web再生に最適化
            "-y",  # 既存ファイルを上書き
            temp_output
        ], check=True)
        
        # 成功したら一時ファイルを目的のファイルに移動
        os.rename(temp_output, output_path)
        
        logger.info(f"Successfully converted video to H.264/AAC: {output_path}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to convert video: {e}")
        
        # 一時ファイルが残っていたら削除
        if os.path.exists(f"{output_path}.temp.mp4"):
            os.remove(f"{output_path}.temp.mp4")
            
        return False

def download_video(url: str, output_path: str, max_height: int = 720) -> bool:
    """
    YouTube動画をダウンロードする。H.264/AACを優先的に選択。
    
    Args:
        url: YouTube URL
        output_path: 保存先パス
        max_height: 最大高さ（ピクセル）
        
    Returns:
        bool: ダウンロード成功時True
    """
    try:
        # H.264/AACを優先的に選択するフォーマット指定
        format_spec = (
            # 1. 最大720pまでのmp4コンテナのH.264ビデオとAACオーディオ
            "bestvideo[height<=720][vcodec^=avc][ext=mp4]+bestaudio[acodec=aac][ext=m4a]/"\
            # 2. 最大720pまでのH.264ビデオとAACオーディオ
            "bestvideo[height<=720][vcodec^=avc]+bestaudio[acodec=aac]/"\
            # 3. 720p以下のmp4形式
            "best[height<=720][ext=mp4]/"\
            # 4. 720p以下の任意のコーデック
            "best[height<=720]"
        )
        
        # ダウンロード実行
        subprocess.run([
            "yt-dlp",
            "-f", format_spec,
            "--merge-output-format", "mp4",
            "-o", output_path,
            url
        ], check=True, timeout=240)  # タイムアウトを4分に延長
        
        # コーデックチェック
        video_codec, audio_codec = check_video_codec(output_path)
        
        # H.264でない場合は変換
        if video_codec != "h264":
            logger.info(f"Video codec is {video_codec}, converting to H.264...")
            
            # 一時ファイルにリネーム
            temp_path = f"{output_path}.original"
            os.rename(output_path, temp_path)
            
            # 変換
            if convert_to_h264(temp_path, output_path):
                # 元ファイル削除
                os.remove(temp_path)
            else:
                # 変換失敗時は元ファイルを戻す
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
    URLがYouTubeのものか検証する
    
    Args:
        url: 検証対象URL
        
    Returns:
        bool: YouTubeのURLならTrue
    """
    import re
    return bool(re.match(r"^(https?://)?(www\.)?(youtube\.com|youtu\.be)/", url))