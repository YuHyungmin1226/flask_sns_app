import os
import sys
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_talisman import Talisman
from dotenv import load_dotenv

# 내부 모듈 임포트
from extensions import db, login_manager, csrf
from models import User, Post
from utils.google_drive_utils import drive_manager
from utils.tasks import set_db_path, trigger_db_sync
from utils.time_utils import KST

# 환경 변수 로드
load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-key-change-in-production')

    # 데이터베이스 설정
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL:
        if DATABASE_URL.startswith('postgres://'):
            DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
        app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
        db_path = None
    else:
        if getattr(sys, 'frozen', False):
            current_dir = os.path.dirname(sys.executable)
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, 'sns.db')
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
        set_db_path(db_path)

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024 * 1024  # 10GB로 상향
    
    # 세션 보안 설정
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=timedelta(days=7)
    )

    # 확장 초기화
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # 보안 헤더 설정 (Talisman)
    csp = {
        'default-src': '\'self\'',
        'script-src': ['\'self\'', 'https://cdn.jsdelivr.net', '\'unsafe-inline\''],
        'style-src': ['\'self\'', 'https://cdn.jsdelivr.net', 'https://fonts.googleapis.com', 'https://cdnjs.cloudflare.com', '\'unsafe-inline\''],
        'font-src': ['\'self\'', 'https://cdn.jsdelivr.net', 'https://fonts.gstatic.com'],
        'img-src': ['\'self\'', 'data:', 'https://*.googleusercontent.com', 'https://drive.google.com', 'https://docs.google.com', 'https://*.gstatic.com', 'https://*.youtube.com', 'https://*.ytimg.com', 'https://img.youtube.com', 'https://i.ytimg.com'],
        'frame-src': ['\'self\'', 'https://drive.google.com', 'https://*.youtube.com', 'https://www.youtube.com', 'https://youtube.com'],
        'connect-src': ['\'self\'', 'https://www.googleapis.com', 'https://cdn.jsdelivr.net']
    }
    Talisman(app, content_security_policy=csp, force_https=False)

    # 블루프린트 등록
    from blueprints.auth import auth_bp
    from blueprints.main import main_bp
    from blueprints.admin import admin_bp
    from blueprints.push import push_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(push_bp)

    # 템플릿 필터
    @app.template_filter('from_json')
    def from_json_filter(value):
        if value is None or value == "":
            return []
        if isinstance(value, str):
            try:
                data = json.loads(value)
                return data if data is not None else []
            except:
                return []
        return value if isinstance(value, (list, dict)) else []

    @app.template_filter('korean_time')
    def korean_time_filter(dt):
        if dt is None: return ""
        if dt.tzinfo is None: return dt.strftime('%Y-%m-%d %H:%M')
        else: return dt.astimezone(KST).strftime('%Y-%m-%d %H:%M')

    # 구글 드라이브 DB 복구
    if db_path and not DATABASE_URL:
        try:
            if drive_manager.download_database(db_path):
                print(f"[Restore] 구글 드라이브로부터 최신 DB를 복구했습니다.")
        except Exception as e:
            print(f"[Restore Error]: {e}")

    # 데이터베이스 초기화
    with app.app_context():
        # 1. 누락된 컬럼 자동 패치 (마이그레이션 도구 대용)
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()
            is_pg = (db.engine.dialect.name == 'postgresql')
            
            user_table_original = next((t for t in existing_tables if t.lower() == 'user'), None)
            if user_table_original:
                existing_cols = [c['name'].lower() for c in inspector.get_columns(user_table_original)]
                user_columns_to_patch = {
                    'username': 'VARCHAR(80)',
                    'password_hash': 'VARCHAR(120)',
                    'created_at': 'TIMESTAMP',
                    'last_login': 'TIMESTAMP',
                    'login_attempts': 'INTEGER DEFAULT 0',
                    'locked_until': 'TIMESTAMP',
                    'password_changed': 'BOOLEAN DEFAULT FALSE' if is_pg else 'BOOLEAN DEFAULT 0',
                    'is_approved': 'BOOLEAN DEFAULT FALSE' if is_pg else 'BOOLEAN DEFAULT 0'
                }
                user_table_quoted = f'"{user_table_original}"' if (is_pg or user_table_original.lower() == 'user') else user_table_original
                for col_name, col_type in user_columns_to_patch.items():
                    if col_name.lower() not in existing_cols:
                        db.session.execute(text(f"ALTER TABLE {user_table_quoted} ADD COLUMN {col_name} {col_type}"))
                        print(f"[Patch] Added column {col_name} to {user_table_quoted}")
            
            post_table_original = next((t for t in existing_tables if t.lower() == 'post'), None)
            if post_table_original:
                existing_cols = [c['name'].lower() for c in inspector.get_columns(post_table_original)]
                post_columns_to_patch = {
                    'content': 'TEXT',
                    'author_id': 'INTEGER',
                    'created_at': 'TIMESTAMP',
                    'updated_at': 'TIMESTAMP',
                    'is_public': 'BOOLEAN DEFAULT TRUE' if is_pg else 'BOOLEAN DEFAULT 1',
                    'url_previews': "TEXT DEFAULT '[]'",
                    'files': "TEXT DEFAULT '[]'"
                }
                post_table_quoted = f'"{post_table_original}"' if (is_pg or post_table_original.lower() == 'post') else post_table_original
                for col_name, col_type in post_columns_to_patch.items():
                    if col_name.lower() not in existing_cols:
                        db.session.execute(text(f"ALTER TABLE {post_table_quoted} ADD COLUMN {col_name} {col_type}"))
                        print(f"[Patch] Added column {col_name} to {post_table_quoted}")
            
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"[Patch Error] 데이터베이스 패치 중 오류 발생: {e}")

        # 2. 테이블 생성 및 초기화
        db.create_all()
        from werkzeug.security import generate_password_hash
        
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                password_hash=generate_password_hash(os.environ.get('ADMIN_PASSWORD', 'admin123')),
                is_approved=True
            )
            db.session.add(admin_user)
            db.session.commit()
            print("기본 관리자 계정이 생성되었습니다.")

    # 스케줄러 설정
    setup_scheduler(app)

    return app

def setup_scheduler(app):
    from apscheduler.schedulers.background import BackgroundScheduler
    from utils.tasks import scheduled_db_sync_task

    def sync_task():
        with app.app_context():
            scheduled_db_sync_task()

    scheduler = BackgroundScheduler(timezone='Asia/Seoul')
    scheduler.add_job(func=sync_task, trigger='interval', minutes=10)
    scheduler.start()

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)