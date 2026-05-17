import random
import json
import requests
from datetime import datetime

# 일상 대화 템플릿 (비용 0원 로컬 데이터)
DAILY_POSTS = [
    "오늘 점심은 뭐 먹지? 고민되네.. 😋",
    "날씨가 너무 좋아서 산책 나왔어요. 기분이 상쾌하네요!",
    "요즘 읽고 있는 책이 너무 재미있어서 시간 가는 줄 모르겠어요. 📚",
    "커피 한 잔의 여유... 이게 바로 행복이죠. ☕",
    "갑자기 비가 오네요? 다들 우산 챙기셨나요?",
    "운동 끝나고 마시는 시원한 물 한 잔! 최고예요. 💪",
    "오늘 하늘이 유난히 파랗고 예쁘네요. 사진 한 장 찍어봤어요.",
    "월요일이라 조금 피곤하지만, 다들 이번 주도 화이팅해요! 🙌",
    "좋은 음악을 들으며 퇴근하는 길, 오늘 하루도 수고 많으셨습니다.",
    "드디어 기다리던 주말이 왔네요! 다들 뭐 하실 계획인가요?",
    "새로 생긴 카페에 왔는데 인테리어가 너무 제 취향이에요. ✨",
    "넷플릭스에서 재미있는 영화 추천해주세요! 볼 게 없네요.",
    "직접 만든 파스타! 생각보다 맛있어서 놀랐어요. 🍝",
    "밤공기가 참 차분하고 좋네요. 잠이 잘 올 것 같아요. 🌙",
    "오늘 하루는 정말 바빴지만 보람차네요."
]

# 댓글 리액션 템플릿
REACTIONS = {
    "positive": [
        "와, 정말 좋네요! 👍",
        "공감합니다. 저도 그렇게 생각해요.",
        "사진 너무 예뻐요! 어디인가요?",
        "우와, 대단하시네요! 부러워요. 😊",
        "좋은 정보 감사합니다!",
        "오늘도 즐거운 하루 보내세요!",
        "멋져요! 저도 한번 해보고 싶네요."
    ],
    "neutral": [
        "그렇군요!",
        "오호, 신기하네요.",
        "잘 보고 갑니다.",
        "좋은 하루 되세요~",
        "공유해주셔서 감사합니다."
    ],
    "question": [
        "오, 진짜요? 더 자세히 알려주실 수 있나요?",
        "그거 어디서 사셨어요? 정보 좀 주세요! 🙏",
        "어떤 점이 좋았는지 궁금해요!",
        "추천하시는 이유가 있나요?"
    ]
}

# 뉴스 RSS 피드 목록 (무료)
RSS_FEEDS = [
    {"name": "IT/과학", "url": "https://www.yonhapnewstv.co.kr/category/news/it/feed/"},
    {"name": "생활/문화", "url": "https://www.yonhapnewstv.co.kr/category/news/culture/feed/"}
]

# 키워드 기반 맞춤 리액션 (비용 0원)
KEYWORD_REACTIONS = {
    "비": ["비 오니까 파전에 막걸리 생각나네요! ☔", "비 소리가 참 좋네요. 다들 우산 챙기셨죠?", "축축하지만 감성적인 날이에요."],
    "커피": ["저도 커피 한 잔 마셔야겠어요! ☕", "커피 향이 여기까지 나는 것 같아요.", "역시 오후엔 카페인 수급이 필요하죠!"],
    "배고파": ["저도 슬슬 배고픈데 뭐 드실 거예요?", "맛있는 거 추천해드릴까요? 😋", "꼬르륵.. 저도요!"],
    "퇴근": ["오늘 하루도 정말 고생 많으셨어요! 🙌", "드디어 퇴근! 즐거운 저녁 보내세요.", "부러워요! 저는 조금 더 있다가 가요."],
    "공부": ["공부 힘드시죠? 화이팅하세요! 📚", "열공하시는 모습이 멋져요!", "잠시 쉬어가는 건 어떨까요?"],
    "운동": ["운동 오운완! 멋지십니다 💪", "저도 운동 시작해야 하는데.. 자극받고 가요!", "체력이 국력이죠! 화이팅!"],
    "여행": ["와, 여행 가고 싶어지네요 ✈️", "사진 보니까 힐링돼요. 조심히 다녀오세요!", "어디인지 정보 좀 주실 수 있나요?"]
}

# 시간대별 특화 게시글
TIME_BASED_POSTS = {
    "morning": ["좋은 아침이에요! 다들 오늘 하루도 힘차게 시작해봐요 ☀️", "아침 공기가 상쾌하네요. 기분 좋은 하루 되세요!", "벌써 아침이라니.. 졸리지만 화이팅!"],
    "lunch": ["슬슬 배고파지네요. 다들 점심 메뉴 정하셨나요? 🍱", "맛점하세요! 저는 오늘 제육볶음 먹으려구요.", "점심 먹고 나른한 오후네요. 커피 한 잔 어떠세요?"],
    "evening": ["오늘 하루도 수고 많으셨습니다. 편안한 저녁 되세요 🌙", "저녁 노을이 예쁘네요. 다들 맛있는 거 드세요!", "드디어 퇴근! 오늘 하루 어떠셨나요?"],
    "night": ["밤이 깊었네요. 다들 좋은 꿈 꾸세요 ✨", "조용한 밤공기가 참 좋네요. 잠이 잘 올 것 같아요.", "아직 안 주무시는 분 계신가요? 저는 이제 자러 갑니다."]
}

def get_random_daily_post():
    """무작위 일상 글 반환 (시간대 고려)"""
    now = datetime.now()
    if 6 <= now.hour < 11:
        pool = DAILY_POSTS + TIME_BASED_POSTS["morning"]
    elif 11 <= now.hour < 14:
        pool = DAILY_POSTS + TIME_BASED_POSTS["lunch"]
    elif 17 <= now.hour < 21:
        pool = DAILY_POSTS + TIME_BASED_POSTS["evening"]
    elif 21 <= now.hour <= 23 or 0 <= now.hour < 2:
        pool = DAILY_POSTS + TIME_BASED_POSTS["night"]
    else:
        pool = DAILY_POSTS
    
    return random.choice(pool)

def get_random_reaction(content="", personality='friendly'):
    """콘텐츠 키워드 분석 및 성격에 따른 무작위 댓글 반환"""
    # 1. 키워드 분석 (Context-aware)
    if content:
        for keyword, reactions in KEYWORD_REACTIONS.items():
            if keyword in content:
                return random.choice(reactions)

    # 2. 일반 리액션 (Fallback)
    category = random.choice(["positive", "positive", "neutral", "question"])
    return random.choice(REACTIONS[category])

def fetch_random_image(keyword="nature"):
    """Unsplash 무료 API를 통한 이미지 URL 획득 (API Key 없이도 기본 제공되는 랜덤 이미지 활용)"""
    # Source Unsplash는 키 없이도 특정 키워드의 랜덤 이미지를 제공함
    return f"https://source.unsplash.com/random/1200x800/?{keyword}"

def fetch_news_rss():
    """RSS 피드에서 최신 뉴스 하나 가져오기 (비용 0원)"""
    import feedparser
    feed_info = random.choice(RSS_FEEDS)
    try:
        feed = feedparser.parse(feed_info['url'])
        if feed.entries:
            entry = random.choice(feed.entries[:5]) # 최신 5개 중 랜덤
            return {
                "title": entry.title,
                "link": entry.link,
                "summary": entry.summary[:100] + "...",
                "category": feed_info['name']
            }
    except Exception as e:
        print(f"RSS Fetch Error: {e}")
    return None
# 금융/경제 RSS
FINANCE_FEEDS = [
    {"name": "증시/금융", "url": "https://www.yonhapnewstv.co.kr/category/news/economy/feed/"}
]

# 날씨별 감성 템플릿
WEATHER_POSTS = {
    "Rain": ["비가 주룩주룩 오네요. 파전에 막걸리 딱인 날씨! ☔", "빗소리 들으면서 책 읽으니까 너무 좋아요.", "오늘 같이 비 오는 날은 집에서 영화 보는 게 최고죠."],
    "Clear": ["오늘 날씨 실화인가요? 하늘이 너무 맑아요! ☀️", "햇살이 따사로워서 광합성 하러 나왔습니다.", "구름 한 점 없는 파란 하늘, 기분까지 좋아지네요."],
    "Clouds": ["구름이 많아서 흐릿한 날이네요. 그래도 운치 있어요.", "금방이라도 비가 올 것 같은 날씨.. 다들 우산 챙기셨죠?", "흐린 날엔 따뜻한 라떼 한 잔이 생각나요. ☕"],
    "Snow": ["와! 눈이 와요! 세상이 온통 하얗네요 ❄️", "첫눈인가요? 다들 눈 구경하고 계신가요?", "미끄러우니까 길 조심하세요!"]
}

def fetch_finance_rss():
    """경제 뉴스 가져오기"""
    import feedparser
    try:
        feed = feedparser.parse(FINANCE_FEEDS[0]['url'])
        if feed.entries:
            entry = random.choice(feed.entries[:3])
            return f"[경제 브리핑] {entry.title}\n\n최근 경제 동향 공유합니다. 다들 참고하세요! 📈\n\n상세보기: {entry.link}"
    except: return None
    return None

def generate_npc_post(npc_profile, weather_data=None):
    """NPC 프로필 및 외부 환경(날씨 등)에 따른 게시글 생성 로직"""
    # 1. 날씨 기반 포스팅 (확률적)
    if weather_data and random.random() < 0.3:
        main_weather = weather_data.get('weather', [{}])[0].get('main', 'Clear')
        if main_weather in WEATHER_POSTS:
            return random.choice(WEATHER_POSTS[main_weather]), []

    # 2. 유형 결정
    post_type = random.choices(["daily", "news", "image", "finance"], weights=[50, 20, 20, 10])[0]

    if post_type == "finance":
        content = fetch_finance_rss()
        if content: return content, []

    if post_type == "news":
        news = fetch_news_rss()
        if news:
            content = f"[{news['category']}] {news['title']}\n\n{news['summary']}\n\n상세보기: {news['link']}"
            return content, [] # URL previews will handle the link
            
    if post_type == "image":
        topic = random.choice(json.loads(npc_profile.preferred_topics or '["nature", "food", "travel"]'))
        image_url = fetch_random_image(topic)
        
        # 주제에 맞는 문구 선택
        if topic in ['food', 'cooking', 'cafe']:
            caption = random.choice(["오늘 정말 맛있게 먹은 메뉴예요! 😋", "취향 저격 맛집/카페 발견! 사진 공유합니다.", "보기만 해도 배부른 비주얼이네요!"])
        elif topic in ['nature', 'travel', 'hiking']:
            caption = random.choice(["오늘 본 멋진 풍경이에요! 웅장하네요. ⛰️", "힐링되는 풍경 사진 한 장 공유합니다.", "가슴이 뻥 뚫리는 시원한 뷰예요!"])
        else:
            caption = "오늘 찍은 사진 한 장 공유합니다! 📸"
            
        return caption + f"\n\n{image_url}", []

    return get_random_daily_post(), []
