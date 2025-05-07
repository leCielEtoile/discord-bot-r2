# トラブルシューティング

## ✅ Botがオンラインにならない

- `DISCORD_TOKEN`が正しいか確認（config.json）
- Discord Developer PortalでBotが「公開中」か確認
- Botがサーバーに参加しているか確認

## 📦 動画がダウンロードできない

- URLが正しいYouTube動画リンクか確認
- `yt-dlp`により削除済み・地域制限などの可能性あり

## ❌ Cloudflare R2にアップロードできない

- バケット名やキーが間違っていないか確認（config.json）
- 公開設定のURLが正しく構成されているか確認

## ⏰ 自動削除されない

- Botが常時起動しているか？
- `scheduler.py`が正しく `start_scheduler()` を呼び出しているか？
