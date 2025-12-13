# Spotify Activity Updater

このプロジェクトは、Spotify Web APIからアクティビティ情報を取得して、GitHubプロフィールのREADME.mdに自動的に表示するためのツールです。

## 機能

- Spotify Web APIから最新トラックを取得
- Spotify Web APIから最長期間（long_term）のトップトラックランキングを取得
- README.mdを自動更新
- GitHub Actionsによる定期実行（1時間ごと）

## セットアップ

### 1. Spotify Developerアプリの作成

1. [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)にアクセス
2. 「Create app」をクリック
3. アプリ名と説明を入力
4. リダイレクトURIを設定（例: `http://localhost:8888/callback`）
5. 「Save」をクリック

### 2. Refresh Tokenの取得

Refresh Tokenを取得するには、OAuth2のAuthorization Code Flowを実行する必要があります。

#### 方法1: 簡単なスクリプトを使用（推奨）

以下のPythonスクリプトを使用してRefresh Tokenを取得できます：

```python
import requests
import base64
from urllib.parse import urlencode

CLIENT_ID = "your_client_id"
CLIENT_SECRET = "your_client_secret"
REDIRECT_URI = "http://localhost:8888/callback"
SCOPE = "user-read-recently-played user-top-read"

# 1. 認証URLを生成
auth_url = "https://accounts.spotify.com/authorize"
params = {
    "client_id": CLIENT_ID,
    "response_type": "code",
    "redirect_uri": REDIRECT_URI,
    "scope": SCOPE
}
print(f"以下のURLにアクセスしてください:\n{auth_url}?{urlencode(params)}")

# 2. リダイレクトされたURLからcodeを取得
code = input("リダイレクトされたURLのcodeパラメータを入力してください: ")

# 3. Access TokenとRefresh Tokenを取得
token_url = "https://accounts.spotify.com/api/token"
auth_header = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
headers = {
    "Authorization": f"Basic {auth_header}",
    "Content-Type": "application/x-www-form-urlencoded"
}
data = {
    "grant_type": "authorization_code",
    "code": code,
    "redirect_uri": REDIRECT_URI
}
response = requests.post(token_url, headers=headers, data=data)
tokens = response.json()
print(f"\nRefresh Token: {tokens['refresh_token']}")
```

#### 方法2: ブラウザで手動実行

1. 以下のURLにアクセス（`CLIENT_ID`と`REDIRECT_URI`を置き換える）:
   ```
   https://accounts.spotify.com/authorize?client_id=YOUR_CLIENT_ID&response_type=code&redirect_uri=http://localhost:8888/callback&scope=user-read-recently-played%20user-top-read
   ```
2. 認証後、リダイレクトされたURLから`code`パラメータを取得
3. 以下のコマンドでトークンを取得（`CLIENT_ID`, `CLIENT_SECRET`, `CODE`, `REDIRECT_URI`を置き換える）:
   ```bash
   curl -H "Authorization: Basic $(echo -n 'CLIENT_ID:CLIENT_SECRET' | base64)" \
        -d grant_type=authorization_code \
        -d code=CODE \
        -d redirect_uri=REDIRECT_URI \
        https://accounts.spotify.com/api/token
   ```

### 3. GitHub Secretsの設定

GitHubリポジトリのSettings > Secrets and variables > Actionsで以下のシークレットを設定：

- `SPOTIFY_CLIENT_ID`: Spotify DeveloperアプリのClient ID
- `SPOTIFY_CLIENT_SECRET`: Spotify DeveloperアプリのClient Secret
- `SPOTIFY_REFRESH_TOKEN`: 取得したRefresh Token

### 4. 必要なスコープ

以下のスコープが必要です：
- `user-read-recently-played`: 最近再生したトラックを取得
- `user-top-read`: トップトラックを取得

### 5. 表示される情報

README.mdには以下の情報が表示されます：

#### 🎧 いま聴いてる
- **最新トラック**: 直近で再生したトラック
- **ジャケ写表示**: アルバムアートワーク
- **クリック可能**: カードをクリックするとSpotifyの楽曲ページに遷移

#### 🏆 Top Tracks (All Time)
- **ランキング表示**: 最長期間（long_term、約数年間）のトップ3楽曲
- **ジャケ写表示**: アルバムアートワーク
- **クリック可能**: カードをクリックするとSpotifyの楽曲ページに遷移
- **詳細情報**: 楽曲名、アーティスト名、人気度

### 6. データの取得範囲

- **最新トラック**: 直近で再生した1件のトラック
- **ランキング**: Spotify Web APIの`long_term`期間（約数年間）のトップトラック

## 使用方法

### 手動実行

```bash
python update_music_activity.py
```

### 環境変数の設定

`.env`ファイルを作成して以下の環境変数を設定：

```env
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REFRESH_TOKEN=your_refresh_token
```

### GitHub Actionsによる自動実行

ワークフローは1時間ごとに自動実行され、README.mdが更新されます。

## カスタマイズ

### ランキング期間の変更

`get_track_ranking`メソッドの`time_range`パラメータを変更できます：
- `short_term`: 約4週間
- `medium_term`: 約6ヶ月
- `long_term`: 約数年間（デフォルト）

### ランキング表示件数の変更

`get_track_ranking`メソッドの`limit`パラメータを変更できます（最大50曲、表示は上位3位）。

### 表示形式の変更

`format_latest_track`や`format_track_ranking`メソッドを編集して、表示形式をカスタマイズできます。

## トラブルシューティング

### 403エラー「Insufficient client scope」が発生する場合

このエラーは、現在のRefresh Tokenに必要なスコープ（`user-top-read`）が含まれていない場合に発生します。

**解決方法（推奨）:**

1. **`get_spotify_token.py`スクリプトを使用（最も簡単）:**
   ```bash
   python get_spotify_token.py
   ```
   スクリプトの指示に従って、新しいRefresh Tokenを取得してください。

2. **手動でRefresh Tokenを再取得:**
   - SPOTIFY_SETUP.mdの「2. Refresh Tokenの取得」セクションを参照
   - 認証URLにアクセスする際、必ず以下のスコープを含めてください:
     ```
     user-read-recently-played user-top-read
     ```

3. **取得したRefresh Tokenを更新:**
   - `.env`ファイルの`SPOTIFY_REFRESH_TOKEN`を更新
   - または、GitHub Secretsの`SPOTIFY_REFRESH_TOKEN`を更新

**注意:** 既存のRefresh Tokenは無効化されませんが、新しいスコープを含むRefresh Tokenを取得する必要があります。

### アクセストークンの取得に失敗する場合

- Refresh Tokenが有効か確認してください
- Client IDとClient Secretが正しいか確認してください
- 必要なスコープが設定されているか確認してください

### データが取得できない場合

- Spotifyアカウントで音楽を再生しているか確認してください
- スコープが正しく設定されているか確認してください
- GitHub Actionsのログでエラー詳細を確認してください

### ログの確認

GitHub Actionsの実行ログでエラーの詳細を確認できます。
