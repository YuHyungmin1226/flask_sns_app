import os
import json
import io
import sys

# 프로젝트 루트 디렉토리를 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.google_drive_utils import drive_manager

def test_connection():
    print("구글 드라이브 연결 테스트를 시작합니다 (OAuth2 방식)...")
    
    # 1. 자격 증명 확인
    if not drive_manager.refresh_token:
        print("오류: GOOGLE_REFRESH_TOKEN이 설정되지 않았습니다.")
        return

    if not drive_manager.service:
        print("오류: 구글 사용자 계정 인증에 실패했습니다.")
        return
    
    print("구글 사용자 계정 인증 성공!")

    # 2. 폴더 접근 권한 확인
    try:
        folder = drive_manager.service.files().get(
            fileId=drive_manager.folder_id,
            fields='id, name'
        ).execute()
        print(f"폴더 접근 성공: {folder.get('name')} ({folder.get('id')})")
    except Exception as e:
        print(f"폴더 접근 오류: {e}")
        return

    # 3. 테스트 파일 업로드
    try:
        print("테스트 파일 업로드 시도 중...")
        test_content = b"This is an OAuth2 test file from Flask SNS App."
        test_stream = io.BytesIO(test_content)
        file_info = drive_manager.upload_file(
            test_stream, 
            "oauth2_test.txt", 
            "text/plain"
        )
        
        if file_info:
            print("테스트 파일 업로드 성공!")
            print(f"   - 파일 ID: {file_info.get('id')}")
            print(f"   - 보기 링크: {file_info.get('webViewLink')}")
            
            # 4. 테스트 파일 삭제
            print("테스트 파일 삭제 시도 중...")
            if drive_manager.delete_file(file_info.get('id')):
                print("테스트 파일 삭제 성공!")
            else:
                print("테스트 파일 삭제 실패 (수동 삭제 필요)")
        else:
            print("테스트 파일 업로드 실패")
            
    except Exception as e:
        print(f"업로드 테스트 중 예외 발생: {e}")

if __name__ == "__main__":
    test_connection()
