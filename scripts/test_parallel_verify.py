import os
import io
import json
from concurrent.futures import ThreadPoolExecutor
import threading
from dotenv import load_dotenv

# 로컬 임포트 전에 환경 변수 먼저 로드 (안전장치)
load_dotenv()

# 로컬 임포트 (경로 설정 필요시 sys.path.append 사용)
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/..')
from utils.google_drive_utils import drive_manager

def test_parallel_upload():
    print("--- 병렬 업로드 쓰레드 안전성 테스트 시작 ---")
    
    # 더미 데이터 생성 (작은 텍스트 파일 5개)
    test_files = [
        {"name": f"test_thread_{i}.txt", "content": f"Hello from thread {i}".encode(), "mimetype": "text/plain"}
        for i in range(5)
    ]
    
    def upload_worker(file_data):
        thread_name = threading.current_thread().name
        print(f"[{thread_name}] 업로드 시작: {file_data['name']}")
        try:
            stream = io.BytesIO(file_data['content'])
            # drive_manager.service property 호출 시 threading.local에 의해 서비스 생성됨
            result = drive_manager.upload_file(stream, file_data['name'], file_data['mimetype'])
            if result:
                print(f"[{thread_name}] 업로드 성공: {result.get('id')}")
                return result
            else:
                print(f"[{thread_name}] 업로드 실패 (결과 없음)")
                return None
        except Exception as e:
            print(f"[{thread_name}] 예외 발생: {str(e)}")
            return None

    # ThreadPoolExecutor 실행
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(upload_worker, test_files))
    
    success_count = len([r for r in results if r is not None])
    print(f"\n--- 테스트 종료 (성공: {success_count}/5) ---")
    
    if success_count == 0:
        print("결과: 모든 업로드가 실패했습니다. 인증 또는 쓰레드 로컬 이슈가 의심됩니다.")
    elif success_count < 5:
        print("결과: 일부 업로드가 실패했습니다. 레이스 컨디션 또는 할당량 문제일 수 있습니다.")
    else:
        print("결과: 모든 업로드 성공. 코어 로직은 정상입니다.")

if __name__ == "__main__":
    test_parallel_upload()
