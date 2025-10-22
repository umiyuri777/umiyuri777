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
import base64
from html import escape
from urllib.parse import quote

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
        
        # SVGディレクトリの作成
        self.svg_dir = "SVG"
        os.makedirs(self.svg_dir, exist_ok=True)
        self.logger.info(f"SVGディレクトリを確認/作成しました: {self.svg_dir}")
    
    def _xml_attr(self, value: str) -> str:
        """SVG/XMLの属性用に最低限のエスケープを行う。
        主に &、<、>、" をエスケープして属性値の破損を防ぐ。
        """
        if value is None:
            return ''
        return (
            str(value)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
        )

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
        楽曲ランキングをSVGカード形式に整形（上位3位固定）
        
        Args:
            ranking: 楽曲ランキングのリスト
            
        Returns:
            整形されたSVG文字列
        """
        if not ranking:
            self.logger.info("ランキングが空のため、プレースホルダーSVGを生成します")
            placeholder = {
                'track_name': 'No Track',
                'artist_name': '—',
                'album_name': '',
                'track_id': '',
                'album_id': '',
                'external_urls': {},
                'play_count': 0
            }
            svg_card = self._create_ranking_svg_card([placeholder, placeholder, placeholder])
            svg_filename = "track_ranking.svg"
            svg_path = self._save_svg_file(svg_card, svg_filename)
            if svg_path:
                return f"## 🏆 Top Tracks (last 7 days)\n\n![Track Ranking]({svg_path})"
            else:
                return f"## 🏆 Top Tracks (last 7 days)\n\n{svg_card}"
        
        self.logger.info(f"{len(ranking)}曲のランキングをSVGカード形式に整形開始")
        
        # 上位3位までを取得（不足分は空で埋める）
        top_3 = ranking[:3]
        while len(top_3) < 3:
            top_3.append({
                'track_name': '',
                'artist_name': '',
                'album_name': '',
                'track_id': '',
                'album_id': '',
                'external_urls': {},
                'play_count': 0
            })
        
        # SVGカードを生成
        svg_card = self._create_ranking_svg_card(top_3)
        
        # SVGファイルに保存
        svg_filename = "track_ranking.svg"
        svg_path = self._save_svg_file(svg_card, svg_filename)
        
        if svg_path:
            return f"## 🏆 Top Tracks (last 7 days)\n\n![Track Ranking]({svg_path})"
        else:
            return f"## 🏆 Top Tracks (last 7 days)\n\n{svg_card}"

    def _create_ranking_svg_card(self, tracks: List[Dict[str, Any]]) -> str:
        """ランキング用のSVGカードを生成"""
        card_width = 900
        card_height = 200
        card_spacing = 20
        card_width_single = (card_width - card_spacing * 2) // 3

        # SVGヘッダーと基本defs（clipPathは後で動的に追加）
        svg_parts: List[str] = []
        svg_parts.append(f'<svg width="{card_width}" height="{card_height}" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">')
        svg_parts.append('  <defs>')
        svg_parts.append('    <linearGradient id="cardGradient1" x1="0%" y1="0%" x2="100%" y2="100%">')
        svg_parts.append('      <stop offset="0%" style="stop-color:#1a1a2e;stop-opacity:1" />')
        svg_parts.append('      <stop offset="100%" style="stop-color:#16213e;stop-opacity:1" />')
        svg_parts.append('    </linearGradient>')
        svg_parts.append('    <linearGradient id="cardGradient2" x1="0%" y1="0%" x2="100%" y2="100%">')
        svg_parts.append('      <stop offset="0%" style="stop-color:#2d1b69;stop-opacity:1" />')
        svg_parts.append('      <stop offset="100%" style="stop-color:#11998e;stop-opacity:1" />')
        svg_parts.append('    </linearGradient>')
        svg_parts.append('    <linearGradient id="cardGradient3" x1="0%" y1="0%" x2="100%" y2="100%">')
        svg_parts.append('      <stop offset="0%" style="stop-color:#8B0000;stop-opacity:1" />')
        svg_parts.append('      <stop offset="100%" style="stop-color:#FFD700;stop-opacity:1" />')
        svg_parts.append('    </linearGradient>')
        svg_parts.append('    <linearGradient id="shine" x1="0%" y1="0%" x2="100%" y2="0%">')
        svg_parts.append('      <stop offset="0%" style="stop-color:#FFFFFF;stop-opacity:0.25" />')
        svg_parts.append('      <stop offset="60%" style="stop-color:#FFFFFF;stop-opacity:0.05" />')
        svg_parts.append('      <stop offset="100%" style="stop-color:#FFFFFF;stop-opacity:0" />')
        svg_parts.append('    </linearGradient>')
        svg_parts.append('    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">')
        svg_parts.append('      <feDropShadow dx="0" dy="4" stdDeviation="8" flood-color="#000000" flood-opacity="0.3"/>')
        svg_parts.append('    </filter>')

        # 画像クリップ用clipPathをトラックごとに追加
        clip_defs: List[str] = []

        # 本体描画パーツ
        body_parts: List[str] = []

        # 各トラックのカードを生成
        for i, track in enumerate(tracks, 1):
            x_pos = (i - 1) * (card_width_single + card_spacing)

            track_name_raw = track.get('track_name', '')
            artist_name_raw = track.get('artist_name', '')
            album_name_raw = track.get('album_name', '')
            track_id = track.get('track_id', '')
            external_urls_raw = track.get('external_urls', {})
            play_count = track.get('play_count', 0)

            # HTMLエスケープ
            track_name = escape(str(track_name_raw)) if track_name_raw else 'No Track'
            artist_name = escape(str(artist_name_raw)) if artist_name_raw else 'No Artist'
            album_name = escape(str(album_name_raw)) if album_name_raw else ''

            # external_urlsをJSON文字列から辞書型にキャスト
            external_urls = self._parse_external_urls(external_urls_raw)

            # Spotifyリンクを取得
            spotify_url = ""
            if external_urls and isinstance(external_urls, dict) and 'spotify' in external_urls:
                spotify_url = external_urls['spotify']

            # ジャケ写のURLを取得
            album_art_url = ""
            oembed_target_url = spotify_url or (f"https://open.spotify.com/track/{track_id}" if track_id else "")
            if oembed_target_url:
                album_art_url = self._get_album_art_via_oembed(oembed_target_url)

            # 画像はBase64のdata URIで埋め込み（外部参照ブロック対策）
            image_src = self._image_data_uri(album_art_url)

            # ランキングの色とグラデーション
            gradient_id = f"cardGradient{i}"
            rank_color = "#FFD700" if i == 1 else "#C0C0C0" if i == 2 else "#CD7F32"

            # 画像用clipPathとカード範囲のclipPathをdefsに追加
            clip_defs.append(f'    <clipPath id="artClipRank{i}">\n      <circle cx="{x_pos + 60}" cy="100" r="50" />\n    </clipPath>')
            clip_defs.append(f'    <clipPath id="cardClip{i}">\n      <rect x="{x_pos}" y="0" width="{card_width_single}" height="{card_height}" rx="12" ry="12" />\n    </clipPath>')

            # カードの背景（縁取り + シャイン）
            body_parts.append(f'  <!-- カード {i} 背景 -->\n  <rect x="{x_pos}" y="0" width="{card_width_single}" height="{card_height}" rx="12" ry="12" fill="url(#{gradient_id})" filter="url(#shadow)" stroke="#ffffff" stroke-opacity="0.08" stroke-width="1"/>')
            body_parts.append(f'  <!-- シャイン {i} -->\n  <rect x="{x_pos - 10}" y="-10" width="{card_width_single * 0.7}" height="60" fill="url(#shine)" clip-path="url(#cardClip{i})"/>')

            if track_name_raw:  # データがある場合のみ表示
                # アルバムアートワーク
                body_parts.append(f'  <!-- アルバムアートワーク {i} -->\n  <circle cx="{x_pos + 60}" cy="100" r="50" fill="#333" stroke="#555" stroke-width="2"/>\n  <image xlink:href="{self._xml_attr(image_src)}" x="{x_pos + 10}" y="50" width="100" height="100" clip-path="url(#artClipRank{i})"/>')

                # ランキング番号（カード左上に配置して重なりを防ぐ）
                body_parts.append(
                    f'  <!-- ランキング番号 {i} -->\n'
                    f'  <circle cx="{x_pos + 22}" cy="22" r="14" fill="{rank_color}" opacity="0.95" filter="url(#shadow)"/>\n'
                    f'  <text x="{x_pos + 22}" y="22" dominant-baseline="middle" font-family="Arial, sans-serif" font-size="12" font-weight="bold" fill="white" text-anchor="middle">{i}</text>'
                )

                # トラック情報
                track_display = track_name[:20] + ('...' if len(track_name) > 20 else '')
                artist_display = artist_name[:25] + ('...' if len(artist_name) > 25 else '')
                body_parts.append(f'  <!-- トラック情報 {i} -->\n  <text x="{x_pos + 140}" y="80" font-family="Arial, sans-serif" font-size="14" font-weight="bold" fill="#ffffff">\n    <tspan x="{x_pos + 140}">{track_display}</tspan>\n  </text>\n  \n  <text x="{x_pos + 140}" y="100" font-family="Arial, sans-serif" font-size="12" fill="#b3b3b3">\n    <tspan x="{x_pos + 140}">{artist_display}</tspan>\n  </text>\n  \n  <text x="{x_pos + 140}" y="120" font-family="Arial, sans-serif" font-size="12" fill="#1db954">\n    <tspan x="{x_pos + 140}">🔥 {play_count} plays</tspan>\n  </text>')

                # Spotify ロゴ
                body_parts.append(f'  <!-- Spotify ロゴ {i} -->\n  <circle cx="{x_pos + card_width_single - 30}" cy="30" r="15" fill="#1db954"/>\n  <text x="{x_pos + card_width_single - 30}" y="37" font-family="Arial, sans-serif" font-size="10" font-weight="bold" fill="white" text-anchor="middle">♪</text>')

                # リンク（透明なオーバーレイ）
                if spotify_url:
                    body_parts.append(f'  <!-- リンク {i} -->\n  <a xlink:href="{self._xml_attr(spotify_url)}" target="_blank">\n    <rect x="{x_pos}" y="0" width="{card_width_single}" height="{card_height}" fill="transparent"/>\n  </a>')

        # 追加のclipPath定義をdefsに入れて閉じる
        svg_parts.extend(clip_defs)
        svg_parts.append('  </defs>')

        # 本体描画を追加
        svg_parts.extend(body_parts)
        svg_parts.append('</svg>')

        return "\n".join(svg_parts)

    def get_latest_track(self) -> Optional[Dict[str, Any]]:
        """直近で再生した最新トラックを1件取得して返す。
        取得に失敗した場合は None を返す。
        """
        try:
            response = (
                self.supabase
                .table('spotify_logs')
                .select('track_name, artist_name, album_name, track_id, album_id, external_urls, popularity, played_at')
                .order('played_at', desc=True)
                .limit(1)
                .execute()
            )

            if hasattr(response, 'data') and response.data:
                return response.data[0]
            else:
                self.logger.info("最新トラックが見つかりませんでした")
                return None
        except Exception as e:
            self.logger.error(f"最新トラック取得中にエラーが発生しました: {e}")
            return None

    def format_latest_track(self, latest_track: Optional[Dict[str, Any]]) -> str:
        """最新トラック表示をSVGカード形式で整形して返す。"""
        title = "## 🎧 いま聴いてる"
        if not latest_track:
            # データが無い場合でも必ずSVGを生成して返す
            svg_card = self._create_latest_track_svg_card(
                track_name='No Track',
                artist_name='—',
                album_name='',
                album_art_url='',
                spotify_url=''
            )
            svg_filename = "latest_track.svg"
            svg_path = self._save_svg_file(svg_card, svg_filename)
            if svg_path:
                return f"{title}\n\n![Latest Track]({svg_path})"
            else:
                return f"{title}\n\n{svg_card}"

        track_name_raw = latest_track.get('track_name', 'Unknown Track')
        artist_name_raw = latest_track.get('artist_name', 'Unknown Artist')
        album_name_raw = latest_track.get('album_name', '')
        track_id = latest_track.get('track_id', '')
        external_urls_raw = latest_track.get('external_urls', {})

        track_name = escape(str(track_name_raw))
        artist_name = escape(str(artist_name_raw))
        album_name = escape(str(album_name_raw))

        external_urls = self._parse_external_urls(external_urls_raw)
        spotify_url = ""
        if external_urls and isinstance(external_urls, dict) and 'spotify' in external_urls:
            spotify_url = external_urls['spotify']

        album_art_url = ""
        oembed_target_url = spotify_url or (f"https://open.spotify.com/track/{track_id}" if track_id else "")
        if oembed_target_url:
            album_art_url = self._get_album_art_via_oembed(oembed_target_url)

        # SVGカードを生成
        svg_card = self._create_latest_track_svg_card(
            track_name=track_name,
            artist_name=artist_name,
            album_name=album_name,
            album_art_url=album_art_url,
            spotify_url=spotify_url
        )

        # SVGファイルに保存
        svg_filename = "latest_track.svg"
        svg_path = self._save_svg_file(svg_card, svg_filename)
        
        if svg_path:
            return f"{title}\n\n![Latest Track]({svg_path})"
        else:
            return f"{title}\n\n{svg_card}"

    def _create_latest_track_svg_card(self, track_name: str, artist_name: str, album_name: str, album_art_url: str, spotify_url: str) -> str:
        """最新トラック用のSVGカードを生成"""
        # テキストの長さに応じてカードの幅を調整
        max_text_length = max(len(track_name), len(artist_name)) * 8
        card_width = max(400, min(600, max_text_length + 200))
        card_height = 180
        
        # 画像はBase64のdata URIで埋め込み（外部参照ブロック対策）
        image_src = self._image_data_uri(album_art_url)
        
        svg_content = f'''<svg width="{card_width}" height="{card_height}" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <defs>
    <linearGradient id="cardGradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#1a1a2e;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#16213e;stop-opacity:1" />
    </linearGradient>
    <linearGradient id="shineLatest" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#FFFFFF;stop-opacity:0.25" />
      <stop offset="60%" style="stop-color:#FFFFFF;stop-opacity:0.05" />
      <stop offset="100%" style="stop-color:#FFFFFF;stop-opacity:0" />
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="4" stdDeviation="8" flood-color="#000000" flood-opacity="0.3"/>
    </filter>
    <!-- アルバムアート用のクリップパス（円形） -->
    <clipPath id="artClipLatest">
      <circle cx="90" cy="90" r="70" />
    </clipPath>
    <!-- カード全体のクリップパス -->
    <clipPath id="cardClipLatest">
      <rect x="0" y="0" width="{card_width}" height="{card_height}" rx="16" ry="16" />
    </clipPath>
  </defs>
  
  <!-- カード背景 -->
  <rect x="0" y="0" width="{card_width}" height="{card_height}" rx="16" ry="16" fill="url(#cardGradient)" filter="url(#shadow)" stroke="#ffffff" stroke-opacity="0.08" stroke-width="1"/>
  <!-- シャイン -->
  <rect x="-10" y="-10" width="{card_width * 0.6}" height="70" fill="url(#shineLatest)" clip-path="url(#cardClipLatest)"/>
  
  <!-- アルバムアートワーク -->
  <circle cx="90" cy="90" r="70" fill="#333" stroke="#555" stroke-width="2"/>
  <image xlink:href="{self._xml_attr(image_src)}" x="20" y="20" width="140" height="140" clip-path="url(#artClipLatest)"/>
  
  <!-- 再生インジケーターは右側のバーで表示（重なり防止のため丸い再生マークは非表示） -->
  
  <!-- トラック情報 -->
  <text x="200" y="60" font-family="Arial, sans-serif" font-size="20" font-weight="bold" fill="#ffffff">
    <tspan x="200">{track_name[:30]}{'...' if len(track_name) > 30 else ''}</tspan>
  </text>
  
  <text x="200" y="90" font-family="Arial, sans-serif" font-size="14" fill="#b3b3b3">
    <tspan x="200">{artist_name[:35]}{'...' if len(artist_name) > 35 else ''}</tspan>
  </text>
  
  <!-- Spotify ロゴ -->
  <circle cx="{card_width - 40}" cy="40" r="20" fill="#1db954"/>
  <text x="{card_width - 40}" y="47" font-family="Arial, sans-serif" font-size="12" font-weight="bold" fill="white" text-anchor="middle">♪</text>
  
  <!-- 再生中バー（アニメーション付き） -->
  <rect x="200" y="110" width="8" height="20" fill="#1db954" rx="4">
    <animate attributeName="height" values="20;5;20" dur="1.0s" repeatCount="indefinite"/>
    <animate attributeName="y" values="110;117;110" dur="1.0s" repeatCount="indefinite"/>
  </rect>
  <rect x="215" y="110" width="8" height="5" fill="#1db954" rx="4">
    <animate attributeName="height" values="5;20;5" dur="1.0s" repeatCount="indefinite"/>
    <animate attributeName="y" values="117;110;117" dur="1.0s" repeatCount="indefinite"/>
  </rect>
  <rect x="230" y="110" width="8" height="15" fill="#1db954" rx="4">
    <animate attributeName="height" values="15;5;20;15" dur="1.0s" repeatCount="indefinite"/>
    <animate attributeName="y" values="110;115;109;110" dur="1.0s" repeatCount="indefinite"/>
  </rect>
  <rect x="245" y="105" width="8" height="25" fill="#1db954" rx="4">
    <animate attributeName="height" values="25;5;25" dur="1.0s" repeatCount="indefinite"/>
    <animate attributeName="y" values="105;115;105" dur="1.0s" repeatCount="indefinite"/>
  </rect>
  
  <!-- リンク（透明なオーバーレイ） -->
  <a xlink:href="{self._xml_attr(spotify_url)}" target="_blank">
    <rect x="0" y="0" width="{card_width}" height="{card_height}" fill="transparent"/>
  </a>
</svg>'''
        
        return svg_content

    def _save_svg_file(self, svg_content: str, filename: str) -> str:
        """SVGコンテンツをファイルに保存し、相対パスを返す"""
        filepath = os.path.join(self.svg_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(svg_content)
            self.logger.info(f"SVGファイルを保存しました: {filepath}")
            return f"{self.svg_dir}/{filename}"
        except Exception as e:
            self.logger.error(f"SVGファイルの保存中にエラーが発生しました: {e}")
            return ""


    def _image_data_uri(self, source_url: str) -> str:
        """画像を取得し、Base64のdata URIとして返す。
        - 外部参照がブロックされる環境（READMEやローカルビューア）でも表示できるようにするため。
        - Spotifyの画像URLを直接使用して最高品質を維持。
        - リサイズはSVG側で行うため、元画像の品質をそのまま保持。
        失敗時はプレースホルダー画像を使う。
        """
        try:
            if not source_url:
                # プレースホルダー画像を使用
                fb = httpx.get("https://placehold.co/300x300?text=No+Art", timeout=10.0, follow_redirects=True)
                fb.raise_for_status()
                content = fb.content
                content_type = fb.headers.get("Content-Type", "image/png")
            else:
                # Spotifyの画像URLを直接使用（最高品質）
                self.logger.debug(f"画像URLを直接使用: {source_url}")
                resp = httpx.get(source_url, timeout=10.0, follow_redirects=True)
                if resp.status_code == 200 and resp.content:
                    content = resp.content
                    content_type = resp.headers.get("Content-Type", "image/jpeg")
                else:
                    # フォールバック
                    fb = httpx.get("https://placehold.co/300x300?text=No+Art", timeout=10.0, follow_redirects=True)
                    fb.raise_for_status()
                    content = fb.content
                    content_type = fb.headers.get("Content-Type", "image/png")

            b64 = base64.b64encode(content).decode("ascii")
            return f"data:{content_type};base64,{b64}"
        except Exception:
            # 追加のフォールバック（空の1px）
            transparent_png_base64 = (
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQAB"
                "J8F8WQAAAABJRU5ErkJggg=="
            )
            return f"data:image/png;base64,{transparent_png_base64}"
    
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
            self.logger.info("最新トラックの取得を開始...")
            latest = self.get_latest_track()
            self.logger.info("最新トラックの取得が完了しました")

            self.logger.info("最新トラックの整形を開始...")
            latest_content = self.format_latest_track(latest)

            self.logger.info("楽曲ランキングの取得を開始...")
            ranking = self.get_track_ranking(limit=3)
            self.logger.info(f"{len(ranking)}曲のランキングを取得しました")
            
            self.logger.info("ランキングの整形を開始...")
            ranking_content = self.format_track_ranking(ranking)
            
            combined_content = latest_content + "\n\n" + ranking_content
        
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
