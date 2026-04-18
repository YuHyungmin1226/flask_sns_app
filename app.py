import os
import sys
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_talisman import Talisman
from dotenv import load_dotenv
import markdown2
import bleach
from markupsafe import Markup

# 내부 모듈 임포트
from extensions import db, login_manager, csrf
from models import User, Post, SystemSetting
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
    app.config['MAX_CONTENT_LENGTH'] = 300 * 1024 * 1024
    
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
        'style-src': ['\'self\'', 'https://cdn.jsdelivr.net', 'https://fonts.googleapis.com', '\'unsafe-inline\''],
        'font-src': ['\'self\'', 'https://cdn.jsdelivr.net', 'https://fonts.gstatic.com'],
        'img-src': ['\'self\'', 'data:', 'https://*.googleusercontent.com', 'https://drive.google.com'],
        'frame-src': ['\'self\'', 'https://drive.google.com', 'https://www.youtube.com']
    }
    Talisman(app, content_security_policy=csp, force_https=False)

    # 블루프린트 등록
    from blueprints.auth import auth_bp
    from blueprints.main import main_bp
    from blueprints.admin import admin_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    # 템플릿 필터
    @app.template_filter('from_json')
    def from_json_filter(value):
        if isinstance(value, str):
            try: return json.loads(value)
            except: return []
        return value

    @app.template_filter('korean_time')
    def korean_time_filter(dt):
        if dt is None: return ""
        if dt.tzinfo is None: return dt.strftime('%Y-%m-%d %H:%M')
        else: return dt.astimezone(KST).strftime('%Y-%m-%d %H:%M')

    @app.template_filter('markdown')
    def markdown_filter(text):
        if not text: return ""
        # Convert Markdown to HTML with common extras
        html = markdown2.markdown(text, extras=[
            "fenced-code-blocks", 
            "tables", 
            "break-on-newline", 
            "strike"
        ])
        
        # Define allowed tags for sanitization (keeping it secure but rich)
        allowed_tags = bleach.sanitizer.ALLOWED_TAGS | {
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'br', 'hr', 
            'pre', 'code', 'blockquote', 'table', 'thead', 'tbody', 
            'tr', 'th', 'td', 'span', 'del', 'ins', 'details', 'summary'
        }
        allowed_attrs = bleach.sanitizer.ALLOWED_ATTRIBUTES.copy()
        allowed_attrs.update({
            'code': ['class'],
            'span': ['class'],
            'th': ['style'],
            'td': ['style'],
            'a': ['href', 'title', 'target']
        })
        
        # Sanitize the HTML
        clean_html = bleach.clean(html, tags=allowed_tags, attributes=allowed_attrs)
        return Markup(clean_html)

    # 구글 드라이브 DB 복구
    if db_path and not DATABASE_URL:
        try:
            if drive_manager.download_database(db_path):
                print(f"[Restore] 구글 드라이브로부터 최신 DB를 복구했습니다.")
        except Exception as e:
            print(f"[Restore Error]: {e}")

    # 데이터베이스 초기화
    with app.app_context():
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
    import utils.news_crawler as news_crawler
    import utils.weather_bot as weather_bot
    from utils.tasks import scheduled_db_sync_task

    def scheduled_news_task():
        with app.app_context():
            try: news_crawler.fetch_and_post_news(app, db, Post, SystemSetting, User)
            except Exception as e: print(f"News Error: {e}")

    def scheduled_weather_task():
        with app.app_context():
            try: weather_bot.fetch_and_post_weather(app, db, Post, SystemSetting, User)
            except Exception as e: print(f"Weather Error: {e}")

    def sync_task():
        with app.app_context():
            scheduled_db_sync_task()

    scheduler = BackgroundScheduler(timezone='Asia/Seoul')
    scheduler.add_job(func=scheduled_news_task, trigger='cron', hour='6,12,18', minute=0)
    scheduler.add_job(func=scheduled_weather_task, trigger='cron', hour=6, minute=0)
    scheduler.add_job(func=sync_task, trigger='interval', minutes=10)
    scheduler.start()

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)