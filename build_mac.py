#!/usr/bin/env python3
"""
Flask SNS 맥용 앱 빌드 스크립트
macOS용 실행 파일 생성
"""

import os
import sys
import shutil
import subprocess

def check_pyinstaller():
    """PyInstaller 설치 확인"""
    try:
        subprocess.run(['pyinstaller', '--version'], capture_output=True, check=True)
        print("✅ PyInstaller가 설치되어 있습니다.")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ PyInstaller가 설치되지 않았습니다.")
        print("💡 설치 명령어: pip install pyinstaller")
        return False

def build_mac_app():
    """맥용 앱 빌드"""
    print("🚀 macOS용 앱 빌드를 시작합니다...")
    
    # 현재 디렉터리
    current_dir = os.path.abspath(".")
    templates_path = os.path.join(current_dir, "templates")
    utils_path = os.path.join(current_dir, "utils")
    
    print(f"📁 현재 디렉터리: {current_dir}")
    print(f"📁 템플릿 경로: {templates_path}")
    print(f"📁 유틸리티 경로: {utils_path}")
    
    # 맥용 빌드 명령어 구성
    cmd = [
        'pyinstaller',
        '--onefile',                    # 단일 실행 파일
        '--console',                    # 콘솔 창 표시
        '--name=FlaskSNS',              # 실행 파일명
        '--distpath=mac_build',         # 출력 디렉터리
        '--workpath=build_temp',        # 작업 디렉터리
        '--specpath=build_temp',        # spec 파일 위치
        f'--add-data={templates_path}:templates',  # 템플릿 (맥용 구분자)
        f'--add-data={utils_path}:utils',          # 유틸리티 (맥용 구분자)
        '--hidden-import=flask',
        '--hidden-import=flask_sqlalchemy',
        '--hidden-import=flask_login',
        '--hidden-import=werkzeug',
        '--hidden-import=jinja2',
        '--hidden-import=sqlalchemy',
        '--hidden-import=requests',
        '--hidden-import=bs4',
        '--hidden-import=PIL',
        '--hidden-import=filetype',
        '--hidden-import=jinja2.ext',
        '--hidden-import=jinja2.loaders',
        '--hidden-import=jinja2.environment',
        '--hidden-import=jinja2.templating',
        'FlaskSNS.py'                   # 메인 스크립트
    ]
    
    print("🔨 PyInstaller로 맥용 빌드를 시작합니다...")
    print(f"명령어: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ 맥용 빌드 성공!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 빌드 실패: {e}")
        print(f"오류 출력: {e.stderr}")
        return False

def create_mac_package():
    """맥용 패키지 생성"""
    print("📦 맥용 패키지를 생성합니다...")
    
    # 출력 폴더
    output_dir = "FlaskSNS_Mac"
    
    # 기존 폴더 삭제
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    # 새 폴더 생성
    os.makedirs(output_dir)
    
    # 실행 파일 복사
    exe_path = os.path.join("mac_build", "FlaskSNS")
    if os.path.exists(exe_path):
        shutil.copy2(exe_path, os.path.join(output_dir, "FlaskSNS"))
        print("✅ 실행 파일 복사 완료")
        
        # 실행 권한 부여
        os.chmod(os.path.join(output_dir, "FlaskSNS"), 0o755)
        print("✅ 실행 권한 부여 완료")
    else:
        print("❌ 실행 파일을 찾을 수 없습니다.")
        return False
    
    # README 파일 생성
    readme_content = """# Flask SNS 맥용 앱

## 사용 방법

1. 이 폴더를 원하는 위치에 복사하세요
2. 터미널에서 다음 명령어를 실행하세요:
   ./FlaskSNS
3. 웹 브라우저에서 http://localhost:5001 접속
4. 기본 계정: admin / admin123

## 주의사항

- macOS 10.14 이상에서 실행됩니다
- 인터넷 연결이 필요합니다 (패키지 다운로드용)
- 첫 실행 시 데이터베이스가 자동으로 생성됩니다
- 종료하려면 Ctrl+C를 누르거나 창을 닫으세요

## 문제 해결

- 실행이 안 되는 경우: 터미널에서 직접 실행해보세요
- 포트 충돌 시: 다른 포트로 자동 변경됩니다
- 데이터베이스 오류: sns.db 파일을 삭제하고 다시 실행하세요
- 권한 오류: chmod +x FlaskSNS 명령어로 실행 권한을 부여하세요

## 지원

문제가 있으면 GitHub 이슈를 생성해주세요.
"""
    
    with open(os.path.join(output_dir, "README.txt"), "w", encoding="utf-8") as f:
        f.write(readme_content)
    print("✅ README 파일 생성 완료")
    
    # 실행 스크립트 생성
    script_content = """#!/bin/bash
echo "🚀 Flask SNS 앱을 시작합니다..."
echo "📱 브라우저에서 http://localhost:5001 으로 접속하세요"
echo "🔑 기본 관리자 계정: admin / admin123"
echo "⏹️  종료하려면 Ctrl+C를 누르세요"
echo "----------------------------------------"
./FlaskSNS
"""
    
    script_path = os.path.join(output_dir, "run.sh")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_content)
    os.chmod(script_path, 0o755)
    print("✅ 실행 스크립트 생성 완료")
    
    return True

def cleanup():
    """임시 파일 정리"""
    print("🧹 임시 파일을 정리합니다...")
    
    temp_dirs = ["build_temp", "mac_build"]
    for dir_name in temp_dirs:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"✅ {dir_name} 삭제 완료")

def main():
    """메인 함수"""
    print("=" * 50)
    print("macOS용 Flask SNS 앱 빌드 도구")
    print("=" * 50)
    
    # PyInstaller 확인
    if not check_pyinstaller():
        return
    
    # 빌드 실행
    if not build_mac_app():
        return
    
    # 맥용 패키지 생성
    if not create_mac_package():
        return
    
    print("\n🎉 맥용 빌드 완료!")
    print(f"📁 {os.path.abspath('FlaskSNS_Mac')} 폴더에 맥용 버전이 생성되었습니다.")
    print("💾 이 폴더를 원하는 위치에 복사하여 실행할 수 있습니다.")
    print("🚀 실행 방법: ./FlaskSNS 또는 ./run.sh")
    
    # 정리
    cleanup()

if __name__ == "__main__":
    main()
