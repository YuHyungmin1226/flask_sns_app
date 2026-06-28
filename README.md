# Flask SNS

Google Drive 연동 기능을 갖춘 개인용 SNS 애플리케이션입니다. 모든 첨부 파일은 사용자의 Google Drive에 안전하게 보관됩니다.

## 주요 기능

- **개인 SNS**: 게시글 작성, 수정, 삭제 기능
- **Google Drive Direct Upload**: 브라우저에서 Google Drive로 파일을 직접 전송하여 서버 부하 없이 **최대 10GB** 대용량 업로드 지원
- **URL 미리보기**: 링크 공유 시 자동 미리보기 생성 (YouTube 특별 지원)
- **댓글 시스템**: 게시물에 대한 실시간 댓글 작성
- **사용자 관리**: 회원가입, 로그인, 비밀번호 변경, 관리자 승인 시스템
- **보안**: 환경 변수를 통한 비밀 정보 관리, 로그인 시도 제한, 계정 잠금, CSRF 보호

## 시작하기

이 프로젝트는 Google Drive API 및 웹 푸시 알림을 사용합니다. 다음 스크립트들을 사용해 설정 키들을 준비해야 합니다:

1. **Google OAuth2 토큰 생성**:
   `scripts/get_refresh_token.py`를 사용하여 다음 정보를 얻을 수 있습니다:
   - GOOGLE_CLIENT_ID
   - GOOGLE_CLIENT_SECRET
   - GOOGLE_REFRESH_TOKEN

2. **Web Push VAPID 키 쌍 생성**:
   `scripts/generate_vapid_keys.py`를 실행하여 다음 키들을 발급받을 수 있습니다:
   - VAPID_PUBLIC_KEY
   - VAPID_PRIVATE_KEY

### 2. 환경 변수 설정
`.env.example` 파일을 복사하여 `.env` 파일을 생성하고 필수 정보를 입력합니다.

```bash
cp .env.example .env
```

### 3. 서버 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# 서버 실행
python app.py
```

### 4. 접속
- **URL**: http://localhost:5000
- **기본 관리자 계정**: admin / admin123 (환경 변수에서 변경 가능)

## 기술 스택

- **Backend**: Flask, Flask-SQLAlchemy, Flask-Login
- **Frontend**: HTML5, Vanilla CSS, Bootstrap 5
- **Database**: SQLite (Local), PostgreSQL (Railway/Production)
- **Storage**: Google Drive API v3
- **Deployment**: Railway 지원 (Procfile 포함)

## 프로젝트 구조

```
flask_sns_app/
├── app.py              # 메인 애플리케이션 로직
├── requirements.txt    # 의존성 패키지 목록
├── .env.example        # 환경 변수 템플릿
├── static/             # CSS, JS, 이미지 등 정적 파일
├── templates/          # HTML 템플릿 파일
├── utils/              # 유틸리티 함수 (Google Drive, URL 미리보기)
├── scripts/            # 관리용 도구 (인증 토큰 생성, 연결 테스트)
└── sns.db              # 로컬 데이터베이스 (실행 시 생성)
```

## 배포 안내 (Railway)

1. Railway 프로젝트를 생성하고 이 저장소를 연결합니다.
2. 다음 환경 변수를 설정합니다:
   - `SECRET_KEY`
   - `ADMIN_PASSWORD`
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
   - `GOOGLE_REFRESH_TOKEN`
3. Railway에서 자동으로 `DATABASE_URL`을 제공합니다.

## 주의 사항
- `.env` 파일은 절대 Git에 커밋하지 마십시오.
- 초기 관리자 계정(admin)은 로그인 후 즉시 비밀번호를 변경하시기 바랍니다.

## 라이선스
MIT License