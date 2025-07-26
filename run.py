#!/usr/bin/env python3
"""
Flask SNS 앱 실행 스크립트
"""

import os
import sys

# 현재 디렉터리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User
from werkzeug.security import generate_password_hash

if __name__ == '__main__':
    print("🚀 Flask SNS 앱을 시작합니다...")
    print("📱 브라우저에서 http://localhost:5001 으로 접속하세요")
    print("🔑 기본 관리자 계정: admin / admin123")
    print("⏹️  종료하려면 Ctrl+C를 누르세요")
    print("-" * 50)
    
    # 데이터베이스 초기화
    with app.app_context():
        print("🗄️  데이터베이스 테이블을 생성합니다...")
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
    app.run(debug=True, host='0.0.0.0', port=5001) 