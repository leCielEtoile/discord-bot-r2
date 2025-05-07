# Discord Bot スラッシュコマンド仕様書

## `/setname`

- **説明**: アップロード時の保存先ユーザー名・ファイル名を登録します
- **引数**:
  - `username`: 保存先の名前（英数字/アンダースコア/ハイフンのみ）
  - `filename`: ファイル名（拡張子不要）
- **使用例**:
  ```
  /setname username=myuser filename=myvideo
  ```

---

## `/upload`

- **説明**: 指定したYouTube動画をCloudflare R2に保存します
- **引数**:
  - `url`: YouTube動画URL
- **使用例**:
  ```
  /upload url=https://youtube.com/watch?v=abc123
  ```

---

## `/myfiles`

- **説明**: 自分がアップロードした動画の一覧を表示します
- **引数**: なし
- **戻り値**: 公開URL付きのファイル一覧
