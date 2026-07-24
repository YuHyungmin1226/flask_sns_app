from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, send_file, request
import io
from datetime import datetime
import json
from flask_login import login_required, current_user
from extensions import db
from models import User, Post, SystemLog
from utils.tasks import trigger_db_sync
import zipfile

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin')
@login_required
def admin_dashboard():
    if current_user.username != 'admin':
        flash('관리자 권한이 필요합니다.', 'error')
        return redirect(url_for('main.index'))
    
    users = User.query.all()
    posts = Post.query.order_by(Post.created_at.desc()).all()
    pending_users = User.query.filter_by(is_approved=False).all()
    
    # 최근 시스템 로그 10개 가져오기
    system_logs = SystemLog.query.order_by(SystemLog.created_at.desc()).limit(10).all()
    
    return render_template('admin.html', users=users, posts=posts, pending_users=pending_users, 
                           system_logs=system_logs)

@admin_bp.route('/admin/user/<int:user_id>/approve', methods=['POST'])
@login_required
def approve_user(user_id):
    if current_user.username != 'admin':
        return redirect(url_for('main.index'))
    
    user = User.query.get_or_404(user_id)
    user.is_approved = True
    db.session.commit()
    trigger_db_sync()
    flash(f'{user.username} 승인 완료.', 'success')
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/user/<int:user_id>/reject', methods=['POST'])
@login_required
def reject_user(user_id):
    if current_user.username != 'admin':
        return redirect(url_for('main.index'))
    
    user = User.query.get_or_404(user_id)
    if user.username != 'admin':
        db.session.delete(user)
        db.session.commit()
        trigger_db_sync()
        flash(f'{user.username} 거절 완료.', 'warning')
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.username != 'admin':
        return redirect(url_for('main.index'))
    
    user = User.query.get_or_404(user_id)
    if user.username != 'admin':
        db.session.delete(user)
        db.session.commit()
        trigger_db_sync()
        flash('삭제 완료.', 'success')
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/export_markdown')
@login_required
def export_markdown():
    if current_user.username != 'admin':
        return redirect(url_for('main.index'))
    
    posts = Post.query.order_by(Post.created_at.desc()).all()
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
        for post in posts:
            md = f"# {post.id}\n- User: {post.author.username}\n- Date: {post.created_at}\n\n{post.content}\n"
            zip_file.writestr(f"post_{post.id}.md", md)
    
    zip_buffer.seek(0)
    return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name=f"export_{datetime.now().strftime('%Y%m%d')}.zip")


@admin_bp.route('/admin/posts/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_posts():
    if current_user.username != 'admin':
        return jsonify({'success': False}), 403
        
    post_ids = request.form.getlist('post_ids')
    if not post_ids:
        flash('삭제할 게시물을 선택해주세요.', 'warning')
        return redirect(url_for('admin.admin_dashboard'))
        
    from utils.google_drive_utils import drive_manager
    
    deleted_count = 0
    for pid in post_ids:
        post = Post.query.get(int(pid))
        if post:
            if post.files:
                try:
                    for file_info in json.loads(post.files):
                        if file_info.get('id'):
                            drive_manager.delete_file(file_info.get('id'))
                except Exception as e:
                    print(f"파일 삭제 오류: {e}")
            db.session.delete(post)
            deleted_count += 1
            
    db.session.commit()
    trigger_db_sync()
    
    flash(f'{deleted_count}개의 게시물이 일괄 삭제되었습니다.', 'success')
    return redirect(url_for('admin.admin_dashboard'))
