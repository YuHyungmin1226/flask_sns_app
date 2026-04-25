from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, json
from flask_login import login_required, current_user
from extensions import db
from models import User, Post, Comment
from utils.tasks import trigger_db_sync
from utils.url_utils import URLPreviewGenerator
from utils.google_drive_utils import drive_manager
from concurrent.futures import ThreadPoolExecutor
import io

main_bp = Blueprint('main', __name__)
url_preview_generator = URLPreviewGenerator()

@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        page = request.args.get('page', 1, type=int)
        pagination = Post.query.filter_by(is_public=True).order_by(Post.created_at.desc()).paginate(page=page, per_page=10)
        posts = pagination.items
        return render_template('index.html', posts=posts, has_next=pagination.has_next)
    return redirect(url_for('auth.login'))

@main_bp.route('/posts/load-more')
@login_required
def load_more():
    page = request.args.get('page', 1, type=int)
    pagination = Post.query.filter_by(is_public=True).order_by(Post.created_at.desc()).paginate(page=page, per_page=10)
    
    html_snippets = []
    for post in pagination.items:
        html_snippets.append(render_template('partials/_post_card.html', post=post))
    
    return jsonify({
        'html': "".join(html_snippets),
        'has_next': pagination.has_next
    })

@main_bp.route('/search')
@login_required
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return redirect(url_for('main.index'))
    
    # Search in post content and author username
    posts = Post.query.join(User).filter(
        (Post.content.like(f'%{query}%')) | 
        (User.username.like(f'%{query}%'))
    ).filter(Post.is_public == True).order_by(Post.created_at.desc()).all()
    
    # Search for users
    users = User.query.filter(User.username.like(f'%{query}%')).all()
    
    return render_template('search_results.html', posts=posts, users=users, query=query)

@main_bp.route('/post/new', methods=['GET', 'POST'])
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
        
        # filetype은 시스템 라이브러리 의존성이 없어 컨테이너 환경에서 더 안전합니다.
        import filetype

        def upload_single_file(file):
            if not file or not file.filename:
                return None
            try:
                file.seek(0)
                file_content = file.read()
                
                # MIME 타입 검증 (파일 헤더 기반)
                import mimetypes
                kind = filetype.guess(file_content)
                mime = kind.mime if kind else None
                
                # filetype이 인식 못하면 브라우저 제공 타입이나 확장자로 판단 (HEIC 등 대응)
                if not mime:
                    mime = file.content_type
                if not mime or mime == 'application/octet-stream':
                    mime, _ = mimetypes.guess_type(file.filename)
                
                if not mime:
                    mime = 'application/octet-stream'
                
                # 소문자 변환으로 비교 안정성 확보
                mime = mime.lower()
                
                allowed_prefixes = ['image/', 'video/', 'application/pdf', 'audio/']
                allowed_exact = ['application/zip', 'application/x-zip-compressed', 'text/plain']
                
                is_allowed = any(mime.startswith(p) for p in allowed_prefixes) or mime in allowed_exact
                if not is_allowed:
                    return None

                temp_stream = io.BytesIO(file_content)
                
                file_info = drive_manager.upload_file(
                    temp_stream, 
                    file.filename, 
                    mime or 'application/octet-stream'
                )
                if file_info:
                    file_id = file_info.get('id')
                    mime_type = file_info.get('mimeType', '')
                    thumbnail_link = file_info.get('thumbnailLink')
                    
                    # 이미지이거나, HEIC/HEIF 등 미리보기가 가능한 파일인 경우 썸네일 처리
                    is_image = mime_type.startswith('image/') or mime_type in ['image/heic', 'image/heif']
                    
                    if thumbnail_link and is_image:
                        thumbnail_link = thumbnail_link.split('=s')[0] + '=s1000'
                    
                    embed_link = f"https://drive.google.com/file/d/{file_id}/preview" if mime_type.startswith('video/') else None
                    
                    return {
                        'id': file_id,
                        'name': file_info.get('name'),
                        'view_link': file_info.get('webViewLink'),
                        'download_link': file_info.get('webContentLink'),
                        'mime_type': mime_type,
                        'size': file_info.get('size')
                    }
            except Exception as e:
                print(f"파일 업로드 실패 ({file.filename}): {e}")
            return None

        if files and any(f.filename for f in files):
            with ThreadPoolExecutor(max_workers=5) as executor:
                results = list(executor.map(upload_single_file, files))
                uploaded_files = [r for r in results if r is not None]
        
        if not content and not uploaded_files:
            flash('내용을 입력하거나 파일을 첨부해 주세요.', 'error')
            return render_template('new_post.html')
        from utils.tasks import trigger_db_sync
        trigger_db_sync()
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
        return jsonify({'success': True, 'redirect': url_for('main.index')}) if request.headers.get('X-Requested-With') == 'XMLHttpRequest' else redirect(url_for('main.index'))
    
    return render_template('new_post.html')

@main_bp.route('/post/<int:post_id>')
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    if not post.is_public and (not current_user.is_authenticated or post.author_id != current_user.id):
        flash('접근 권한이 없습니다.', 'error')
        return redirect(url_for('main.index'))
    
    url_previews = json.loads(post.url_previews) if post.url_previews else []
    files = json.loads(post.files) if post.files else []
    return render_template('view_post.html', post=post, url_previews=url_previews, files=files)

@main_bp.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    post = Post.query.get_or_404(post_id)
    content = request.form.get('content')
    if not content.strip():
        flash('댓글 내용을 입력해주세요.', 'error')
        return redirect(url_for('main.view_post', post_id=post_id))
    
    comment = Comment(content=content, author_id=current_user.id, post_id=post_id)
    db.session.add(comment)
    db.session.commit()
    trigger_db_sync()
    
    flash('댓글이 작성되었습니다!', 'success')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'message': '댓글이 작성되었습니다!',
            'comment': {
                'author': current_user.username,
                'content': content,
                'created_at': '방금 전'
            }
        })
        
    return redirect(url_for('main.view_post', post_id=post_id))

@main_bp.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author_id != current_user.id:
        flash('삭제 권한이 없습니다.', 'error')
        return redirect(url_for('main.index'))
    
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
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': '게시글이 삭제되었습니다.'})

    flash('게시글이 삭제되었습니다.', 'success')
    return redirect(url_for('main.index'))

@main_bp.route('/profile')
@login_required
def profile():
    user_posts = Post.query.filter_by(author_id=current_user.id).order_by(Post.created_at.desc()).all()
    return render_template('profile.html', user_posts=user_posts)

@main_bp.route('/file/thumbnail/<file_id>')
def get_thumbnail(file_id):
    """
    구글 드라이브의 임시 썸네일 링크는 몇 시간 후 만료되므로, 
    영구적인 접근을 위해 서버 측에서 리다이렉트해주는 엔드포인트입니다.
    """
    try:
        # 파일 정보 가져오기 (가장 최신의 썸네일 링크 획득)
        file_info = drive_manager.service.files().get(
            fileId=file_id, 
            fields='thumbnailLink'
        ).execute()
        
        thumbnail_link = file_info.get('thumbnailLink')
        if thumbnail_link:
            # 해상도 조절 (기본값은 작으므로 s1000으로 확장)
            if '=s' in thumbnail_link:
                thumbnail_link = thumbnail_link.split('=s')[0] + '=s1000'
            else:
                thumbnail_link += '=s1000'
            return redirect(thumbnail_link)
        
        # 썸네일이 없는 경우 (방금 업로드했거나 지원하지 않는 경우) 폴백
        return redirect(f"https://drive.google.com/thumbnail?id={file_id}&sz=w1000")
    except Exception as e:
        print(f"썸네일 가져오기 오류: {e}")
        return redirect(f"https://drive.google.com/thumbnail?id={file_id}&sz=w1000")

@main_bp.route('/ping')
def ping():
    from utils.time_utils import get_korean_time
    return jsonify({
        'status': 'alive',
        'timestamp': get_korean_time().isoformat(),
        'message': 'Flask SNS is running!'
    })
