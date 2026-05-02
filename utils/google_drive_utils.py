import os
import json
import io
import threading
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from dotenv import load_dotenv

class GoogleDriveManager:
    def __init__(self):
        # 환경 변수를 생성자에서 고정하지 않고 실시간으로 읽어오도록 변경 (지연 로딩)
        # 구글 드라이브 폴더 ID는 공개되어도 안전하므로 기본값 유지
        self.default_folder_id = os.environ.get('GOOGLE_DRIVE_FOLDER_ID', '1O50x9kbr5BliCayYTzKVLJ6NsH1uTFk7')
        
        # 쓰레드별 서비스 인스턴스 관리를 위한 로컬 변수
        self._local = threading.local()

    @property
    def folder_id(self):
        """실시간으로 환경 변수에서 폴더 ID 획득"""
        return os.environ.get('GOOGLE_DRIVE_FOLDER_ID', self.default_folder_id)

    @property
    def service(self):
        """쓰레드별로 독립적인 구글 드라이브 서비스 인스턴스를 반환"""
        if not hasattr(self._local, 'instance') or self._local.instance is None:
            self._local.instance = self._authenticate()
        return self._local.instance

    def _authenticate(self):
        """OAuth2 Refresh Token을 사용하여 사용자 계정 인증 수행 (실시간 환경 변수 로드)"""
        # 매번 환경 변수를 새로 확인하여 load_dotenv() 이후의 값을 반영함
        load_dotenv()
        client_id = os.environ.get('GOOGLE_CLIENT_ID')
        client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
        refresh_token = os.environ.get('GOOGLE_REFRESH_TOKEN')

        if not all([client_id, client_secret, refresh_token]):
            print("오류: 구글 드라이브 인증에 필요한 환경 변수가 설정되지 않았습니다.")
            return None

        try:
            creds = Credentials(
                None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/drive']
            )
            
            # 토큰 만료 시 갱신
            if creds and (creds.expired or not creds.valid):
                creds.refresh(Request())
                
            return build('drive', 'v3', credentials=creds)
        except Exception as e:
            print(f"구글 드라이브 인증 오류: {e}")
            return None

    def find_file_id(self, filename):
        """이름으로 파일 ID 찾기"""
        if not self.service:
            return None
        try:
            query = f"name = '{filename}' and '{self.folder_id}' in parents and trashed = false"
            results = self.service.files().list(q=query, fields="files(id, name)").execute()
            files = results.get('files', [])
            return files[0].get('id') if files else None
        except Exception as e:
            print(f"파일 검색 오류 ({filename}): {e}")
            return None

    def create_upload_session(self, filename, mimetype, origin=None):
        """브라우저 직접 업로드를 위한 구글 드라이브 세션 URI 생성 (CORS 지원)"""
        if not self.service:
            return None
        
        try:
            # 토큰 갱신 확인
            creds = self.service._http.credentials
            if creds.expired or not creds.valid:
                creds.refresh(Request())

            url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable"
            headers = {
                "Authorization": f"Bearer {creds.token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": mimetype
            }
            
            # CORS를 허용하기 위해 Origin 헤더 추가
            if origin:
                headers["Origin"] = origin
                
            metadata = {
                'name': filename,
                'parents': [self.folder_id]
            }
            
            import requests
            response = requests.post(url, headers=headers, json=metadata)
            if response.status_code == 200:
                return response.headers.get('Location')
            else:
                print(f"세션 생성 실패: {response.status_code} {response.text}")
                return None
        except Exception as e:
            print(f"세션 생성 오류: {e}")
            return None

    def complete_upload(self, file_id):
        """업로드 완료 후 파일 권한 설정 및 정보 반환"""
        if not self.service:
            return None
            
        try:
            # 파일을 '링크가 있는 모든 사용자에게 공개'로 설정
            self.service.permissions().create(
                fileId=file_id,
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()
            
            # 최신 정보 가져오기
            file_info = self.service.files().get(
                fileId=file_id,
                fields='id, name, webViewLink, webContentLink, thumbnailLink, mimeType, size'
            ).execute()
            
            return file_info
        except Exception as e:
            print(f"업로드 완료 처리 오류 ({file_id}): {e}")
            return None

    def sync_database(self, local_db_path, filename='sns.db'):
        """로컬 DB 파일을 드라이브로 동기화 (업데이트 또는 생성)"""
        if not self.service:
            return None
        
        try:
            file_id = self.find_file_id(filename)
            media = MediaIoBaseUpload(local_db_path, mimetype='application/x-sqlite3', resumable=True)
            
            if file_id:
                # 파일 업데이트
                updated_file = self.service.files().update(
                    fileId=file_id,
                    media_body=media
                ).execute()
                print(f"[Sync] DB 업데이트 완료 (ID: {file_id})")
                return updated_file.get('id')
            else:
                # 파일 신규 생성
                file_metadata = {
                    'name': filename,
                    'parents': [self.folder_id]
                }
                new_file = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
                print(f"[Sync] 새 DB 파일 생성 및 업로드 완료 (ID: {new_file.get('id')})")
                return new_file.get('id')
        except Exception as e:
            print(f"DB 동기화 오류: {e}")
            return None

    def download_database(self, local_db_path, filename='sns.db'):
        """드라이브에서 DB 파일을 다운로드하여 로컬에 저장"""
        if not self.service:
            return False
            
        try:
            file_id = self.find_file_id(filename)
            if not file_id:
                print(f"[Restore] 드라이브에 {filename} 파일이 없습니다.")
                return False
                
            request = self.service.files().get_media(fileId=file_id)
            with io.FileIO(local_db_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
            print(f"[Restore] 드라이브로부터 DB 다운로드 및 복구 완료.")
            return True
        except Exception as e:
            print(f"DB 다운로드 오류: {e}")
            return False

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
