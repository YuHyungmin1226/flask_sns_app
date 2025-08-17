from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
import os
import sys
import uuid
import json
from utils.url_utils import URLPreviewGenerator
from utils.file_utils import save_file, validate_file, get_file_info_from_json, delete_file, get_file_size_display

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')

# Railway 배포 대응 - 데이터베이스 설정
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    # Railway PostgreSQL 사용
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    # 로컬 개발용 SQLite
    if getattr(sys, 'frozen', False):
        current_dir = os.path.dirname(sys.executable)
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, 'sns.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# URL 미리보기 생성기
url_preview_generator = URLPreviewGenerator()

# Jinja2 필터 추가
@app.template_filter('from_json')
def from_json_filter(value):
    """JSON 문자열을 파이썬 객체로 변환하는 필터"""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except:
            return []
    return value

@app.template_filter('korean_time')
def korean_time_filter(dt):
    """한국 시간으로 포맷팅하는 필터"""
    if dt is None:
        return ""
    
    # UTC 시간을 한국 시간으로 변환 (이미 한국 시간이면 그대로 사용)
    if dt.tzinfo is None:
        # timezone 정보가 없으면 한국 시간으로 가정
        korean_dt = dt.replace(tzinfo=KST)
    else:
        # UTC 시간을 한국 시간으로 변환
        korean_dt = dt.astimezone(KST)
    
    return korean_dt.strftime('%Y-%m-%d %H:%M')

# 한국 시간대 설정
KST = timezone(timedelta(hours=9))

def get_korean_time():
    """한국 시간 반환"""
    return datetime.now(KST)

# 데이터베이스 모델
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=get_korean_time)
    last_login = db.Column(db.DateTime)
    login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)
    password_changed = db.Column(db.Boolean, default=False)  # 비밀번호 변경 여부
    
    posts = db.relationship('Post', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=get_korean_time)
    updated_at = db.Column(db.DateTime, default=get_korean_time, onupdate=get_korean_time)
    is_public = db.Column(db.Boolean, default=True)
    url_previews = db.Column(db.Text, default='[]')  # JSON 문자열로 저장
    files = db.Column(db.Text, default='[]')  # JSON 문자열로 저장
    
    comments = db.relationship('Comment', backref='post', lazy=True, cascade='all, delete-orphan')

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=get_korean_time)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 보안 관련 함수들
def is_account_locked(user):
    if user.locked_until and user.locked_until > datetime.utcnow():
        return True
    return False

def lock_account(user, minutes=15):
    user.locked_until = get_korean_time() + timedelta(minutes=minutes)
    user.login_attempts = 0
    db.session.commit()

def reset_login_attempts(user):
    user.login_attempts = 0
    user.locked_until = None
    db.session.commit()

# Railway 슬립모드 방지용 핑 엔드포인트
@app.route('/ping')
def ping():
    """Railway 슬립모드 방지용 핑 엔드포인트"""
    return jsonify({
        'status': 'alive',
        'timestamp': datetime.now(KST).isoformat(),
        'message': 'Flask SNS is running!'
    })

# 라우트
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
        
        if check_password_hash(user.password_hash, password):
            reset_login_attempts(user)
            user.last_login = get_korean_time()
            db.session.commit()
            login_user(user)
            
            # 기본 비밀번호 사용 중인지 확인
            if not user.password_changed and password == 'admin123':
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
        
        flash('회원가입이 완료되었습니다!', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # 현재 비밀번호 확인
        if not check_password_hash(current_user.password_hash, current_password):
            flash('현재 비밀번호가 올바르지 않습니다.', 'error')
            return render_template('change_password.html')
        
        # 새 비밀번호 확인
        if new_password != confirm_password:
            flash('새 비밀번호가 일치하지 않습니다.', 'error')
            return render_template('change_password.html')
        
        # 새 비밀번호 유효성 검사
        if len(new_password) < 6:
            flash('비밀번호는 최소 6자 이상이어야 합니다.', 'error')
            return render_template('change_password.html')
        
        # 비밀번호 변경
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
        
        # URL 미리보기 생성
        urls = url_preview_generator.extract_urls(content)
        print(f"추출된 URL들: {urls}")
        url_previews = []
        for url in urls:
            print(f"URL 미리보기 처리 중: {url}")
            preview = url_preview_generator.get_url_preview(url)
            if preview:
                print(f"미리보기 생성 성공: {preview}")
                url_previews.append(preview)
            else:
                print(f"미리보기 생성 실패: {url}")
        
        print(f"최종 URL 미리보기: {url_previews}")
        
        # Railway 배포용 - 파일 업로드 임시 비활성화
        uploaded_files = []
        # files = request.files.getlist('files')
        # 
        # print(f"업로드된 파일 수: {len(files)}")
        # print(f"request.files: {request.files}")
        # print(f"request.form: {request.form}")
        # 
        # for file in files:
        #     if file and file.filename:
        #         print(f"파일명: {file.filename}")
        #         print(f"파일 크기: {file.content_length}")
        #         print(f"파일 타입: {file.content_type}")
        #         
        #         # 파일 유효성 검사
        #         validation_errors = validate_file(file)
        #         if validation_errors:
        #             for error in validation_errors:
        #                 flash(error, 'error')
        #             return render_template('new_post.html')
        #         
        #         # 파일 저장
        #         try:
        #             file_info = save_file(file, file.filename)
        #             print(f"저장된 파일 정보: {file_info}")
        #             uploaded_files.append(file_info)
        #         except Exception as e:
        #             print(f"파일 업로드 중 오류: {e}")
        #             import traceback
        #             traceback.print_exc()
        #             flash(f'파일 업로드 중 오류가 발생했습니다: {str(e)}', 'error')
        #             return render_template('new_post.html')
        
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
        return redirect(url_for('index'))
    
    return render_template('new_post.html')

@app.route('/post/<int:post_id>')
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    if not post.is_public and (not current_user.is_authenticated or post.author_id != current_user.id):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('index'))
    
    url_previews = json.loads(post.url_previews) if post.url_previews else []
    files = get_file_info_from_json(post.files)
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
    
    # Railway 배포용 - 파일 삭제 임시 비활성화
    # 첨부된 파일들 삭제 로직은 현재 비활성화됨
    
    db.session.delete(post)
    db.session.commit()
    
    flash('게시글이 삭제되었습니다.', 'success')
    
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    user_posts = Post.query.filter_by(author_id=current_user.id).order_by(Post.created_at.desc()).all()
    return render_template('profile.html', user_posts=user_posts)

# 관리자 기능
@app.route('/admin')
@login_required
def admin():
    if current_user.username != 'admin':
        flash('관리자 권한이 필요합니다.', 'error')
        return redirect(url_for('index'))
    
    users = User.query.all()
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template('admin.html', users=users, posts=posts)

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

# 파일 다운로드 (Railway 배포용 - 임시 비활성화)
@app.route('/download/<path:filename>')
def download_file(filename):
    """파일 다운로드/표시 (Railway 배포용 - 임시 비활성화)"""
    flash('파일 업로드 기능은 현재 비활성화되어 있습니다.', 'info')
    return redirect(url_for('index'))

# 파일 삭제 (Railway 배포용 - 임시 비활성화)
@app.route('/post/<int:post_id>/file/<filename>/delete', methods=['POST'])
@login_required
def delete_post_file(post_id, filename):
    """게시글의 특정 파일 삭제 (Railway 배포용 - 임시 비활성화)"""
    flash('파일 업로드 기능은 현재 비활성화되어 있습니다.', 'info')
    return redirect(url_for('view_post', post_id=post_id))

# API 엔드포인트
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

if __name__ == '__main__':
    # Railway 배포용 포트 설정
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port) 