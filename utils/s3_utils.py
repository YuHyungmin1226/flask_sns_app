import boto3
import os
import uuid
from datetime import datetime, timezone, timedelta
from werkzeug.utils import secure_filename
from botocore.exceptions import ClientError
import json

# 한국 시간대 설정
KST = timezone(timedelta(hours=9))

def get_korean_time():
    """한국 시간 반환"""
    return datetime.now(KST)

class S3Manager:
    def __init__(self):
        """S3 매니저 초기화"""
        from botocore.config import Config
        
        # S3 클라이언트 설정
        config = Config(
            connect_timeout=30,
            read_timeout=60,
            retries={'max_attempts': 3}
        )
        
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            region_name=os.environ.get('AWS_REGION', 'ap-northeast-2'),
            config=config
        )
        self.bucket_name = os.environ.get('S3_BUCKET_NAME')
        
        print(f"🔧 S3 매니저 초기화 완료: {self.bucket_name}")
        
    def upload_file(self, file, filename):
        """파일을 S3에 업로드"""
        try:
            # 파일 내용을 메모리에 복사 (스트림 닫힘 방지)
            file.seek(0)
            file_content = file.read()
            
            # 파일 크기 확인
            if len(file_content) == 0:
                raise Exception("파일이 비어있습니다.")
            
            print(f"📄 파일 읽기 완료: {len(file_content)} bytes")
            
            # 고유한 파일명 생성
            unique_filename = self.generate_unique_filename(filename)
            
            # 파일 타입별 폴더 결정
            file_type = self.get_file_type(filename)
            folder = self.get_folder_by_type(file_type)
            
            # S3 키 (경로) 생성
            s3_key = f"{folder}/{unique_filename}"
            
            # 파일 업로드 (BytesIO 사용) - 타임아웃 방지
            from io import BytesIO
            file_stream = BytesIO(file_content)
            
            # 파일 업로드 (클라이언트 초기화 시 이미 Config 설정됨)
            self.s3_client.upload_fileobj(
                file_stream,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': self.get_content_type(filename),
                    'ACL': 'public-read',  # 공개 읽기 권한
                    'CacheControl': 'max-age=31536000'  # 캐시 최적화
                }
            )
            
            # 파일 URL 생성
            file_url = f"https://{self.bucket_name}.s3.ap-southeast-2.amazonaws.com/{s3_key}"
            
            # 파일 정보 반환
            file_info = {
                'original_name': filename,
                'saved_name': unique_filename,
                'file_type': file_type,
                'file_url': file_url,
                's3_key': s3_key,
                'size': len(file_content),
                'uploaded_at': get_korean_time().isoformat()
            }
            
            print(f"✅ S3 업로드 성공: {file_url}")
            return file_info
            
        except ClientError as e:
            print(f"❌ S3 업로드 실패: {e}")
            raise Exception(f"S3 업로드 실패: {str(e)}")
        except Exception as e:
            print(f"❌ 파일 업로드 오류: {e}")
            raise Exception(f"파일 업로드 오류: {str(e)}")
    
    def delete_file(self, s3_key):
        """S3에서 파일 삭제"""
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            print(f"✅ S3 파일 삭제 성공: {s3_key}")
            return True
        except ClientError as e:
            print(f"❌ S3 파일 삭제 실패: {e}")
            return False
    
    def generate_unique_filename(self, filename):
        """고유한 파일명 생성"""
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        unique_id = str(uuid.uuid4())
        timestamp = get_korean_time().strftime('%Y%m%d_%H%M%S')
        
        if ext:
            return f"{timestamp}_{unique_id}.{ext}"
        else:
            return f"{timestamp}_{unique_id}"
    
    def get_file_type(self, filename):
        """파일 확장자로부터 파일 타입을 반환"""
        if '.' not in filename:
            return 'unknown'
        
        ext = filename.rsplit('.', 1)[1].lower()
        
        file_types = {
            'image': {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'},
            'document': {'pdf', 'doc', 'docx', 'txt', 'rtf'},
            'video': {'mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv'},
            'audio': {'mp3', 'wav', 'flac', 'ogg', 'm4a'},
            'archive': {'zip', 'rar', '7z', 'tar', 'gz'}
        }
        
        for file_type, extensions in file_types.items():
            if ext in extensions:
                return file_type
        
        return 'unknown'
    
    def get_folder_by_type(self, file_type):
        """파일 타입별 폴더 반환"""
        folders = {
            'image': 'images',
            'document': 'documents',
            'video': 'videos',
            'audio': 'audio',
            'archive': 'archives'
        }
        return folders.get(file_type, 'documents')
    
    def get_content_type(self, filename):
        """파일의 MIME 타입 반환"""
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        
        content_types = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'bmp': 'image/bmp',
            'pdf': 'application/pdf',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'txt': 'text/plain',
            'mp4': 'video/mp4',
            'avi': 'video/x-msvideo',
            'mov': 'video/quicktime',
            'mp3': 'audio/mpeg',
            'wav': 'audio/wav',
            'zip': 'application/zip'
        }
        
        return content_types.get(ext, 'application/octet-stream')
    
    def get_file_size(self, file_content):
        """파일 크기 반환 (바이트)"""
        return len(file_content)
    
    def get_file_size_display(self, size_bytes):
        """파일 크기를 읽기 쉬운 형태로 변환"""
        if size_bytes == 0:
            return "0B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f}{size_names[i]}"

# 전역 S3 매니저 인스턴스
s3_manager = S3Manager()
