import requests
from datetime import datetime
import pytz

def fetch_and_post_weather(app, db, Post, SystemSetting, User):
    """
    wttr.in 서비스를 활용하여 서울 기준 매일 아침 날씨를 크롤링하고
    관리자 계정으로 포스팅합니다.
    """
    with app.app_context():
        # 1. 스위치 상태 확인
        setting = SystemSetting.query.get('weather_bot_enabled')
        if not setting or setting.value != 'True':
            print("[Weather_Bot] 스위치가 OFF 상태입니다. 날씨 봇 구동을 건너뜁니다.")
            return
            
        print("[Weather_Bot] 오늘의 날씨 정보를 수집합니다...")
        
        try:
            # 타임아웃 10초, 한국어 결과 플래그
            r = requests.get('https://wttr.in/Seoul?format=j1&lang=ko', timeout=10)
            r.encoding = 'utf-8'  # 응답 인코딩을 명시적으로 UTF-8로 지정 (한글 깨짐 방지)
            data = r.json()
            
            # 데이터 추출
            current = data['current_condition'][0]
            weather_desc = current['weatherDesc'][0]['value']
            # lang_ko 데이터가 존재하면 우선 사용
            if 'lang_ko' in current and len(current['lang_ko']) > 0:
                weather_desc = current['lang_ko'][0]['value']
                
            temp = current['temp_C']
            feels_like = current['FeelsLikeC']
            humidity = current['humidity']
            
            # 오늘 일기 예보
            today = data['weather'][0]
            max_temp = today['maxtempC']
            min_temp = today['mintempC']
            # 아치 6시 기준 강수 확률 추출
            chance_of_rain = "0"
            for hourly in today['hourly']:
                if hourly['time'] == "600":
                    chance_of_rain = hourly['chanceofrain']
                    break
            
            # 이모지 자동 매핑 필터 (키워드 기반 간단 매핑)
            desc_lower = weather_desc.lower()
            icon = "☁️"
            if "clear" in desc_lower or "맑음" in desc_lower:
                icon = "☀️"
            elif "rain" in desc_lower or "비" in desc_lower or "showers" in desc_lower:
                icon = "🌧️"
            elif "snow" in desc_lower or "눈" in desc_lower:
                icon = "❄️"
            elif "cloudy" in desc_lower or "흐림" in desc_lower or "구름" in desc_lower or "overcast" in desc_lower:
                icon = "☁️"
            elif "partly" in desc_lower or "구름조금" in desc_lower:
                icon = "⛅"
            else:
                icon = "🌤️"
            
            kst = pytz.timezone('Asia/Seoul')
            date_str = datetime.now(kst).strftime('%Y년 %m월 %d일')
            
            # 본문 평문 조합 (마크다운 제거)
            content = f"[{date_str}] 오늘의 아침 날씨 (서울)\n\n"
            content += f"• 상태: {icon} {weather_desc}\n"
            content += f"• 현재 기온: {temp}℃ (체감 {feels_like}℃)\n"
            content += f"• 최저 / 최고: {min_temp}℃ / {max_temp}℃\n"
            content += f"• 강수 확률: {chance_of_rain}% (오전 기준)\n"
            content += f"• 습도: {humidity}%\n\n"
            content += "오늘도 활기찬 하루 보내시길 바랍니다! ☕"
            
            admin = User.query.filter_by(username='admin').first()
            if not admin:
                print("[Weather_Bot] 'admin' 계정을 찾을 수 없습니다.")
                return
                
            new_post = Post(content=content, author_id=admin.id, is_public=True)
            db.session.add(new_post)
            db.session.commit()
            
            print(f"[Weather_Bot] 날씨 브리핑이 성공적으로 등록되었습니다.")
            
        except Exception as e:
            print(f"[Weather_Bot] 날씨 데이터를 가져오거나 포스팅 중 오류 발생: {e}")
