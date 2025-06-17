"""
bot/youtube.py

YouTube動画のダウンロードと処理を行うモジュール
yt-dlpとFFmpegを使用してH.264/AACコーデックに最適化
プレイリストURL対策とURL正規化機能を含む
"""

import subprocess
import logging
import os
import json
import re
from typing import Tuple, Optional
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

def normalize_youtube_url(url: str) -> str:
    """
    YouTube URLを正規化してプレイリスト情報を除去
    v=パラメータのみを抽出して単一動画URLに変換
    
    Args:
        url: 正規化対象のYouTube URL
        
    Returns:
        str: 正規化された単一動画URL
        
    Examples:
        >>> normalize_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLxxxxxx")
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        
        >>> normalize_youtube_url("https://youtu.be/dQw4w9WgXcQ?list=PLxxxxxx")
        "https://youtu.be/dQw4w9WgXcQ"
    """
    try:
        # URLの解析
        parsed = urlparse(url)
        
        # youtu.be 短縮URL形式の処理
        if parsed.netloc in ['youtu.be', 'www.youtu.be']:
            # パスから動画IDを抽出 (/dQw4w9WgXcQ 形式)
            video_id = parsed.path.strip('/')
            if video_id:
                return f"https://youtu.be/{video_id}"
        
        # youtube.com 標準URL形式の処理
        elif parsed.netloc in ['youtube.com', 'www.youtube.com', 'm.youtube.com']:
            # クエリパラメータを解析
            query_params = parse_qs(parsed.query)
            
            # v=パラメータから動画IDを抽出
            if 'v' in query_params and query_params['v']:
                video_id = query_params['v'][0]
                return f"https://www.youtube.com/watch?v={video_id}"
        
        # 正規化できない場合は元のURLを返す
        logger.warning(f"Could not normalize URL: {url}")
        return url
        
    except Exception as e:
        logger.warning(f"URL normalization failed for {url}: {e}")
        return url

def validate_youtube_url(url: str) -> bool:
    """
    URLがYouTubeの有効なURLかどうかを検証
    
    Args:
        url: 検証対象のURL文字列
        
    Returns:
        bool: YouTubeのURLである場合True
    """
    # 基本的なYouTube URLパターンの確認
    youtube_patterns = [
        r"^(https?://)?(www\.)?(youtube\.com|youtu\.be|m\.youtube\.com)/",
        r"^(https?://)?youtube\.com/watch\?.*v=",
        r"^(https?://)?youtu\.be/[a-zA-Z0-9_-]+"
    ]
    
    return any(re.search(pattern, url) for pattern in youtube_patterns)

def extract_video_id(url: str) -> str:
    """
    YouTube URLから動画IDを抽出
    
    Args:
        url: YouTube URL
        
    Returns:
        str: 動画ID（抽出できない場合は空文字列）
    """
    try:
        # 正規化されたURLから動画IDを抽出
        normalized_url = normalize_youtube_url(url)
        parsed = urlparse(normalized_url)
        
        # youtu.be形式
        if parsed.netloc in ['youtu.be', 'www.youtu.be']:
            return parsed.path.strip('/')
        
        # youtube.com形式
        elif parsed.netloc in ['youtube.com', 'www.youtube.com', 'm.youtube.com']:
            query_params = parse_qs(parsed.query)
            if 'v' in query_params and query_params['v']:
                return query_params['v'][0]
        
        return ""
        
    except Exception as e:
        logger.warning(f"Video ID extraction failed for {url}: {e}")
        return ""

def get_video_title(url: str) -> str:
    """
    YouTube動画のタイトルを取得
    URL正規化を適用してプレイリスト情報を除去
    
    Args:
        url: YouTube動画のURL
        
    Returns:
        str: 動画タイトル（取得失敗時は「無題」を返す）
    """
    try:
        # URLを正規化してプレイリスト情報を除去
        normalized_url = normalize_youtube_url(url)
        
        result = subprocess.run(
            ["yt-dlp", "--get-title", normalized_url],
            capture_output=True, text=True, check=True, timeout=30
        )
        title = result.stdout.strip()
        logger.info(f"Retrieved title: {title} for URL: {normalized_url}")
        return title
    except Exception as e:
        logger.warning(f"Title fetch failed for {url}: {e}")
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
    URL正規化を適用してプレイリスト情報を除去
    
    Args:
        url: ダウンロード対象のYouTube URL
        output_path: 保存先ファイルパス
        max_height: 最大解像度の高さ（ピクセル、デフォルト720p）
        
    Returns:
        bool: ダウンロード成功時True
    """
    try:
        # URLを正規化してプレイリスト情報を除去
        normalized_url = normalize_youtube_url(url)
        video_id = extract_video_id(normalized_url)
        
        logger.info(f"Downloading video: {video_id} from normalized URL: {normalized_url}")
        
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
        
        # yt-dlpでダウンロード実行（正規化されたURLを使用）
        subprocess.run([
            "yt-dlp",
            "-f", format_spec,
            "--merge-output-format", "mp4",  # 最終的にMP4に統合
            "--no-playlist",                 # プレイリスト無効化
            "-o", output_path,
            normalized_url
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