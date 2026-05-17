import random
import json
from datetime import datetime, timedelta
from extensions import db
from models import User, Post, Comment, NpcProfile, SystemSetting, NpcRelationship, SystemLog
from utils.npc_content import generate_npc_post, get_random_reaction
from utils.time_utils import get_korean_time_for_db
from utils.url_utils import URLPreviewGenerator
from utils.tasks import trigger_db_sync

url_preview_generator = URLPreviewGenerator()

def log_event(message, level='info'):
    """시스템 로그를 DB에 기록합니다."""
    try:
        new_log = SystemLog(message=message, level=level)
        db.session.add(new_log)
        db.session.commit()
    except:
        db.session.rollback()

def get_next_delay(activity_level):
    """활동 지수(1~10)에 따른 다음 활동 대기 시간(분) 계산 (매우 공격적)"""
    # 10일 때 평균 5분, 1일 때 평균 50분
    base_minutes = (11 - activity_level) * 5
    jitter = random.uniform(0.5, 1.5)
    return max(3, int(base_minutes * jitter))

def run_npc_cycle(app):
    """전체 NPC 활동 사이클 실행 (스케줄러 호출)"""
    with app.app_context():
        # NPC 시스템 활성화 여부 확인
        enabled_setting = db.session.get(SystemSetting, 'npc_system_enabled')
        if not enabled_setting or enabled_setting.value != 'True':
            return

        now = get_korean_time_for_db()
        
        # 날씨 데이터
        weather_setting = db.session.get(SystemSetting, 'current_weather')
        weather_data = json.loads(weather_setting.value) if weather_setting else None

        # 모든 NPC 정보 가져오기
        npcs = User.query.join(NpcProfile).filter(User.is_npc == True).all()
        is_sleeping = 2 <= now.hour <= 7

        # 1. 게시글 작성 체크
        for npc in npcs:
            p = npc.npc_profile
            
            # 자가 수정: 예정 시간이 없거나 너무 멀면(2시간 이상) 현재로 초기화
            if not p.next_action_at or p.next_action_at > (now + timedelta(hours=2)):
                p.next_action_at = now

            if p.next_action_at <= now:
                # 취침 시간에는 5% 확률로만 활동
                if is_sleeping and random.random() > 0.05:
                    continue
                    
                try:
                    execute_npc_post(npc, weather_data)
                    log_event(f"[활동] {npc.username}님이 새 게시글을 작성했습니다.")
                except Exception as e:
                    log_event(f"[오류] {npc.username} 게시 중 에러: {str(e)}", 'error')
            else:
                # 대기 중 로그 (너무 자주 찍히지 않게 디버그 용)
                pass

        # 2. 댓글 반응 체크 (최근 15분 이내 글)
        recent_posts = Post.query.filter(Post.created_at >= now - timedelta(minutes=15)).all()
        if recent_posts:
            potential_commenters = User.query.filter(User.is_npc == True).all()
            for post in recent_posts:
                author = User.query.get(post.author_id)
                if not author: continue
                
                for npc in potential_commenters:
                    if npc.id == post.author_id: continue
                    # 이미 댓글 달았는지 확인
                    existing = Comment.query.filter_by(author_id=npc.id, post_id=post.id).first()
                    if existing: continue

                    rel = NpcRelationship.query.filter_by(npc_id=npc.id, target_id=post.author_id).first()
                    affinity = rel.affinity if rel else 0
                    
                    # 반응 확률: 실제 유저 40%, NPC 5% + 친밀도 보너스
                    chance = 0.4 if not author.is_npc else 0.05
                    bonus = min(affinity * 0.01, 0.2)
                    
                    if random.random() < (chance + bonus):
                        try:
                            execute_npc_comment(npc, post)
                            log_event(f"[활동] {npc.username}님이 게시글({post.id})에 댓글을 남겼습니다.")
                        except Exception as e:
                            log_event(f"[오류] {npc.username} 댓글 중 에러: {str(e)}", 'error')

def execute_npc_post(npc, weather_data=None):
    """실제 게시글 작성 및 다음 시간 예약"""
    content, _ = generate_npc_post(npc.npc_profile, weather_data)
    _, previews = url_preview_generator.process_text_with_urls(content)
    
    new_post = Post(
        content=content,
        author_id=npc.id,
        is_public=True,
        url_previews=json.dumps(previews, ensure_ascii=False)
    )
    db.session.add(new_post)
    
    # 다음 활동 시간 예약
    delay = get_next_delay(npc.npc_profile.activity_level)
    npc.npc_profile.last_post_at = get_korean_time_for_db()
    npc.npc_profile.next_action_at = get_korean_time_for_db() + timedelta(minutes=delay)
    
    db.session.commit()
    trigger_db_sync() 
    print(f"[NPC Activity] {npc.username} posted. Next in {delay}m.")

def execute_npc_comment(npc, post):
    """무작위 댓글 작성 및 친밀도 상승"""
    reaction = get_random_reaction(post.content, npc.npc_profile.personality)
    new_comment = Comment(content=reaction, author_id=npc.id, post_id=post.id)
    db.session.add(new_comment)
    
    # 친밀도 상승
    rel = NpcRelationship.query.filter_by(npc_id=npc.id, target_id=post.author_id).first()
    if not rel:
        rel = NpcRelationship(npc_id=npc.id, target_id=post.author_id, affinity=0)
        db.session.add(rel)
    rel.affinity += 5
    rel.last_interaction = get_korean_time_for_db()
    
    npc.npc_profile.last_comment_at = get_korean_time_for_db()
    db.session.commit()
    trigger_db_sync()
    print(f"[NPC Activity] {npc.username} commented on post {post.id}.")

def init_npcs():
    """기본 NPC 계정들 생성 및 초기화"""
    npc_data = [
        {"username": "daily_life", "personality": "friendly", "topics": '["daily", "food"]'},
        {"username": "news_bot", "personality": "serious", "topics": '["it", "science", "news"]'},
        {"username": "nature_lover", "personality": "peaceful", "topics": '["nature", "travel", "hiking"]'},
        {"username": "foodie_bot", "personality": "witty", "topics": '["food", "cooking", "cafe"]'}
    ]
    
    from werkzeug.security import generate_password_hash
    import os

    for data in npc_data:
        user = User.query.filter_by(username=data['username']).first()
        if not user:
            user = User(
                username=data['username'],
                password_hash=generate_password_hash(os.environ.get('ADMIN_PASSWORD', 'admin123')),
                is_approved=True,
                is_npc=True
            )
            db.session.add(user)
            db.session.flush()
            
            profile = NpcProfile(
                user_id=user.id,
                personality=data['personality'],
                preferred_topics=data['topics'],
                next_action_at=get_korean_time_for_db()
            )
            db.session.add(profile)
    
    db.session.commit()
    
    if not db.session.get(SystemSetting, 'npc_system_enabled'):
        db.session.add(SystemSetting(key='npc_system_enabled', value='True'))
        db.session.commit()
    
    log_event("NPC 시스템이 초기화되었습니다.")
