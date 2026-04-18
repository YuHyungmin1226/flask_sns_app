import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow

# 보안을 위해 하드코딩된 키를 제거했습니다.
# 환경 변수에서 가져오거나 실행 시 입력을 받습니다.
CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

def main():
    global CLIENT_ID, CLIENT_SECRET
    
    if not CLIENT_ID:
        CLIENT_ID = input("Google OAuth Client ID를 입력하세요: ").strip()
    if not CLIENT_SECRET:
        CLIENT_SECRET = input("Google OAuth Client Secret을 입력하세요: ").strip()

    if not CLIENT_ID or not CLIENT_SECRET:
        print("오류: Client ID와 Client Secret이 필요합니다.")
        return

    client_config = {
        "installed": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    # OAuth2 흐름 설정
    try:
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        print("\n아래 URL을 복사하여 브라우저에서 열고 로그인을 완료해 주세요:")
        
        creds = flow.run_local_server(port=0, open_browser=True)
        print("\n--- 인증 성공 ---")
        print(f"REFRESH_TOKEN: {creds.refresh_token}")
        print("-----------------\n")
    except Exception as e:
        print(f"인증 중 오류 발생: {e}")

if __name__ == "__main__":
    main()
