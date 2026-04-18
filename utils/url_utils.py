import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, parse_qs
from typing import List, Dict, Optional
import time
import json

class URLPreviewGenerator:
    """URL 미리보기 생성 클래스 (YouTube 특별 지원)"""
    
    def __init__(self, cache_duration: int = 3600):
        self.cache = {}
        self.cache_duration = cache_duration
    
    def extract_urls(self, text: str) -> List[str]:
        """텍스트에서 URL 추출"""
        # HTTP/HTTPS URL 패턴
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        urls = re.findall(url_pattern, text)
        
        # 중복 제거 및 유효성 검증
        valid_urls = []
        for url in urls:
            try:
                parsed = urlparse(url)
                if parsed.netloc and parsed.scheme in ['http', 'https']:
                    valid_urls.append(url)
            except:
                continue
        
        return list(set(valid_urls))  # 중복 제거
    
    def extract_youtube_id(self, url: str) -> Optional[str]:
        """YouTube URL에서 동영상 ID 추출"""
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11})(?:[?&/]|$)',
            r'(?:embed\/)([0-9A-Za-z_-]{11})',
            r'(?:v\/)([0-9A-Za-z_-]{11})',
            r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def get_youtube_data(self, video_id: str) -> Optional[Dict]:
        """YouTube 데이터 추출 (oEmbed API 사용)"""
        try:
            # YouTube oEmbed API 사용
            oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            response = requests.get(oembed_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # 고해상도 썸네일 URL 생성
                thumbnail_urls = [
                    f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",  # 최고 해상도
                    f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",     # 고해상도
                    f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",     # 중간 해상도
                    f"https://img.youtube.com/vi/{video_id}/0.jpg"              # 기본
                ]
                
                # 사용 가능한 썸네일 찾기
                thumbnail_url = None
                for url in thumbnail_urls:
                    try:
                        thumb_response = requests.head(url, timeout=5)
                        if thumb_response.status_code == 200:
                            thumbnail_url = url
                            break
                    except:
                        continue
                
                return {
                    'type': 'youtube',
                    'url': f"https://www.youtube.com/watch?v={video_id}",
                    'video_id': video_id,
                    'title': data.get('title', ''),
                    'author_name': data.get('author_name', ''),
                    'author_url': data.get('author_url', ''),
                    'thumbnail_url': thumbnail_url or f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                    'width': data.get('width', 560),
                    'height': data.get('height', 315),
                    'duration': None,
                    'view_count': None,
                    'site_name': 'YouTube'
                }
        except Exception as e:
            print(f"YouTube 데이터 추출 오류: {e}")
        
        return None
    
    def get_url_preview(self, url: str) -> Optional[Dict]:
        """URL 메타데이터 추출 (YouTube 특별 처리)"""
        # 캐시 확인
        cache_key = url
        if cache_key in self.cache:
            cache_time, cache_data = self.cache[cache_key]
            if time.time() - cache_time < self.cache_duration:
                return cache_data
        
        # YouTube 특별 처리
        youtube_id = self.extract_youtube_id(url)
        if youtube_id:
            youtube_data = self.get_youtube_data(youtube_id)
            if youtube_data:
                self.cache[cache_key] = (time.time(), youtube_data)
                return youtube_data
        
        # 일반 웹사이트 처리
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            preview_data = self._extract_metadata(soup, url)
            
            if preview_data:
                self.cache[cache_key] = (time.time(), preview_data)
                return preview_data
                
        except Exception as e:
            print(f"URL 미리보기 생성 오류 ({url}): {e}")
        
        return None
    
    def _extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict:
        """HTML에서 메타데이터 추출"""
        metadata = {
            'url': url,
            'type': 'website',
            'site_name': self._get_domain_name(url)
        }
        
        # Open Graph 태그
        og_tags = {
            'title': soup.find('meta', property='og:title'),
            'description': soup.find('meta', property='og:description'),
            'image': soup.find('meta', property='og:image'),
            'site_name': soup.find('meta', property='og:site_name')
        }
        
        # 일반 메타 태그
        meta_tags = {
            'title': soup.find('title'),
            'description': soup.find('meta', attrs={'name': 'description'})
        }
        
        # 제목 추출
        if og_tags['title'] and og_tags['title'].get('content'):
            metadata['title'] = og_tags['title']['content']
        elif meta_tags['title']:
            metadata['title'] = meta_tags['title'].get_text().strip()
        else:
            metadata['title'] = self._get_domain_name(url)
        
        # 설명 추출
        if og_tags['description'] and og_tags['description'].get('content'):
            metadata['description'] = og_tags['description']['content']
        elif meta_tags['description'] and meta_tags['description'].get('content'):
            metadata['description'] = meta_tags['description']['content']
        else:
            # 첫 번째 p 태그에서 설명 추출
            first_p = soup.find('p')
            if first_p:
                metadata['description'] = first_p.get_text().strip()[:200] + '...'
            else:
                metadata['description'] = ''
        
        # 이미지 추출
        if og_tags['image'] and og_tags['image'].get('content'):
            metadata['image_url'] = og_tags['image']['content']
        else:
            # 첫 번째 이미지 찾기
            first_img = soup.find('img')
            if first_img and first_img.get('src'):
                img_src = first_img['src']
                if not img_src.startswith('http'):
                    img_src = urljoin(url, img_src)
                metadata['image_url'] = img_src
        
        # 사이트명
        if og_tags['site_name'] and og_tags['site_name'].get('content'):
            metadata['site_name'] = og_tags['site_name']['content']
        
        return metadata
    
    def _get_domain_name(self, url: str) -> str:
        """URL에서 도메인명 추출"""
        try:
            parsed = urlparse(url)
            return parsed.netloc.replace('www.', '')
        except:
            return url
    
    def process_text_with_urls(self, text: str) -> tuple[str, List[Dict]]:
        """텍스트에서 URL을 추출하고 미리보기 생성"""
        urls = self.extract_urls(text)
        url_previews = []
        
        for url in urls:
            preview = self.get_url_preview(url)
            if preview:
                url_previews.append(preview)
        
        return text, url_previews