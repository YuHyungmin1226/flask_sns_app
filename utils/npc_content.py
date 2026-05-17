import random
import json
import requests
from datetime import datetime

# 페르소나별 문장 조각 데이터
PERSONA_DATA = {
    "friendly": {
        "openings": ["안녕하세요! ", "반가워요 여러분, ", "오늘 하루 잘 보내고 계신가요? ", "다들 평안한 하루 되시길 바랄게요. ", "잠시 안부 전하러 왔어요. "],
        "bodies": [
            "맛있는 점심을 먹었더니 기분이 참 좋네요. 😊",
            "요즘 날씨가 변덕스러운데 감기 조심하세요!",
            "좋은 음악을 듣고 있으니 마음이 여유로워지네요.",
            "새로운 취미를 시작해볼까 고민 중인데 추천해주실 만한 게 있을까요?",
            "길을 걷다 예쁜 꽃을 발견해서 기분이 좋아졌어요."
        ],
        "closings": ["행복한 하루 되세요!", "다음에 또 이야기 나눠요. ✨", "오늘도 화이팅입니다!", "모두들 즐거운 시간 보내시길!"]
    },
    "casual": {
        "openings": ["다들 뭐해? ㅋㅋ ", "오랜만! ", "방가방가~ ", "와 오늘 대박이다.. ", "안녕안녕! "],
        "bodies": [
            "오늘 점심 메뉴 대실패함.. ㅠㅠ 맛집 추천 좀 해주라.",
            "진짜 퇴근하고 싶어서 미칠 것 같아! ㅋㅋㅋ",
            "넷플릭스에 새로 올라온 거 봤어? 진짜 존잼임.",
            "주말 순삭 실화냐.. 월요일 오지 마라 제발.",
            "갑자기 떡볶이 땡기는데 같이 먹을 사람?"
        ],
        "closings": ["이따가 또 올게!", "다들 불금 보내라구 🔥", "그럼 이만 뿅!", "나중에 또 봐~"]
    },
    "serious": {
        "openings": ["안녕하십니까. ", "반갑습니다. 인사가 늦었습니다. ", "좋은 소식이 있어 공유드리고자 합니다. ", "삶의 가치에 대해 생각해보게 되는 날입니다. "],
        "bodies": [
            "독서는 마음의 양식이라더니, 최근 읽은 서적이 깊은 울림을 줍니다.",
            "꾸준한 운동은 몸과 마음을 건강하게 만드는 지름길인 것 같습니다.",
            "성실하게 하루를 보낸 스스로에게 작은 보상을 주려 합니다.",
            "함께하는 삶의 소중함을 다시금 깨닫는 요즈음입니다.",
            "전문성을 높이기 위해 매일 조금씩이라도 공부하는 습관을 들이고 있습니다."
        ],
        "closings": ["평안한 시간 되시길 바랍니다.", "이상입니다. 감사합니다.", "오늘도 정진하시길 바랍니다.", "건강 유의하십시오."]
    },
    "emotional": {
        "openings": ["비가 오면 생각이 많아져요.. ", "오늘 노을이 참 예쁘네요. ", "창밖을 보다가 문득.. ", "어디선가 그리운 향기가 나요. "],
        "bodies": [
            "시간이 흐르는 게 가끔은 무겁게 느껴지기도 합니다.",
            "소소한 일상 속에서 나만의 조각을 찾아가는 중이에요.",
            "따뜻한 라떼 한 잔에 담긴 온기가 마음을 녹여주네요. ☕",
            "때로는 멈춰 서서 뒤를 돌아보는 시간도 필요한 것 같아요.",
            "별이 빛나는 밤, 당신의 하루는 어떠셨나요?"
        ],
        "closings": ["부디 따뜻한 밤 되기를..", "마음 깊이 응원합니다.", "소중한 순간들을 기록해보세요.", "내일은 더 빛날 거예요."]
    }
}

# 추임새 (Filler words)
FILLERS = ["아! ", "와~ ", "음.. ", "헉! ", "허허, ", "그나저나 ", "문득 "]

# 키워드 기반 맞춤 리액션
KEYWORD_REACTIONS = {
    "비": ["비 오니까 파전에 막걸리 생각나네요! ☔", "비 소리가 참 좋네요. 다들 우산 챙기셨죠?", "축축하지만 감성적인 날이에요."],
    "커피": ["저도 커피 한 잔 마셔야겠어요! ☕", "커피 향이 여기까지 나는 것 같아요.", "역시 오후엔 카페인 수급이 필요하죠!"],
    "배고파": ["저도 슬슬 배고픈데 뭐 드실 거예요?", "맛있는 거 추천해드릴까요? 😋", "꼬르륵.. 저도요!"],
    "퇴근": ["오늘 하루도 정말 고생 많으셨어요! 🙌", "드디어 퇴근! 즐거운 저녁 보내세요.", "부러워요! 저는 조금 더 있다가 가요."],
    "공부": ["공부 힘드시죠? 화이팅하세요! 📚", "열공하시는 모습이 멋져요!", "잠시 쉬어가는 건 어떨까요?"],
    "운동": ["운동 오운완! 멋지십니다 💪", "저도 운동 시작해야 하는데.. 자극받고 가요!", "체력이 국력이죠! 화이팅!"],
    "여행": ["와, 여행 가고 싶어지네요 ✈️", "사진 보니까 힐링돼요. 조심히 다녀오세요!", "어디인지 정보 좀 주실 수 있나요?"]
}

# 날씨별 감성 템플릿
WEATHER_POSTS = {
    "Rain": ["비가 주룩주룩 오네요. 파전에 막걸리 딱인 날씨! ☔", "빗소리 들으면서 책 읽으니까 너무 좋아요.", "오늘 같이 비 오는 날은 집에서 영화 보는 게 최고죠."],
    "Clear": ["오늘 날씨 실화인가요? 하늘이 너무 맑아요! ☀️", "햇살이 따사로워서 광합성 하러 나왔습니다.", "구름 한 점 없는 파란 하늘, 기분까지 좋아지네요."],
    "Clouds": ["구름이 많아서 흐릿한 날이네요. 그래도 운치 있어요.", "금방이라도 비가 올 것 같은 날씨.. 다들 우산 챙기셨죠?", "흐린 날엔 따뜻한 라떼 한 잔이 생각나요. ☕"],
    "Snow": ["와! 눈이 와요! 세상이 온통 하얗네요 ❄️", "첫눈인가요? 다들 눈 구경하고 계신가요?", "미끄러우니까 길 조심하세요!"]
}

# 경제/금융 RSS 피드
FINANCE_FEEDS = [
    {"name": "증시/금융", "url": "https://www.yonhapnewstv.co.kr/category/news/economy/feed/"}
]

# 일반 뉴스 RSS 피드
RSS_FEEDS = [
    {"name": "IT/과학", "url": "https://www.yonhapnewstv.co.kr/category/news/it/feed/"},
    {"name": "생활/문화", "url": "https://www.yonhapnewstv.co.kr/category/news/culture/feed/"}
]

def generate_sentence(personality='friendly'):
    """페르소나에 맞춰 문장을 조립합니다."""
    data = PERSONA_DATA.get(personality, PERSONA_DATA['friendly'])
    
    opening = random.choice(data['openings'])
    body = random.choice(data['bodies'])
    closing = random.choice(data['closings'])
    
    # 30% 확률로 추임새 추가
    filler = random.choice(FILLERS) if random.random() < 0.3 else ""
    
    return f"{filler}{opening}{body} {closing}"

def get_random_daily_post(personality='friendly'):
    """무작위 일상 글 생성"""
    return generate_sentence(personality)

def get_random_reaction(content="", personality='friendly'):
    """콘텐츠 키워드 분석 및 성격에 따른 무작위 댓글 반환"""
    # 1. 키워드 분석 (Context-aware)
    if content:
        for keyword, reactions in KEYWORD_REACTIONS.items():
            if keyword in content:
                return random.choice(reactions)

    # 2. 일반 리액션 (페르소나 반영)
    data = PERSONA_DATA.get(personality, PERSONA_DATA['friendly'])
    return random.choice(data['closings']) # 짧은 인사말로 대체

def fetch_random_image(keyword="nature"):
    """LoremFlickr를 통한 무작위 이미지 URL 획득"""
    return f"https://loremflickr.com/1200/800/{keyword}"

def fetch_news_rss():
    """RSS 피드에서 최신 뉴스 하나 가져오기"""
    import feedparser
    feed_info = random.choice(RSS_FEEDS)
    try:
        feed = feedparser.parse(feed_info['url'])
        if feed.entries:
            entry = random.choice(feed.entries[:5])
            return {
                "title": entry.title,
                "link": entry.link,
                "summary": entry.summary[:100] + "...",
                "category": feed_info['name']
            }
    except: return None
    return None

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
    """NPC 프로필 및 외부 환경에 따른 게시글 생성"""
    personality = npc_profile.personality or 'friendly'
    
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
            return content, []
            
    if post_type == "image":
        topic = random.choice(json.loads(npc_profile.preferred_topics or '["nature", "food", "travel"]'))
        image_url = fetch_random_image(topic)
        
        if topic in ['food', 'cooking', 'cafe']:
            caption = random.choice(["오늘 정말 맛있게 먹은 메뉴예요! 😋", "취향 저격 맛집/카페 발견! 사진 공유합니다.", "보기만 해도 배부른 비주얼이네요!"])
        elif topic in ['nature', 'travel', 'hiking']:
            caption = random.choice(["오늘 본 멋진 풍경이에요! 웅장하네요. ⛰️", "힐링되는 풍경 사진 한 장 공유합니다.", "가슴이 뻥 뚫리는 시원한 뷰예요!"])
        else:
            caption = "오늘 찍은 사진 한 장 공유합니다! 📸"
            
        return caption + f"\n\n{image_url}", []

    return get_random_daily_post(personality), []
