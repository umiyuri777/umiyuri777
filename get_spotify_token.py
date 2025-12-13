#!/usr/bin/env python3
"""
Spotify Refresh Tokenを取得するためのヘルパースクリプト

このスクリプトを使用して、必要なスコープ（user-read-recently-played, user-top-read）を含む
Refresh Tokenを取得できます。
"""

import requests
import base64
from urllib.parse import urlencode, urlparse, parse_qs

def get_spotify_token():
    """Spotify Refresh Tokenを取得する"""
    
    print("=" * 60)
    print("Spotify Refresh Token 取得ツール")
    print("=" * 60)
    print()
    
    # ユーザー入力
    CLIENT_ID = input("Spotify Client IDを入力してください: ").strip()
    CLIENT_SECRET = input("Spotify Client Secretを入力してください: ").strip()
    REDIRECT_URI = input("Redirect URIを入力してください（デフォルト: http://localhost:8888/callback）: ").strip()
    
    if not REDIRECT_URI:
        REDIRECT_URI = "http://localhost:8888/callback"
    
    # 必要なスコープ
    SCOPE = "user-read-recently-played user-top-read"
    
    print()
    print("-" * 60)
    print("ステップ1: 認証URLにアクセス")
    print("-" * 60)
    
    # 認証URLを生成
    auth_url = "https://accounts.spotify.com/authorize"
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "show_dialog": "true"  # 既に許可済みの場合でも確認ダイアログを表示
    }
    
    auth_url_with_params = f"{auth_url}?{urlencode(params)}"
    
    print(f"\n以下のURLをブラウザで開いてください:\n")
    print(auth_url_with_params)
    print()
    print("Spotifyにログインし、アプリのアクセス許可を承認してください。")
    print()
    
    # リダイレクトされたURLからcodeを取得
    print("-" * 60)
    print("ステップ2: 認証コードの取得")
    print("-" * 60)
    print()
    print("認証後、リダイレクトされたURLをコピーして貼り付けてください。")
    print("例: http://localhost:8888/callback?code=AQBx...")
    print()
    
    redirect_url = input("リダイレクトされたURL: ").strip()
    
    # URLからcodeパラメータを抽出
    try:
        parsed_url = urlparse(redirect_url)
        query_params = parse_qs(parsed_url.query)
        
        if 'code' not in query_params:
            print("\n❌ エラー: URLにcodeパラメータが見つかりません。")
            print("リダイレクトされたURLを正しくコピーしてください。")
            return
        
        code = query_params['code'][0]
        print(f"\n✅ 認証コードを取得しました: {code[:20]}...")
        
    except Exception as e:
        print(f"\n❌ エラー: URLの解析に失敗しました: {e}")
        return
    
    # Access TokenとRefresh Tokenを取得
    print()
    print("-" * 60)
    print("ステップ3: トークンの取得")
    print("-" * 60)
    print()
    
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
    
    try:
        response = requests.post(token_url, headers=headers, data=data)
        response.raise_for_status()
        
        tokens = response.json()
        
        if 'refresh_token' not in tokens:
            print("❌ エラー: Refresh Tokenが取得できませんでした。")
            print(f"レスポンス: {tokens}")
            return
        
        refresh_token = tokens['refresh_token']
        access_token = tokens.get('access_token', '')
        
        print("✅ トークンの取得に成功しました！")
        print()
        print("=" * 60)
        print("取得したRefresh Token:")
        print("=" * 60)
        print(refresh_token)
        print()
        print("=" * 60)
        print("次のステップ:")
        print("=" * 60)
        print("1. このRefresh Tokenをコピーしてください")
        print("2. .envファイルのSPOTIFY_REFRESH_TOKENを更新してください")
        print("3. GitHub Secretsを使用している場合は、SPOTIFY_REFRESH_TOKENを更新してください")
        print()
        print("⚠️  注意: Refresh Tokenは機密情報です。他人に共有しないでください。")
        print()
        
        # スコープの確認
        if 'scope' in tokens:
            print(f"✅ 取得されたスコープ: {tokens['scope']}")
            required_scopes = ['user-read-recently-played', 'user-top-read']
            obtained_scopes = tokens['scope'].split()
            
            missing_scopes = [s for s in required_scopes if s not in obtained_scopes]
            if missing_scopes:
                print(f"⚠️  警告: 以下のスコープが不足しています: {', '.join(missing_scopes)}")
            else:
                print("✅ 必要なスコープがすべて含まれています")
        
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ エラー: トークンの取得に失敗しました")
        print(f"ステータスコード: {e.response.status_code}")
        print(f"レスポンス: {e.response.text}")
    except Exception as e:
        print(f"\n❌ エラー: {e}")


if __name__ == "__main__":
    try:
        get_spotify_token()
    except KeyboardInterrupt:
        print("\n\n処理が中断されました。")
    except Exception as e:
        print(f"\n❌ 予期しないエラーが発生しました: {e}")

