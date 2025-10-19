#!/usr/bin/env python3
"""
SupabaseからSpotifyログを取得してREADME.mdを更新するスクリプト
"""

import os
import json
import logging
from datetime import datetime, timedelta
from supabase import create_client, Client
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import httpx

class SpotifyActivityUpdater:
    def __init__(self):
        """Supabaseクライアントを初期化"""
        # ログ設定
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY')
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL と SUPABASE_KEY の環境変数が設定されていません")
        
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        self.logger.info("Supabaseクライアントが初期化されました")
    
    def get_recent_spotify_logs(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        指定された日数分のSpotifyログを取得
        
        Args:
            days: 取得する日数（デフォルト: 7日）
            
        Returns:
            Spotifyログのリスト
        """
        try:
            # 過去N日間のデータを取得
            start_date = datetime.now() - timedelta(days=days)
            self.logger.info(f"過去{days}日間のSpotifyログを取得開始 (開始日: {start_date.isoformat()})")
            
            # Supabaseからデータを取得（played_atでフィルタリング）
            response = self.supabase.table('spotify_logs').select(
                'track_name, artist_name, album_name, played_at, duration_ms, popularity, external_urls'
            ).gte(
                'played_at', start_date.isoformat()
            ).order('played_at', desc=True).execute()
            
            # レスポンスをJSONとして処理
            if hasattr(response, 'data') and response.data:
                self.logger.info(f"{len(response.data)}件のログを取得しました")
                # JSONデータをログ出力（デバッグ用）
                self.logger.debug(f"取得したデータ: {json.dumps(response.data[:2], ensure_ascii=False, indent=2)}")
                return response.data
            else:
                self.logger.warning("レスポンスにデータが含まれていません")
                return []
            
        except Exception as e:
            self.logger.error(f"Spotifyログの取得中にエラーが発生しました: {e}")
            self.logger.error(f"エラーの詳細: {str(e)}")
            return []
    
    def get_track_ranking(self, days: int = 7, limit: int = 10) -> List[Dict[str, Any]]:
        """
        指定された日数分の楽曲ランキングを取得
        
        Args:
            days: 取得する日数（デフォルト: 7日）
            limit: 取得する楽曲数（デフォルト: 10曲）
            
        Returns:
            楽曲ランキングのリスト
        """
        try:
            # 過去N日間のデータを取得
            start_date = datetime.now() - timedelta(days=days)
            self.logger.info(f"過去{days}日間の楽曲ランキングを取得開始 (開始日: {start_date.isoformat()})")
            
            # Supabaseからランキングデータを取得
            response = self.supabase.table('spotify_logs').select(
                'track_name, artist_name, album_name, track_id, album_id, external_urls, popularity'
            ).gte(
                'played_at', start_date.isoformat()
            ).execute()
            
            if hasattr(response, 'data') and response.data:
                # 楽曲ごとに再生回数を集計
                track_counts = {}
                for log in response.data:
                    track_key = f"{log.get('track_name', '')}|{log.get('artist_name', '')}"
                    if track_key not in track_counts:
                        track_counts[track_key] = {
                            'track_name': log.get('track_name', ''),
                            'artist_name': log.get('artist_name', ''),
                            'album_name': log.get('album_name', ''),
                            'track_id': log.get('track_id', ''),
                            'album_id': log.get('album_id', ''),
                            'external_urls': log.get('external_urls', {}),
                            'popularity': log.get('popularity', 0),
                            'play_count': 0
                        }
                    track_counts[track_key]['play_count'] += 1
                
                # 再生回数でソートして上位を取得
                ranking = sorted(track_counts.values(), key=lambda x: x['play_count'], reverse=True)[:limit]
                
                self.logger.info(f"{len(ranking)}曲のランキングを取得しました")
                return ranking
            else:
                self.logger.warning("ランキングデータが取得できませんでした")
                return []
            
        except Exception as e:
            self.logger.error(f"楽曲ランキングの取得中にエラーが発生しました: {e}")
            return []
    
    def format_track_ranking(self, ranking: List[Dict[str, Any]]) -> str:
        """
        楽曲ランキングをMarkdown形式に整形
        
        Args:
            ranking: 楽曲ランキングのリスト
            
        Returns:
            整形されたMarkdown文字列
        """
        if not ranking:
            self.logger.info("ランキングが空のため、デフォルトメッセージを返します")
            return "🏆 ランキングデータがありません"
        
        self.logger.info(f"{len(ranking)}曲のランキングをMarkdown形式に整形開始")
        
        markdown_lines = ["## 🏆 Top Tracks (過去1週間)"]
        markdown_lines.append("")
        
        # ランキング表示（ジャケ写付き）
        for i, track in enumerate(ranking, 1):
            track_name = track.get('track_name', 'Unknown Track')
            artist_name = track.get('artist_name', 'Unknown Artist')
            album_name = track.get('album_name', '')
            album_id = track.get('album_id', '')
            track_id = track.get('track_id', '')
            external_urls_raw = track.get('external_urls', {})
            play_count = track.get('play_count', 0)
            popularity = track.get('popularity', 0)
            
            # external_urlsをJSON文字列から辞書型にキャスト
            external_urls = self._parse_external_urls(external_urls_raw)
            
            # Spotifyリンクを取得
            spotify_url = ""
            if external_urls and isinstance(external_urls, dict) and 'spotify' in external_urls:
                spotify_url = external_urls['spotify']
            
            # ジャケ写のURLを取得（oEmbedからthumbnail_urlを使用）
            # external_urlsが無い場合はtrack_idからURLを生成してフォールバック
            album_art_url = ""
            oembed_target_url = spotify_url or (f"https://open.spotify.com/track/{track_id}" if track_id else "")
            if oembed_target_url:
                album_art_url = self._get_album_art_via_oembed(oembed_target_url)
            
            # ランキング表示
            rank_emoji = self._get_rank_emoji(i)
            
            # 人気度を表示
            popularity_str = ""
            if popularity and popularity > 0:
                popularity_str = f" ⭐{popularity}"
            
            # ジャケ写付きの表示
            if album_art_url and spotify_url:
                # ジャケ写をクリック可能にしてSpotifyリンクに飛ばす
                markdown_lines.append(f"### {rank_emoji} {i}位")
                markdown_lines.append(f"**{play_count}回** | [{track_name}]({spotify_url}) - {artist_name}{popularity_str}")
                markdown_lines.append(f"<a href=\"{spotify_url}\"><img src=\"{album_art_url}\" width=\"150\" height=\"150\" alt=\"{album_name}\" style=\"border-radius: 8px;\" /></a>")
            elif spotify_url:
                # Spotifyリンクのみの場合
                markdown_lines.append(f"### {rank_emoji} {i}位")
                markdown_lines.append(f"**{play_count}回** | [{track_name}]({spotify_url}) - {artist_name}{popularity_str}")
            else:
                # リンクなしの場合
                markdown_lines.append(f"### {rank_emoji} {i}位")
                markdown_lines.append(f"**{play_count}回** | **{track_name}** - {artist_name}{popularity_str}")
            
            markdown_lines.append("")
        
        result = "\n".join(markdown_lines)
        self.logger.info(f"ランキングMarkdown形式の整形が完了しました (文字数: {len(result)})")
        return result
    
    def _get_album_art_via_oembed(self, spotify_url: str) -> str:
        """Spotify oEmbed APIからthumbnail_urlを取得して返す。
        ネットワークエラーや予期しないレスポンス時は空文字を返す。
        """
        if not spotify_url:
            return ""
        try:
            response = httpx.get(
                "https://open.spotify.com/oembed",
                params={"url": spotify_url},
                timeout=10.0,
                follow_redirects=True,
            )
            if response.status_code != 200:
                self.logger.warning(f"oEmbedの取得に失敗しました (status={response.status_code}) url={spotify_url}")
                return ""
            data = response.json()
            thumbnail_url = data.get("thumbnail_url", "")
            if isinstance(thumbnail_url, str):
                return thumbnail_url
            return ""
        except Exception as e:
            self.logger.warning(f"oEmbed取得中に例外が発生しました: {e}")
            return ""

    def _get_rank_emoji(self, rank: int) -> str:
        """ランキングに応じた絵文字を返す"""
        if rank == 1:
            return "🥇"
        elif rank == 2:
            return "🥈"
        elif rank == 3:
            return "🥉"
        else:
            return "🎵"
    
    def _parse_external_urls(self, external_urls_raw) -> Dict[str, Any]:
        """
        external_urlsをJSON文字列から辞書型にキャスト
        
        Args:
            external_urls_raw: JSON文字列または辞書型のデータ
            
        Returns:
            辞書型のexternal_urls
        """
        try:
            # 既に辞書型の場合はそのまま返す
            if isinstance(external_urls_raw, dict):
                return external_urls_raw
            
            # 文字列の場合はJSONパース
            if isinstance(external_urls_raw, str):
                if external_urls_raw.strip():  # 空文字列でない場合
                    parsed = json.loads(external_urls_raw)
                    self.logger.debug(f"JSON文字列をパースしました: {parsed}")
                    return parsed
                else:
                    return {}
            
            # その他の型の場合は空辞書を返す
            self.logger.warning(f"予期しない型のexternal_urls: {type(external_urls_raw)}")
            return {}
            
        except json.JSONDecodeError as e:
            self.logger.error(f"external_urlsのJSONパースエラー: {e}")
            self.logger.error(f"パース対象データ: {external_urls_raw}")
            return {}
        except Exception as e:
            self.logger.error(f"external_urlsの処理中にエラーが発生しました: {e}")
            return {}
    
    def _format_date(self, date_str: str) -> str:
        """日付文字列を日本語形式に整形"""
        try:
            date_obj = datetime.fromisoformat(date_str)
            return date_obj.strftime('%Y年%m月%d日')
        except:
            return date_str
    
    def _calculate_stats(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """ログから統計情報を計算"""
        if not logs:
            self.logger.info("ログが空のため、統計情報を計算しません")
            return {}
        
        self.logger.info("統計情報の計算を開始")
        
        total_plays = len(logs)
        unique_tracks = len(set(log.get('track_name', '') for log in logs))
        unique_artists = len(set(log.get('artist_name', '') for log in logs))
        
        # 総再生時間を計算
        total_duration_ms = sum(log.get('duration_ms', 0) for log in logs)
        total_duration_hours = total_duration_ms / (1000 * 60 * 60)
        
        # 平均人気度を計算
        popularities = [log.get('popularity', 0) for log in logs if log.get('popularity', 0) > 0]
        avg_popularity = sum(popularities) / len(popularities) if popularities else 0
        
        stats = {
            'total_plays': total_plays,
            'unique_tracks': unique_tracks,
            'unique_artists': unique_artists,
            'total_duration': f"{total_duration_hours:.1f}時間",
            'avg_popularity': avg_popularity
        }
        
        self.logger.info(f"統計情報の計算完了: {json.dumps(stats, ensure_ascii=False)}")
        return stats
    
    def update_readme(self, spotify_content: str):
        """
        README.mdファイルを更新
        
        Args:
            spotify_content: 追加するSpotifyコンテンツ
        """
        readme_path = 'README.md'
        
        try:
            self.logger.info("README.mdの更新を開始")
            
            # 既存のREADME.mdを読み込み
            with open(readme_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Spotifyセクションの開始と終了マーカー
            start_marker = "<!-- SPOTIFY_ACTIVITY_START -->"
            end_marker = "<!-- SPOTIFY_ACTIVITY_END -->"
            
            # 既存のSpotifyセクションを検索
            start_pos = content.find(start_marker)
            end_pos = content.find(end_marker)
            
            if start_pos != -1 and end_pos != -1:
                # 既存のセクションを置換
                new_content = (
                    content[:start_pos] + 
                    start_marker + "\n" + 
                    spotify_content + "\n" + 
                    end_marker + 
                    content[end_pos + len(end_marker):]
                )
                self.logger.info("既存のSpotifyセクションを置換しました")
            else:
                # 新しいセクションを追加（Activitiesセクションの前に挿入）
                activities_pos = content.find("## 🏃‍♀️ Activities")
                if activities_pos != -1:
                    new_content = (
                        content[:activities_pos] + 
                        start_marker + "\n" + 
                        spotify_content + "\n" + 
                        end_marker + "\n\n" + 
                        content[activities_pos:]
                    )
                    self.logger.info("Activitiesセクションの前にSpotifyセクションを追加しました")
                else:
                    # Activitiesセクションが見つからない場合は末尾に追加
                    new_content = content + "\n\n" + start_marker + "\n" + spotify_content + "\n" + end_marker
                    self.logger.info("ファイル末尾にSpotifyセクションを追加しました")
            
            # ファイルに書き込み
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            self.logger.info("README.mdが正常に更新されました")
            
        except Exception as e:
            self.logger.error(f"README.mdの更新中にエラーが発生しました: {e}")
            self.logger.error(f"エラーの詳細: {str(e)}")
            raise
    
    def run(self):
        """メイン実行関数"""
        try:
            self.logger.info("Spotifyログの取得を開始...")
            logs = self.get_recent_spotify_logs()
            self.logger.info(f"{len(logs)}件のログを取得しました")
            
            self.logger.info("楽曲ランキングの取得を開始...")
            ranking = self.get_track_ranking(limit=3)
            self.logger.info(f"{len(ranking)}曲のランキングを取得しました")
            
            self.logger.info("ランキングの整形を開始...")
            ranking_content = self.format_track_ranking(ranking)
            
            # ランキングとログを結合
            combined_content = ranking_content
            
            self.logger.info("README.mdの更新を開始...")
            self.update_readme(combined_content)
            
            self.logger.info("すべての処理が完了しました！")
            
        except Exception as e:
            self.logger.error(f"処理中にエラーが発生しました: {e}")
            self.logger.error(f"エラーの詳細: {str(e)}")
            raise


def main():
    """メイン関数"""
    load_dotenv()
    
    updater = SpotifyActivityUpdater()
    updater.run()


if __name__ == "__main__":
    main()
