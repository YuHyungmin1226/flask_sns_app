from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, send_file, request
import io
from datetime import datetime
import json
from flask_login import login_required, current_user
from extensions import db
from models import User, Post, SystemSetting, SystemLog
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
    weather_bot_enabled = SystemSetting.query.get('weather_bot_enabled').value == 'True' if SystemSetting.query.get('weather_bot_enabled') else False
    npc_system_enabled = SystemSetting.query.get('npc_system_enabled').value == 'True' if SystemSetting.query.get('npc_system_enabled') else False
    
    # 최근 시스템 로그 10개 가져오기
    system_logs = SystemLog.query.order_by(SystemLog.created_at.desc()).limit(10).all()
    
    return render_template('admin.html', users=users, posts=posts, pending_users=pending_users, 
                           weather_bot_enabled=weather_bot_enabled, npc_system_enabled=npc_system_enabled,
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

@admin_bp.route('/admin/weather-bot/toggle', methods=['POST'])
@login_required
def toggle_weather_bot():
    if current_user.username != 'admin': return jsonify({'success': False}), 403
    setting = SystemSetting.query.get('weather_bot_enabled') or SystemSetting(key='weather_bot_enabled', value='True')
    if not SystemSetting.query.get('weather_bot_enabled'): db.session.add(setting)
    setting.value = 'False' if setting.value == 'True' else 'True'
    db.session.commit()
    trigger_db_sync()
    return jsonify({'success': True, 'enabled': setting.value == 'True'})

@admin_bp.route('/admin/npc-system/toggle', methods=['POST'])
@login_required
def toggle_npc_system():
    if current_user.username != 'admin': return jsonify({'success': False}), 403
    setting = SystemSetting.query.get('npc_system_enabled') or SystemSetting(key='npc_system_enabled', value='True')
    if not SystemSetting.query.get('npc_system_enabled'): db.session.add(setting)
    setting.value = 'False' if setting.value == 'True' else 'True'
    db.session.commit()
    trigger_db_sync()
    return jsonify({'success': True, 'enabled': setting.value == 'True'})

@admin_bp.route('/admin/npc/<int:npc_id>/force-post', methods=['POST'])
@login_required
def force_npc_post(npc_id):
    if current_user.username != 'admin': return jsonify({'success': False}), 403
    from utils.npc_manager import execute_npc_post
    npc = User.query.get_or_404(npc_id)
    if not npc.is_npc: return jsonify({'success': False, 'error': 'Not an NPC'}), 400
    
    weather_setting = SystemSetting.query.get('current_weather')
    weather_data = json.loads(weather_setting.value) if weather_setting else None
    
    execute_npc_post(npc, weather_data)
    flash(f'{npc.username}의 게시글 작성을 강제 실행했습니다.', 'success')
    return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/npc/post-as', methods=['POST'])
@login_required
def post_as_npc():
    if current_user.username != 'admin': return jsonify({'success': False}), 403
    npc_id = request.form.get('npc_id', type=int)
    content = request.form.get('content')
    
    if not content:
        flash('내용을 입력해주세요.', 'error')
        return redirect(url_for('admin.admin_dashboard'))
        
    npc = User.query.get_or_404(npc_id)
    new_post = Post(content=content, author_id=npc.id, is_public=True)
    db.session.add(new_post)
    db.session.commit()
    
    flash(f'{npc.username} 계정으로 글을 올렸습니다.', 'success')
    return redirect(url_for('admin.admin_dashboard'))
