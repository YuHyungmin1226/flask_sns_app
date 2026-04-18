from dotenv import load_dotenv

# 환경 변수 로드 (임포트보다 먼저 실행되어야 함)
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
import os
import sys
import uuid
import json
import io
import zipfile
from concurrent.futures import ThreadPoolExecutor
from utils.url_utils import URLPreviewGenerator
from utils.google_drive_utils import drive_manager

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
app.config['MAX_CONTENT_LENGTH'] = 300 * 1024 * 1024  # 전체 용량 300MB 제한

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

url_preview_generator = URLPreviewGenerator()
KST = timezone(timedelta(hours=9))

def get_korean_time():
    return datetime.now(KST)

def get_korean_time_for_db():
    return datetime.now(KST).replace(tzinfo=None)

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

# 데이터베이스 모델
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=get_korean_time_for_db)
    last_login = db.Column(db.DateTime)
    login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)
    password_changed = db.Column(db.Boolean, default=False)
    is_approved = db.Column(db.Boolean, default=False)
    
    posts = db.relationship('Post', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=get_korean_time_for_db)
    updated_at = db.Column(db.DateTime, default=get_korean_time_for_db, onupdate=get_korean_time_for_db)
    is_public = db.Column(db.Boolean, default=True)
    url_previews = db.Column(db.Text, default='[]')
    files = db.Column(db.Text, default='[]')
    
    comments = db.relationship('Comment', backref='post', lazy=True, cascade='all, delete-orphan')

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=get_korean_time_for_db)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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

@app.route('/ping')
def ping():
    return jsonify({
        'status': 'alive',
        'timestamp': get_korean_time().isoformat(),
        'message': 'Flask SNS is running!'
    })

def init_db():
    try:
        with app.app_context():
            db.create_all()
            try:
                db.session.execute(db.text('SELECT is_approved FROM "user" LIMIT 1'))
            except Exception:
                db.session.rollback()
                print("User 테이블에 is_approved 컬럼 추가 중...")
                try:
                    with db.engine.connect() as conn:
                        conn.execute(db.text('ALTER TABLE "user" ADD COLUMN is_approved BOOLEAN DEFAULT TRUE'))
                        conn.commit()
                    print("is_approved 컬럼이 추가되었습니다.")
                except Exception as e:
                    print(f"컬럼 추가 실패: {e}")
            
            admin_user = User.query.filter_by(username='admin').first()
            if not admin_user:
                admin_user = User(
                    username='admin',
                    password_hash=generate_password_hash(os.environ.get('ADMIN_PASSWORD', 'admin123')),
                    password_changed=False
                )
                db.session.add(admin_user)
                db.session.commit()
                print("기본 관리자 계정이 생성되었습니다.")
            else:
                if not admin_user.is_approved:
                    admin_user.is_approved = True
                    db.session.commit()
                    print("관리자 계정이 승인되었습니다.")

    except Exception as e:
        print(f"데이터베이스 초기화 오류: {e}")

init_db()

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
        
        # 파일 개수 제한 (최대 30개)
        if len(files) > 30:
            flash('파일은 한 번에 최대 30개까지만 첨부할 수 있습니다.', 'error')
            return render_template('new_post.html')
        
        # 병렬 업로드를 위한 헬퍼 함수
        def upload_single_file(file):
            if not file or not file.filename:
                return None
            try:
                # 파일 내용을 메모리에 읽어서 독립적인 스트림 생성 (쓰레드 안전성 확보)
                file.seek(0)
                file_content = file.read()
                temp_stream = io.BytesIO(file_content)
                
                # 파일 업로드 (쓰레드별 로컬 드라이브 서비스 사용)
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
                    
                    embed_link = None
                    if mime_type.startswith('video/'):
                        embed_link = f"https://drive.google.com/file/d/{file_id}/preview"
                    
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

        # ThreadPoolExecutor를 사용한 병렬 업로드 수행
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
        
        flash('게시글이 작성되었습니다!', 'success')
        
        # AJAX 요청인 경우 JSON 반환
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'redirect': url_for('index')
            })
            
        return redirect(url_for('index'))
    
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
    
    comment = Comment(
        content=content,
        author_id=current_user.id,
        post_id=post_id
    )
    db.session.add(comment)
    db.session.commit()
    
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
            files_to_delete = json.loads(post.files)
            for file_info in files_to_delete:
                file_id = file_info.get('id')
                if file_id:
                    drive_manager.delete_file(file_id)
        except Exception as e:
            print(f"파일 삭제 처리 중 오류: {e}")
            
    db.session.delete(post)
    db.session.commit()
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
    return render_template('admin.html', users=users, posts=posts, pending_users=pending_users)

@app.route('/admin/user/<int:user_id>/approve', methods=['POST'])
@login_required
def approve_user(user_id):
    if current_user.username != 'admin':
        flash('관리자 권한이 필요합니다.', 'error')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    user.is_approved = True
    db.session.commit()
    flash(f'{user.username} 사용자가 승인되었습니다.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/user/<int:user_id>/reject', methods=['POST'])
@login_required
def reject_user(user_id):
    if current_user.username != 'admin':
        flash('관리자 권한이 필요합니다.', 'error')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    if user.username == 'admin':
        flash('관리자 계정은 거절할 수 없습니다.', 'error')
        return redirect(url_for('admin'))
    
    db.session.delete(user)
    db.session.commit()
    flash(f'{user.username} 가입 요청이 거절되었습니다.', 'warning')
    return redirect(url_for('admin'))

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.username != 'admin':
        flash('관리자 권한이 필요합니다.', 'error')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    if user.username == 'admin':
        flash('관리자 계정은 삭제할 수 없습니다.', 'error')
        return redirect(url_for('admin'))
    
    db.session.delete(user)
    db.session.commit()
    flash('사용자가 삭제되었습니다.', 'success')
    return redirect(url_for('admin'))

@app.route('/api/posts')
def api_posts():
    posts = Post.query.filter_by(is_public=True).order_by(Post.created_at.desc()).all()
    posts_data = []
    for post in posts:
        posts_data.append({
            'id': post.id,
            'content': post.content,
            'author': post.author.username,
            'created_at': post.created_at.isoformat(),
            'comment_count': len(post.comments)
        })
    return jsonify(posts_data)

@app.route('/export_markdown')
@login_required
def export_markdown():
    if current_user.username != 'admin':
        flash('관리자만 접근 가능한 기능입니다.', 'error')
        return redirect(url_for('index'))
    
    posts = Post.query.order_by(Post.created_at.desc()).all()
    
    # 메모리 내 ZIP 파일 생성을 위한 스트림
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
        for post in posts:
            # 마크다운 내용 구성
            md_content = f"# 게시물 (ID: {post.id})\n"
            md_content += f"- 작성자: {post.author.username}\n"
            md_content += f"- 작성일: {post.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            md_content += f"- 공개 여부: {'공개' if post.is_public else '비공개'}\n\n"
            
            md_content += "## 본문\n"
            md_content += f"{post.content if post.content else '(내용 없음)'}\n\n"
            
            # 첨부 파일 정보
            if post.files:
                files = json.loads(post.files)
                if files:
                    md_content += "## 첨부 파일\n"
                    for f in files:
                        md_content += f"- [{f.get('name')}]({f.get('view_link')})\n"
                    md_content += "\n"
            
            # URL 미리보기 정보
            if post.url_previews:
                previews = json.loads(post.url_previews)
                if previews:
                    md_content += "## 링크 미리보기\n"
                    for p in previews:
                        md_content += f"- [{p.get('title')}]({p.get('url')})\n"
                    md_content += "\n"
            
            # 파일명 생성 (특수문자 제거 및 날짜 포함)
            safe_date = post.created_at.strftime('%Y%m%d_%H%M%S')
            filename = f"post_{post.id}_{safe_date}.md"
            
            # ZIP에 파일 추가
            zip_file.writestr(filename, md_content)
    
    # 스트림 위치 초기화 후 전송
    zip_buffer.seek(0)
    
    filename = f"flask_sns_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=filename
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Flask SNS 앱 시작 (Port: {port})")
    app.run(debug=False, host='0.0.0.0', port=port)