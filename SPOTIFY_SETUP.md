# Spotify Activity Updater

このプロジェクトは、Supabaseに保存されているSpotifyログを取得して、GitHubプロフィールのREADME.mdに自動的に表示するためのツールです。

## 機能

- SupabaseからSpotifyログを取得
- ログを日付ごとに整理してMarkdown形式に整形
- README.mdを自動更新
- GitHub Actionsによる定期実行（1時間ごと）

## セットアップ

### 1. Supabaseの設定

Supabaseプロジェクトで以下のテーブル構造を使用します：

```sql
-- Spotify ログテーブルの作成
CREATE TABLE spotify_logs (
    id BIGSERIAL PRIMARY KEY,
    track_name VARCHAR(255) NOT NULL,
    artist_name VARCHAR(255) NOT NULL,
    played_at TIMESTAMPTZ NOT NULL,
    saved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    track_id VARCHAR(50) NOT NULL,
    artist_id VARCHAR(50) NOT NULL,
    album_name VARCHAR(255) NOT NULL,
    album_id VARCHAR(50) NOT NULL,
    duration_ms INTEGER NOT NULL,
    popularity INTEGER,
    external_urls JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- インデックスの作成（パフォーマンス向上のため）
CREATE INDEX idx_spotify_logs_track_id ON spotify_logs(track_id);
CREATE INDEX idx_spotify_logs_artist_id ON spotify_logs(artist_id);
CREATE INDEX idx_spotify_logs_played_at ON spotify_logs(played_at);
CREATE INDEX idx_spotify_logs_artist_name ON spotify_logs(artist_name);
CREATE INDEX idx_spotify_logs_track_name ON spotify_logs(track_name);

-- 複合インデックス（よく使われるクエリパターン用）
CREATE INDEX idx_spotify_logs_track_artist ON spotify_logs(track_name, artist_name);
CREATE INDEX idx_spotify_logs_played_at_desc ON spotify_logs(played_at DESC);

-- RLS（Row Level Security）の設定（オプション）
ALTER TABLE spotify_logs ENABLE ROW LEVEL SECURITY;

-- 全ユーザーが読み取り可能にするポリシー（必要に応じて調整）
CREATE POLICY "Allow read access for all users" ON spotify_logs
    FOR SELECT USING (true);

-- 認証されたユーザーのみが挿入可能にするポリシー
CREATE POLICY "Allow insert for authenticated users" ON spotify_logs
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

-- updated_atカラムを自動更新するトリガー関数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- updated_atトリガーの作成
CREATE TRIGGER update_spotify_logs_updated_at 
    BEFORE UPDATE ON spotify_logs 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();
```

### 2. GitHub Secretsの設定

GitHubリポジトリのSettings > Secrets and variables > Actionsで以下のシークレットを設定：

- `SUPABASE_URL`: SupabaseプロジェクトのURL
- `SUPABASE_KEY`: SupabaseのAPIキー（anon key）

### 3. 表示される情報

README.mdには以下の情報が表示されます：

#### 🏆 楽曲ランキング（過去1週間）
- **ランキング表示**: 再生回数順のトップ3楽曲
- **ジャケ写表示**: アルバムアートワーク（150x150px、角丸スタイル）
- **クリック可能**: ジャケ写をクリックするとSpotifyの楽曲ページに遷移
- **詳細情報**: 楽曲名、アーティスト名、再生回数、人気度

#### 🎵 最近の音楽活動
- **楽曲情報**: 楽曲名、アーティスト名、アルバム名
- **Spotify情報**: 人気度、Spotifyへのリンク

### 4. データの取得範囲

デフォルトでは過去7日間のログを取得します。期間を変更したい場合は、`update_music_activity.py`の`get_recent_spotify_logs`メソッドの`days`パラメータを調整してください。

## 使用方法

### 手動実行

```bash
python update_music_activity.py
```

### GitHub Actionsによる自動実行

ワークフローは1時間ごとに自動実行され、README.mdが更新されます。

## カスタマイズ

### 取得期間の変更

デフォルトでは過去7日間のログを取得します。期間を変更したい場合は、`get_recent_spotify_logs`メソッドの`days`パラメータを調整してください。

### 表示形式の変更

`format_spotify_logs`メソッドを編集して、表示形式をカスタマイズできます。

### 統計情報の追加

`_calculate_stats`メソッドを編集して、表示する統計情報を追加・変更できます。

### 楽曲情報の表示項目

`format_spotify_logs`メソッド内で、表示する楽曲情報の項目を調整できます：
- 楽曲名、アーティスト名、アルバム名
- 再生時刻、楽曲の長さ
- 人気度、Spotifyリンク

### ランキング機能のカスタマイズ

`get_track_ranking`メソッドでランキングの取得件数や期間を調整できます：
- `days`: ランキング対象期間（デフォルト: 7日）
- `limit`: 表示する楽曲数（デフォルト: 3曲）

`format_track_ranking`メソッドでランキングの表示形式を調整できます：
- ジャケ写のサイズ（現在: 150x150px）
- ランキング絵文字（🥇🥈🥉🎵）
- 表示レイアウト


### ログの確認

GitHub Actionsの実行ログでエラーの詳細を確認できます。
