import os
import sys
import json
import io
import zipfile
import threading
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory, send_file
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# 내부 모듈 임포트
from extensions import db, login_manager
from models import User, Post, Comment, SystemSetting
from utils.url_utils import URLPreviewGenerator
from utils.google_drive_utils import drive_manager
from utils.time_utils import KST, get_korean_time, get_korean_time_for_db

# 환경 변수 로드
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-key-change-in-production')

# 데이터베이스 설정
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    if getattr(sys, 'frozen', False):
        current_dir = os.path.dirname(sys.executable)
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, 'sns.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 300 * 1024 * 1024

# 확장 초기화
db.init_app(app)
login_manager.init_app(app)

url_preview_generator = URLPreviewGenerator()

# --- 구글 드라이브 DB 동기화 초기화 (Restore) ---
def restore_db_from_drive():
    try:
        if not os.environ.get('DATABASE_URL'): # SQLite 환경에서만 작동
            success = drive_manager.download_database(db_path)
            if success:
                print(f"[Restore] 구글 드라이브로부터 최신 DB를 복구했습니다.")
            else:
                print(f"[Restore] 드라이브에 DB가 없거나 복구에 실패했습니다. 로컬 DB를 사용합니다.")
    except Exception as e:
        print(f"[Restore Error] DB 복구 중 에러 발생: {e}")

# 앱 구동 시 즉시 복구 시도
restore_db_from_drive()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 템플릿 필터
@app.template_filter('from_json')
def from_json_filter(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except:
            return []
    return value

@app.template_filter('korean_time')
def korean_time_filter(dt):
    if dt is None:
        return ""
    if dt.tzinfo is None:
        return dt.strftime('%Y-%m-%d %H:%M')
    else:
        korean_dt = dt.astimezone(KST)
        return korean_dt.strftime('%Y-%m-%d %H:%M')

# 권한 및 보안 도구
def is_account_locked(user):
    if user.locked_until and user.locked_until > get_korean_time_for_db():
        return True
    return False

def lock_account(user, minutes=15):
    user.locked_until = get_korean_time_for_db() + timedelta(minutes=minutes)
    user.login_attempts = 0
    db.session.commit()

def reset_login_attempts(user):
    user.login_attempts = 0
    user.locked_until = None
    db.session.commit()

# 데이터베이스 초기화
def init_db():
    try:
        with app.app_context():
            db.create_all()
            
            # 관리자 계정 확인 및 생성
            admin_user = User.query.filter_by(username='admin').first()
            if not admin_user:
                admin_user = User(
                    username='admin',
                    password_hash=generate_password_hash(os.environ.get('ADMIN_PASSWORD', 'admin123')),
                    password_changed=False,
                    is_approved=True
                )
                db.session.add(admin_user)
                db.session.commit()
                print("기본 관리자 계정이 생성 및 승인되었습니다.")
            elif not admin_user.is_approved:
                admin_user.is_approved = True
                db.session.commit()
                print("관리자 계정이 활성화되었습니다.")

    except Exception as e:
        print(f"데이터베이스 초기화 오류: {e}")

init_db()

@app.route('/ping')
def ping():
    return jsonify({
        'status': 'alive',
        'timestamp': get_korean_time().isoformat(),
        'message': 'Flask SNS is running!'
    })

@app.route('/')
def index():
    if current_user.is_authenticated:
        posts = Post.query.filter_by(is_public=True).order_by(Post.created_at.desc()).all()
        return render_template('index.html', posts=posts)
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if not user:
            flash('존재하지 않는 사용자명입니다.', 'error')
            return render_template('login.html')
        
        if is_account_locked(user):
            flash('계정이 잠겼습니다. 잠시 후 다시 시도해주세요.', 'error')
            return render_template('login.html')
        
        if not user.is_approved:
            flash('관리자 승인 대기 중인 계정입니다.', 'warning')
            return render_template('login.html')

        if check_password_hash(user.password_hash, password):
            reset_login_attempts(user)
            user.last_login = get_korean_time_for_db()
            db.session.commit()
            login_user(user)
            
            if not user.password_changed and password == os.environ.get('ADMIN_PASSWORD', 'admin123'):
                flash('보안을 위해 비밀번호를 변경해주세요.', 'warning')
                return redirect(url_for('change_password'))
            else:
                flash('로그인 성공!', 'success')
                return redirect(url_for('index'))
        else:
            user.login_attempts += 1
            if user.login_attempts >= 5:
                lock_account(user)
                flash('로그인 시도가 너무 많습니다. 계정이 잠겼습니다.', 'error')
            else:
                db.session.commit()
                flash(f'비밀번호가 올바르지 않습니다. ({5-user.login_attempts}회 남음)', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('비밀번호가 일치하지 않습니다.', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('이미 존재하는 사용자명입니다.', 'error')
            return render_template('register.html')
        
        user = User(
            username=username,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        trigger_db_sync()
        
        flash('회원가입 요청이 완료되었습니다. 관리자 승인 후 로그인 가능합니다.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not check_password_hash(current_user.password_hash, current_password):
            flash('현재 비밀번호가 올바르지 않습니다.', 'error')
            return render_template('change_password.html')
        
        if new_password != confirm_password:
            flash('새 비밀번호가 일치하지 않습니다.', 'error')
            return render_template('change_password.html')
        
        if len(new_password) < 6:
            flash('비밀번호는 최소 6자 이상이어야 합니다.', 'error')
            return render_template('change_password.html')
        
        current_user.password_hash = generate_password_hash(new_password)
        current_user.password_changed = True
        db.session.commit()
        trigger_db_sync()
        
        flash('비밀번호가 성공적으로 변경되었습니다!', 'success')
        return redirect(url_for('index'))
    
    return render_template('change_password.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('login'))

@app.route('/post/new', methods=['GET', 'POST'])
@login_required
def new_post():
    if request.method == 'POST':
        content = request.form.get('content')
        is_public = request.form.get('is_public') == 'on'
        
        urls = url_preview_generator.extract_urls(content)
        url_previews = []
        for url in urls:
            preview = url_preview_generator.get_url_preview(url)
            if preview:
                url_previews.append(preview)
        
        uploaded_files = []
        files = request.files.getlist('files')
        
        if len(files) > 30:
            flash('파일은 한 번에 최대 30개까지만 첨부할 수 있습니다.', 'error')
            return render_template('new_post.html')
        
        def upload_single_file(file):
            if not file or not file.filename:
                return None
            try:
                file.seek(0)
                file_content = file.read()
                temp_stream = io.BytesIO(file_content)
                
                file_info = drive_manager.upload_file(
                    temp_stream, 
                    file.filename, 
                    file.content_type or 'application/octet-stream'
                )
                if file_info:
                    file_id = file_info.get('id')
                    mime_type = file_info.get('mimeType', '')
                    thumbnail_link = file_info.get('thumbnailLink')
                    if thumbnail_link and mime_type.startswith('image/'):
                        thumbnail_link = thumbnail_link.split('=s')[0] + '=s1000'
                    
                    embed_link = f"https://drive.google.com/file/d/{file_id}/preview" if mime_type.startswith('video/') else None
                    
                    return {
                        'id': file_id,
                        'name': file_info.get('name'),
                        'view_link': file_info.get('webViewLink'),
                        'download_link': file_info.get('webContentLink'),
                        'thumbnail_link': thumbnail_link,
                        'embed_link': embed_link,
                        'mime_type': mime_type,
                        'size': file_info.get('size')
                    }
            except Exception as e:
                print(f"파일 업로드 실패 ({file.filename}): {e}")
            return None

        uploaded_files = []
        if files and any(f.filename for f in files):
            with ThreadPoolExecutor(max_workers=5) as executor:
                results = list(executor.map(upload_single_file, files))
                uploaded_files = [r for r in results if r is not None]
        
        if not content and not uploaded_files:
            flash('내용을 입력하거나 파일을 첨부해 주세요.', 'error')
            return render_template('new_post.html')
        
        post = Post(
            content=content,
            author_id=current_user.id,
            is_public=is_public,
            url_previews=json.dumps(url_previews, ensure_ascii=False),
            files=json.dumps(uploaded_files, ensure_ascii=False)
        )
        db.session.add(post)
        db.session.commit()
        trigger_db_sync()
        
        flash('게시글이 작성되었습니다!', 'success')
        return jsonify({'success': True, 'redirect': url_for('index')}) if request.headers.get('X-Requested-With') == 'XMLHttpRequest' else redirect(url_for('index'))
    
    return render_template('new_post.html')

@app.route('/post/<int:post_id>')
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    if not post.is_public and (not current_user.is_authenticated or post.author_id != current_user.id):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('index'))
    
    url_previews = json.loads(post.url_previews) if post.url_previews else []
    files = json.loads(post.files) if post.files else []
    return render_template('view_post.html', post=post, url_previews=url_previews, files=files)

@app.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    post = Post.query.get_or_404(post_id)
    content = request.form.get('content')
    if not content.strip():
        flash('댓글 내용을 입력해주세요.', 'error')
        return redirect(url_for('view_post', post_id=post_id))
    
    comment = Comment(content=content, author_id=current_user.id, post_id=post_id)
    db.session.add(comment)
    db.session.commit()
    trigger_db_sync()
    
    flash('댓글이 작성되었습니다!', 'success')
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author_id != current_user.id:
        flash('삭제 권한이 없습니다.', 'error')
        return redirect(url_for('index'))
    
    if post.files:
        try:
            for file_info in json.loads(post.files):
                if file_info.get('id'):
                    drive_manager.delete_file(file_info.get('id'))
        except Exception as e:
            print(f"파일 삭제 오류: {e}")
            
    db.session.delete(post)
    db.session.commit()
    trigger_db_sync()
    flash('게시글이 삭제되었습니다.', 'success')
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    user_posts = Post.query.filter_by(author_id=current_user.id).order_by(Post.created_at.desc()).all()
    return render_template('profile.html', user_posts=user_posts)

@app.route('/admin')
@login_required
def admin():
    if current_user.username != 'admin':
        flash('관리자 권한이 필요합니다.', 'error')
        return redirect(url_for('index'))
    
    users = User.query.all()
    posts = Post.query.order_by(Post.created_at.desc()).all()
    pending_users = User.query.filter_by(is_approved=False).all()
    news_bot_enabled = SystemSetting.query.get('news_bot_enabled').value == 'True' if SystemSetting.query.get('news_bot_enabled') else False
    weather_bot_enabled = SystemSetting.query.get('weather_bot_enabled').value == 'True' if SystemSetting.query.get('weather_bot_enabled') else False
    
    return render_template('admin.html', users=users, posts=posts, pending_users=pending_users, news_bot_enabled=news_bot_enabled, weather_bot_enabled=weather_bot_enabled)

@app.route('/admin/user/<int:user_id>/approve', methods=['POST'])
@login_required
def approve_user(user_id):
    if current_user.username != 'admin':
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    user.is_approved = True
    db.session.commit()
    trigger_db_sync()
    flash(f'{user.username} 승인 완료.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/user/<int:user_id>/reject', methods=['POST'])
@login_required
def reject_user(user_id):
    if current_user.username != 'admin':
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    if user.username != 'admin':
        db.session.delete(user)
        db.session.commit()
        trigger_db_sync()
        flash(f'{user.username} 거절 완료.', 'warning')
    return redirect(url_for('admin'))

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.username != 'admin':
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    if user.username != 'admin':
        db.session.delete(user)
        db.session.commit()
        trigger_db_sync()
        flash('삭제 완료.', 'success')
    return redirect(url_for('admin'))

@app.route('/export_markdown')
@login_required
def export_markdown():
    if current_user.username != 'admin':
        return redirect(url_for('index'))
    
    posts = Post.query.order_by(Post.created_at.desc()).all()
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
        for post in posts:
            md = f"# {post.id}\n- User: {post.author.username}\n- Date: {post.created_at}\n\n{post.content}\n"
            zip_file.writestr(f"post_{post.id}.md", md)
    
    zip_buffer.seek(0)
    return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name=f"export_{datetime.now().strftime('%Y%m%d')}.zip")

@app.route('/admin/news-bot/toggle', methods=['POST'])
@login_required
def toggle_news_bot():
    if current_user.username != 'admin': return jsonify({'success': False}), 403
    setting = SystemSetting.query.get('news_bot_enabled') or SystemSetting(key='news_bot_enabled', value='True')
    if not setting.value: db.session.add(setting)
    setting.value = 'False' if setting.value == 'True' else 'True'
    db.session.commit()
    trigger_db_sync()
    return jsonify({'success': True, 'enabled': setting.value == 'True'})

@app.route('/admin/weather-bot/toggle', methods=['POST'])
@login_required
def toggle_weather_bot():
    if current_user.username != 'admin': return jsonify({'success': False}), 403
    setting = SystemSetting.query.get('weather_bot_enabled') or SystemSetting(key='weather_bot_enabled', value='True')
    if not setting.value: db.session.add(setting)
    setting.value = 'False' if setting.value == 'True' else 'True'
    db.session.commit()
    trigger_db_sync()
    return jsonify({'success': True, 'enabled': setting.value == 'True'})

# APScheduler
from apscheduler.schedulers.background import BackgroundScheduler
import utils.news_crawler as news_crawler
import utils.weather_bot as weather_bot

def scheduled_news_task():
    try: news_crawler.fetch_and_post_news(app, db, Post, SystemSetting, User)
    except Exception as e: print(f"News Error: {e}")

def scheduled_weather_task():
    try: weather_bot.fetch_and_post_weather(app, db, Post, SystemSetting, User)
    except Exception as e: print(f"Weather Error: {e}")

def scheduled_db_sync_task():
    try: 
        if not os.environ.get('DATABASE_URL'): drive_manager.sync_database(db_path)
    except Exception as e: print(f"Sync Error: {e}")

def trigger_db_sync():
    if not os.environ.get('DATABASE_URL'): threading.Thread(target=scheduled_db_sync_task).start()

scheduler = BackgroundScheduler(timezone='Asia/Seoul')
scheduler.add_job(func=scheduled_news_task, trigger='cron', hour='6,12,18', minute=0)
scheduler.add_job(func=scheduled_weather_task, trigger='cron', hour=6, minute=0)
scheduler.add_job(func=scheduled_db_sync_task, trigger='interval', minutes=10)
scheduler.start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)