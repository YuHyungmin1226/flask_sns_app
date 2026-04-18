import os
import json
import io
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

class GoogleDriveManager:
    def __init__(self):
        # 구글 드라이브 폴더 ID는 공개되어도 안전하므로 기본값으로 유지
        self.folder_id = os.environ.get('GOOGLE_DRIVE_FOLDER_ID', '1O50x9kbr5BliCayYTzKVLJ6NsH1uTFk7')
        
        # 민감한 정보는 환경 변수에서만 가져오며 기본값을 제공하지 않음
        self.client_id = os.environ.get('GOOGLE_CLIENT_ID')
        self.client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
        self.refresh_token = os.environ.get('GOOGLE_REFRESH_TOKEN')
        self.service = self._authenticate()

    def _authenticate(self):
        """OAuth2 Refresh Token을 사용하여 사용자 계정 인증 수행"""
        if not all([self.client_id, self.client_secret, self.refresh_token]):
            print("오류: 구글 드라이브 인증에 필요한 환경 변수가 설정되지 않았습니다.")
            return None

        try:
            creds = Credentials(
                None,
                refresh_token=self.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret,
                scopes=['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/drive']
            )
            
            # 토큰 만료 시 갱신
            if creds and (creds.expired or not creds.valid):
                creds.refresh(Request())
                
            return build('drive', 'v3', credentials=creds)
        except Exception as e:
            print(f"구글 드라이브 인증 오류: {e}")
            return None

    def upload_file(self, file_stream, filename, mimetype):
        """파일을 구글 드라이브의 지정된 폴더에 업로드하고 정보 반환"""
        if not self.service:
            print("드라이브 서비스가 초기화되지 않았습니다.")
            return None

        try:
            file_metadata = {
                'name': filename,
                'parents': [self.folder_id]
            }
            
            file_stream.seek(0)
            media = MediaIoBaseUpload(file_stream, mimetype=mimetype, resumable=True)
            
            # 파일 업로드
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink, webContentLink'
            ).execute()
            
            file_id = file.get('id')
            
            # 파일을 '링크가 있는 모든 사용자에게 공개'로 설정
            self.service.permissions().create(
                fileId=file_id,
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()
            
            file_info = self.service.files().get(
                fileId=file_id,
                fields='id, name, webViewLink, webContentLink, mimeType, size'
            ).execute()
            
            return file_info
            
        except Exception as e:
            print(f"파일 업로드 오류: {e}")
            return None

    def delete_file(self, file_id):
        """파일 ID를 이용해 구글 드라이브에서 파일 삭제"""
        if not self.service:
            return False
            
        try:
            self.service.files().delete(fileId=file_id).execute()
            return True
        except Exception as e:
            print(f"파일 삭제 오류 ({file_id}): {e}")
            return False

# 싱글톤 인스턴스 생성
drive_manager = GoogleDriveManager()
