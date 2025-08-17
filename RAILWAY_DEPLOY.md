# Railway 배포 가이드 🚀

Flask SNS 앱을 Railway에 배포하는 방법입니다.

## 📋 사전 준비사항

1. **GitHub 계정** (코드 저장용)
2. **Railway 계정** (이미 있으시죠!)
3. **Git 설치** (로컬에서)

## 🚀 배포 단계

### 1단계: GitHub에 코드 업로드

```bash
# Git 저장소 초기화
git init
git add .
git commit -m "Initial commit for Railway deployment"

# GitHub에 새 저장소 생성 후
git remote add origin https://github.com/yourusername/flask-sns-app.git
git push -u origin main
```

### 2단계: Railway에서 새 프로젝트 생성

1. [Railway 대시보드](https://railway.app/dashboard) 접속
2. **"New Project"** 클릭
3. **"Deploy from GitHub repo"** 선택
4. GitHub 저장소 선택

### 3단계: PostgreSQL 데이터베이스 추가

1. Railway 프로젝트 대시보드에서 **"New"** 클릭
2. **"Database"** → **"PostgreSQL"** 선택
3. 데이터베이스가 생성되면 자동으로 환경변수에 연결됨

### 4단계: 환경변수 설정

Railway 프로젝트 대시보드에서 **"Variables"** 탭에서 설정:

```
SECRET_KEY=your-super-secret-key-change-this-in-production
```

### 5단계: 배포 확인

1. **"Deployments"** 탭에서 배포 상태 확인
2. 배포 완료 후 **"View"** 버튼으로 사이트 접속
3. 기본 계정으로 로그인: `admin` / `admin123`

## 🔧 슬립모드 방지 설정

### 방법 1: UptimeRobot 사용 (무료)

1. [UptimeRobot](https://uptimerobot.com/) 가입
2. 새 모니터 추가:
   - **Monitor Type**: HTTP(s)
   - **URL**: `https://your-app.railway.app/ping`
   - **Check Interval**: 5분

### 방법 2: Railway 유료 플랜 ($5/월)

- **24/7 실행**: 슬립모드 완전 없음
- **즉시 응답**: 부팅 시간 없음

## 📁 현재 비활성화된 기능

Railway 배포를 위해 임시로 비활성화된 기능들:

- ✅ **파일 업로드**: 로컬 파일 시스템 대신 클라우드 스토리지 필요
- ✅ **파일 다운로드**: 업로드 기능과 연동
- ✅ **파일 삭제**: 업로드 기능과 연동

## 🔄 파일 업로드 기능 복원 방법

나중에 파일 업로드 기능을 복원하려면:

1. **AWS S3** 또는 **Cloudinary** 설정
2. `app.py`에서 주석 처리된 파일 업로드 코드 복원
3. 클라우드 스토리지 연동 코드 추가

## 🐛 문제 해결

### 배포 실패 시
1. **Logs** 탭에서 오류 확인
2. **Variables** 탭에서 환경변수 확인
3. **GitHub**에서 코드 푸시 후 재배포

### 데이터베이스 연결 오류
1. PostgreSQL 서비스가 실행 중인지 확인
2. `DATABASE_URL` 환경변수 확인
3. 데이터베이스 테이블 자동 생성 확인

### 포트 오류
- Railway에서 자동으로 `PORT` 환경변수 설정
- 코드에서 `os.environ.get('PORT', 5000)` 사용

## 📞 지원

문제가 있으면:
1. Railway **Logs** 탭에서 오류 확인
2. GitHub 이슈 생성
3. Railway Discord 커뮤니티 활용

---

**배포 완료 후 URL**: `https://your-app-name.railway.app`
