#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask SNS 포터블 앱 실행 파일
USB에 복사하여 어디서든 실행할 수 있는 개인 SNS 애플리케이션
"""

import os
import sys

# 현재 디렉터리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User
from werkzeug.security import generate_password_hash

if __name__ == '__main__':
    print("🚀 Flask SNS 포터블 앱을 시작합니다...")
    print("📱 브라우저에서 http://localhost:5001 으로 접속하세요")
    print("🔑 기본 관리자 계정: admin / admin123")
    print("💾 모든 데이터는 이 폴더에 저장됩니다")
    print("⏹️  종료하려면 Ctrl+C를 누르세요")
    print("-" * 50)
    
    # 데이터베이스 초기화
    with app.app_context():
        print("🗄️  데이터베이스 테이블을 생성합니다...")
        
        # 데이터베이스 경로 출력 (디버깅용)
        if getattr(sys, 'frozen', False):
            current_dir = os.path.dirname(sys.executable)
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, 'sns.db')
        print(f"📁 데이터베이스 경로: {db_path}")
        
        db.create_all()
        
        # 기본 관리자 계정 생성
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                password_hash=generate_password_hash('admin123'),
                password_changed=False  # 기본 비밀번호 사용 중
            )
            db.session.add(admin_user)
            db.session.commit()
            print("✅ 기본 관리자 계정이 생성되었습니다. (admin/admin123)")
            print("⚠️  보안을 위해 첫 로그인 시 비밀번호 변경을 권장합니다.")
        else:
            print("ℹ️  관리자 계정이 이미 존재합니다.")
    
    print("🌐 웹 서버를 시작합니다...")
    app.run(debug=False, host='0.0.0.0', port=5001) 