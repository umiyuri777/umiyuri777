#!/usr/bin/env python3
"""
SupabaseからSpotifyログを取得してREADME.mdを更新するスクリプト
"""

import os
import json
from datetime import datetime, timedelta
from supabase import create_client, Client
from typing import List, Dict, Any


class SpotifyActivityUpdater:
    def __init__(self):
        """Supabaseクライアントを初期化"""
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY')
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL と SUPABASE_KEY の環境変数が設定されていません")
        
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
    
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
            
            # Supabaseからデータを取得（played_atでフィルタリング）
            response = self.supabase.table('spotify_logs').select(
                'track_name, artist_name, album_name, played_at, duration_ms, popularity, external_urls'
            ).gte(
                'played_at', start_date.isoformat()
            ).order('played_at', desc=True).execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            print(f"Spotifyログの取得中にエラーが発生しました: {e}")
            return []
    
    def format_spotify_logs(self, logs: List[Dict[str, Any]]) -> str:
        """
        SpotifyログをMarkdown形式に整形
        
        Args:
            logs: Spotifyログのリスト
            
        Returns:
            整形されたMarkdown文字列
        """
        if not logs:
            return "🎵 最近の音楽活動はありません"
        
        markdown_lines = ["## 🎵 Recent Music Activity"]
        markdown_lines.append("")
        
        # 日付ごとにグループ化
        daily_logs = {}
        for log in logs:
            date_str = log.get('played_at', '').split('T')[0] if log.get('played_at') else 'Unknown'
            if date_str not in daily_logs:
                daily_logs[date_str] = []
            daily_logs[date_str].append(log)
        
        # 日付順にソート（新しい順）
        for date_str in sorted(daily_logs.keys(), reverse=True):
            logs_for_date = daily_logs[date_str]
            
            # 日付ヘッダー
            formatted_date = self._format_date(date_str)
            markdown_lines.append(f"### {formatted_date}")
            markdown_lines.append("")
            
            # その日の楽曲リスト
            for log in logs_for_date:
                track_name = log.get('track_name', 'Unknown Track')
                artist_name = log.get('artist_name', 'Unknown Artist')
                album_name = log.get('album_name', '')
                played_at = log.get('played_at', '')
                duration_ms = log.get('duration_ms', 0)
                popularity = log.get('popularity', 0)
                external_urls = log.get('external_urls', {})
                
                # 再生時刻を整形
                time_str = ""
                if played_at:
                    try:
                        played_time = datetime.fromisoformat(played_at.replace('Z', '+00:00'))
                        time_str = f" ({played_time.strftime('%H:%M')})"
                    except:
                        pass
                
                # 楽曲の長さを分:秒形式に変換
                duration_str = ""
                if duration_ms:
                    minutes = duration_ms // 60000
                    seconds = (duration_ms % 60000) // 1000
                    duration_str = f" [{minutes}:{seconds:02d}]"
                
                # 人気度を表示
                popularity_str = ""
                if popularity and popularity > 0:
                    popularity_str = f" ⭐{popularity}"
                
                # Spotifyリンクを追加（もしあれば）
                spotify_link = ""
                if external_urls and external_urls.get('spotify'):
                    spotify_link = f" [🎵]({external_urls['spotify']})"
                
                # アルバム名を表示（もしあれば）
                album_str = f" - *{album_name}*" if album_name else ""
                
                markdown_lines.append(
                    f"- 🎶 **{track_name}** - {artist_name}{album_str}{time_str}{duration_str}{popularity_str}{spotify_link}"
                )
            
            markdown_lines.append("")
        
        # 統計情報を追加
        stats = self._calculate_stats(logs)
        if stats:
            markdown_lines.append("### 📊 統計情報")
            markdown_lines.append("")
            markdown_lines.append(f"- **総再生回数**: {stats['total_plays']}回")
            markdown_lines.append(f"- **ユニーク楽曲数**: {stats['unique_tracks']}曲")
            markdown_lines.append(f"- **ユニークアーティスト数**: {stats['unique_artists']}人")
            markdown_lines.append(f"- **総再生時間**: {stats['total_duration']}")
            if stats['avg_popularity'] > 0:
                markdown_lines.append(f"- **平均人気度**: {stats['avg_popularity']:.1f}")
            markdown_lines.append("")
        
        return "\n".join(markdown_lines)
    
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
            return {}
        
        total_plays = len(logs)
        unique_tracks = len(set(log.get('track_name', '') for log in logs))
        unique_artists = len(set(log.get('artist_name', '') for log in logs))
        
        # 総再生時間を計算
        total_duration_ms = sum(log.get('duration_ms', 0) for log in logs)
        total_duration_hours = total_duration_ms / (1000 * 60 * 60)
        
        # 平均人気度を計算
        popularities = [log.get('popularity', 0) for log in logs if log.get('popularity', 0) > 0]
        avg_popularity = sum(popularities) / len(popularities) if popularities else 0
        
        return {
            'total_plays': total_plays,
            'unique_tracks': unique_tracks,
            'unique_artists': unique_artists,
            'total_duration': f"{total_duration_hours:.1f}時間",
            'avg_popularity': avg_popularity
        }
    
    def update_readme(self, spotify_content: str):
        """
        README.mdファイルを更新
        
        Args:
            spotify_content: 追加するSpotifyコンテンツ
        """
        readme_path = 'README.md'
        
        try:
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
                else:
                    # Activitiesセクションが見つからない場合は末尾に追加
                    new_content = content + "\n\n" + start_marker + "\n" + spotify_content + "\n" + end_marker
            
            # ファイルに書き込み
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print("README.mdが正常に更新されました")
            
        except Exception as e:
            print(f"README.mdの更新中にエラーが発生しました: {e}")
            raise
    
    def run(self):
        """メイン実行関数"""
        try:
            print("Spotifyログの取得を開始...")
            logs = self.get_recent_spotify_logs()
            print(f"{len(logs)}件のログを取得しました")
            
            print("ログの整形を開始...")
            formatted_content = self.format_spotify_logs(logs)
            
            print("README.mdの更新を開始...")
            self.update_readme(formatted_content)
            
            print("すべての処理が完了しました！")
            
        except Exception as e:
            print(f"処理中にエラーが発生しました: {e}")
            raise


def main():
    """メイン関数"""
    updater = SpotifyActivityUpdater()
    updater.run()


if __name__ == "__main__":
    main()
