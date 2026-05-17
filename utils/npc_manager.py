import random
import json
from datetime import datetime, timedelta
from extensions import db
from models import User, Post, Comment, NpcProfile, SystemSetting, NpcRelationship
from utils.npc_content import generate_npc_post, get_random_reaction
from utils.time_utils import get_korean_time_for_db
from utils.url_utils import URLPreviewGenerator # 수정된 임포트
from utils.tasks import trigger_db_sync # DB 동기화 임포트

url_preview_generator = URLPreviewGenerator()

def get_next_delay(activity_level):
    """활동 지수에 따른 다음 활동 대기 시간(분) 계산 (최적화)"""
    # 활동 지수 1~10에 따라 대기 시간을 대폭 단축 (생동감 부여)
    # 10일 때 평균 40분, 1일 때 평균 400분(약 6시간) 대기하도록 설정
    base_minutes = (11 - activity_level) * 40
    jitter = random.uniform(0.5, 1.5)
    return max(10, int(base_minutes * jitter)) # 최소 10분은 대기

def run_npc_cycle(app):
    """전체 NPC 활동 사이클 실행 (스케줄러에 의해 호출됨)"""
    with app.app_context():
        # NPC 시스템 활성화 여부 확인
        enabled_setting = SystemSetting.query.get('npc_system_enabled')
        if not enabled_setting or enabled_setting.value != 'True':
            return

        now = get_korean_time_for_db()
        print(f"[NPC Heartbeat] Cycle started at {now}")
        
        # 날씨 데이터 가져오기 (메모리 반영용)
        weather_setting = SystemSetting.query.get('current_weather')
        weather_data = json.loads(weather_setting.value) if weather_setting else None

        # 1. 취침 시간 확인 (02시~07시 사이엔 활동 확률 극감)
        if 2 <= now.hour <= 7:
            if random.random() > 0.05: # 5% 확률로만 활동
                print("[NPC Heartbeat] Silent night... (sleeping)")
                return

        # 2. 활동 예정 시간이 된 NPC 찾기 (게시글 작성)
        # NpcProfile.next_action_at이 None이거나 현재 시간 이전인 경우
        npcs_to_post = User.query.join(NpcProfile).filter(
            User.is_npc == True,
            (NpcProfile.next_action_at == None) | (NpcProfile.next_action_at <= now)
        ).all()

        if npcs_to_post:
            print(f"[NPC Heartbeat] {len(npcs_to_post)} NPCs are ready to post.")
            for npc in npcs_to_post:
                try:
                    execute_npc_post(npc, weather_data)
                except Exception as e:
                    print(f"NPC Post Error ({npc.username}): {e}")
        else:
            print("[NPC Heartbeat] No NPCs are scheduled to post yet.")

        # 3. 새로운 게시글에 대한 무작위 댓글 반응
        # 최근 15분 이내의 글 조회 (너무 길면 부하 발생)
        recent_posts = Post.query.filter(
            Post.created_at >= now - timedelta(minutes=15)
        ).all()
        
        if recent_posts:
            # 쿼리 최적화: NPC 목록 및 작성자 정보 미리 로드
            potential_commenters = User.query.filter(User.is_npc == True).all()
            author_ids = list(set([p.author_id for p in recent_posts]))
            authors = {u.id: u for u in User.query.filter(User.id.in_(author_ids)).all()}
            
            for post in recent_posts:
                author = authors.get(post.author_id)
                if not author: continue
                
                for npc in potential_commenters:
                    if npc.id == post.author_id: continue
                    
                    # 이미 댓글 달았는지 확인
                    existing = Comment.query.filter_by(author_id=npc.id, post_id=post.id).first()
                    if existing: continue

                    # 친밀도 점수 가져오기
                    rel = NpcRelationship.query.filter_by(npc_id=npc.id, target_id=post.author_id).first()
                    affinity = rel.affinity if rel else 0
                    
                    # 반응 확률 (유저 글은 40%, NPC 글은 5% + 친밀도 보너스)
                    base_chance = 0.4 if not author.is_npc else 0.05
                    bonus_chance = min(affinity * 0.01, 0.2)
                    
                    if random.random() < (base_chance + bonus_chance):
                        execute_npc_comment(npc, post)

def execute_npc_post(npc, weather_data=None):
    """실제 게시글 작성 및 다음 시간 예약"""
    content, files = generate_npc_post(npc.npc_profile, weather_data)
    
    # URL 미리보기 추출
    _, previews = url_preview_generator.process_text_with_urls(content)
    
    new_post = Post(
        content=content,
        author_id=npc.id,
        is_public=True,
        url_previews=json.dumps(previews, ensure_ascii=False)
    )
    db.session.add(new_post)
    
    # 메모리 업데이트 (최근 활동 저장)
    mem = json.loads(npc.npc_profile.memory or '{}')
    mem['last_post_type'] = 'daily' 
    npc.npc_profile.memory = json.dumps(mem)
    
    # 다음 활동 시간 예약
    delay = get_next_delay(npc.npc_profile.activity_level)
    npc.npc_profile.last_post_at = get_korean_time_for_db()
    npc.npc_profile.next_action_at = get_korean_time_for_db() + timedelta(minutes=delay)
    
    db.session.commit()
    trigger_db_sync() # 동기화 강제 트리거
    print(f"[NPC Activity] {npc.username} posted. Next action in {delay} mins.")

def execute_npc_comment(npc, post):
    """무작위 지연 후 댓글 작성 시뮬레이션"""
    reaction = get_random_reaction(post.content, npc.npc_profile.personality)
    
    new_comment = Comment(
        content=reaction,
        author_id=npc.id,
        post_id=post.id
    )
    db.session.add(new_comment)
    npc.npc_profile.last_comment_at = get_korean_time_for_db()
    
    # 친밀도 상승 로직
    rel = NpcRelationship.query.filter_by(npc_id=npc.id, target_id=post.author_id).first()
    if not rel:
        rel = NpcRelationship(npc_id=npc.id, target_id=post.author_id, affinity=0)
        db.session.add(rel)
    rel.affinity += 5
    rel.last_interaction = get_korean_time_for_db()
    
    db.session.commit()
    trigger_db_sync() # 동기화 강제 트리거
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
                next_action_at=get_korean_time_for_db() + timedelta(minutes=random.randint(5, 60))
            )
            db.session.add(profile)
    
    db.session.commit()
    
    # NPC 시스템 설정 초기화
    if not SystemSetting.query.get('npc_system_enabled'):
        db.session.add(SystemSetting(key='npc_system_enabled', value='True'))
        db.session.commit()
        
    print("[NPC Init] Basic NPC accounts and settings have been initialized.")
