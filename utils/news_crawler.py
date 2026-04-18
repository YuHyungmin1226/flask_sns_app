import feedparser
import json

def fetch_and_post_news(app, db, Post, SystemSetting, User):
    """
    구글 뉴스 RSS를 크롤링하고 중복 검사 후 새로운 기사만 어드민 계정으로 포스팅합니다.
    순환 참조를 피하기 위해 app, db 및 모델들을 인자로 받습니다.
    """
    with app.app_context():
        # 1. 봇 활성화 상태 확인
        setting = SystemSetting.query.get('news_bot_enabled')
        if not setting or setting.value != 'True':
            print("[News_Bot] 스위치가 OFF 상태이거나 설정이 없습니다. 크롤링을 건너뜁니다.")
            return
            
        print("[News_Bot] 구글 뉴스 크롤링을 시작합니다...")
        feed_url = 'https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko'
        
        try:
            feed = feedparser.parse(feed_url)
        except Exception as e:
            print(f"[News_Bot] 피드 파싱 오류: {e}")
            return
            
        if not feed.entries:
            print("[News_Bot] 피드에서 기사를 찾을 수 없습니다.")
            return
            
        # 상위 20개 기사 추출
        entries = feed.entries[:20]
        
        # 2. 이전 포스팅 캐시(URL 기록) 불러오기
        history_setting = SystemSetting.query.get('last_posted_news')
        history_urls = set()
        if history_setting and history_setting.value:
            try:
                history_urls = set(json.loads(history_setting.value))
            except Exception as e:
                print(f"[News_Bot] 캐시 역직렬화 오류: {e}")
                
        # 3. 새로운 기사 필터링 (중복 방지)
        new_articles = []
        for entry in entries:
            link = getattr(entry, 'link', '')
            if link and link not in history_urls:
                new_articles.append(entry)
                
        # 4. 스킵 조건: 새 기사가 없으면 빈 게시물 스킵
        if not new_articles:
            print("[News_Bot] 새로운 기사가 없습니다. 포스팅을 건너뜁니다 (Skip).")
            return
            
        # 5. 본문 내용 작성 (마크다운 제거 - 평문 및 URL 직접 노출)
        content = f"📰 [Google News 최신 큐레이션 - {len(new_articles)}건]\n\n"
        for article in new_articles:
            title = getattr(article, 'title', '제목 없음')
            link = getattr(article, 'link', '#')
            content += f"• {title}\n  주소: {link}\n\n"
        
        content += "전체 뉴스는 Google News에서 확인하실 수 있습니다."
            
        # 6. 관리자 계정 조회
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("[News_Bot] 'admin' 계정을 찾을 수 없어 봇 구동에 실패했습니다.")
            return
            
        # 7. 포스트 생성 및 저장
        new_post = Post(
            content=content, 
            author_id=admin.id, 
            is_public=True
        )
        db.session.add(new_post)
        
        # 8. 이력 캐시 업데이트 (최근 100개까지만 유지하여 메모리/DB 절약)
        current_urls = [getattr(e, 'link', '') for e in entries]
        updated_history = list(set(list(history_urls) + current_urls))[-100:]
        
        if history_setting:
            history_setting.value = json.dumps(updated_history)
        else:
            db.session.add(SystemSetting(key='last_posted_news', value=json.dumps(updated_history)))
            
        try:
            db.session.commit()
            print(f"[News_Bot] 성공! {len(new_articles)}개의 새로운 뉴스를 포스팅했습니다.")
        except Exception as e:
            db.session.rollback()
            print(f"[News_Bot] DB 저장 중 오류 발생: {e}")
