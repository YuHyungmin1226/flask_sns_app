from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from models import User
from utils.time_utils import get_korean_time_for_db
from datetime import timedelta
import os

auth_bp = Blueprint('auth', __name__)

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

@auth_bp.route('/login', methods=['GET', 'POST'])
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
                return redirect(url_for('auth.change_password'))
            else:
                flash('로그인 성공!', 'success')
                return redirect(url_for('main.index'))
        else:
            user.login_attempts += 1
            if user.login_attempts >= 5:
                lock_account(user)
                flash('로그인 시도가 너무 많습니다. 계정이 잠겼습니다.', 'error')
            else:
                db.session.commit()
                flash(f'비밀번호가 올바르지 않습니다. ({5-user.login_attempts}회 남음)', 'error')
    
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
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
        from utils.tasks import trigger_db_sync
        trigger_db_sync()
        
        flash('회원가입 요청이 완료되었습니다. 관리자 승인 후 로그인 가능합니다.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('register.html')

@auth_bp.route('/change_password', methods=['GET', 'POST'])
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
        from utils.tasks import trigger_db_sync
        trigger_db_sync()
        
        flash('비밀번호가 성공적으로 변경되었습니다!', 'success')
        return redirect(url_for('main.index'))
    
    return render_template('change_password.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('auth.login'))
