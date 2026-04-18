from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, send_file
import io
from datetime import datetime
from flask_login import login_required, current_user
from extensions import db
from models import User, Post, SystemSetting
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
    news_bot_enabled = SystemSetting.query.get('news_bot_enabled').value == 'True' if SystemSetting.query.get('news_bot_enabled') else False
    weather_bot_enabled = SystemSetting.query.get('weather_bot_enabled').value == 'True' if SystemSetting.query.get('weather_bot_enabled') else False
    
    return render_template('admin.html', users=users, posts=posts, pending_users=pending_users, news_bot_enabled=news_bot_enabled, weather_bot_enabled=weather_bot_enabled)

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

@admin_bp.route('/admin/news-bot/toggle', methods=['POST'])
@login_required
def toggle_news_bot():
    if current_user.username != 'admin': return jsonify({'success': False}), 403
    setting = SystemSetting.query.get('news_bot_enabled') or SystemSetting(key='news_bot_enabled', value='True')
    if not setting.value: db.session.add(setting)
    setting.value = 'False' if setting.value == 'True' else 'True'
    db.session.commit()
    trigger_db_sync()
    return jsonify({'success': True, 'enabled': setting.value == 'True'})

@admin_bp.route('/admin/weather-bot/toggle', methods=['POST'])
@login_required
def toggle_weather_bot():
    if current_user.username != 'admin': return jsonify({'success': False}), 403
    setting = SystemSetting.query.get('weather_bot_enabled') or SystemSetting(key='weather_bot_enabled', value='True')
    if not setting.value: db.session.add(setting)
    setting.value = 'False' if setting.value == 'True' else 'True'
    db.session.commit()
    trigger_db_sync()
    return jsonify({'success': True, 'enabled': setting.value == 'True'})
