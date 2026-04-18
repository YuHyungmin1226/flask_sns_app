# Railway 배포 가이드

이 프로젝트는 Railway에 최적화되어 있습니다. 다음 단계를 따라 배포를 완료하십시오.

## 1. Railway 준비 사항

1. [Railway.app](https://railway.app/) 계정이 필요합니다.
2. New Project -> Deploy from GitHub repo를 선택하여 이 저장소를 연결합니다.

## 2. 필수 환경 변수 설정

Railway 프로젝트 설정의 'Variables' 탭에서 다음 변수들을 등록해야 합니다.

### 기본 설정
| 변수명 | 설명 | 예시 |
| :--- | :--- | :--- |
| `SECRET_KEY` | Flask 세션 암호화 키 | (충분히 긴 무작위 문자열) |
| `ADMIN_PASSWORD` | 초기 관리자 비밀번호 | admin123 |
| `TZ` | 서버 시간대 설정 | Asia/Seoul |

### Google Drive API 설정 (필수)
파일 업로드 기능을 사용하기 위해 반드시 필요합니다.
| 변수명 | 설명 | 비고 |
| :--- | :--- | :--- |
| `GOOGLE_CLIENT_ID` | Google Cloud 콘솔 클라이언트 ID | 743112499911-... |
| `GOOGLE_CLIENT_SECRET` | Google Cloud 콘솔 클라이언트 보안 비밀 | GOCSPX-... |
| `GOOGLE_REFRESH_TOKEN` | 관리자 계정 리프레시 토큰 | 1//0e... |

## 3. 데이터베이스 설정

1. Railway에서 'Add Service' -> 'Database' -> 'Add PostgreSQL'을 선택합니다.
2. PostgreSQL이 추가되면 Railway가 자동으로 프로젝트 전체에 `DATABASE_URL` 환경 변수를 주입합니다.
3. 애플리케이션 시작 시 `app.py`의 `init_db()` 함수가 자동으로 테이블을 생성합니다.

## 4. 배포 확인

1. 배포가 완료되면 Railway에서 제공하는 도메인(예: xxx.up.railway.app)으로 접속합니다.
2. `/ping` 엔드포인트에 접속하여 서버 상태를 확인합니다 (예: https://your-app.up.railway.app/ping).
3. 관리자 계정(admin)으로 로그인하여 작동 여부를 확인합니다.

## 5. 주의 사항
- `scripts/get_refresh_token.py`는 로컬에서만 실행하며, 생성된 토큰만 환경 변수에 등록하십시오.
- Railway 슬립 모드를 방지하려면 정기적인 핑 서비스(예: Cron-job.org)를 사용하여 `/ping` 엔드포인트를 호출하는 것을 권장합니다.
