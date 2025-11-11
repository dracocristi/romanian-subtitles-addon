from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, quote
import time
from typing import List, Dict, Optional

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Create the main app
app = FastAPI()

# Stremio Addon Manifest
MANIFEST = {
    "id": "ro.subtitles.romanian",
    "version": "1.0.0",
    "name": "Romanian Subtitles",
    "description": "Comprehensive Romanian subtitle addon supporting subtitrari.ro, subs.ro, and titrari.ro",
    "logo": "https://www.stremio.com/website/stremio-logo-small.png",
    "resources": ["subtitles"],
    "types": ["movie", "series"],
    "idPrefixes": ["tt"],
    "catalogs": [],
    "behaviorHints": {
        "configurable": False,
        "configurationRequired": False
    }
}

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# User agent for requests
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

class SubtitleScraper:
    """Base class for subtitle scrapers"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
    
    def search(self, imdb_id: str, type: str, season: Optional[int] = None, episode: Optional[int] = None) -> List[Dict]:
        """Search for subtitles - to be implemented by subclasses"""
        raise NotImplementedError

class SubtitrariRoScraper(SubtitleScraper):
    """Scraper for subtitrari.ro"""
    
    BASE_URL = "https://www.subtitrari.ro"
    
    def search(self, imdb_id: str, type: str, season: Optional[int] = None, episode: Optional[int] = None) -> List[Dict]:
        subtitles = []
        try:
            # Search by IMDB ID
            search_url = f"{self.BASE_URL}/index.php?page=cauta&z7={imdb_id}"
            
            logger.info(f"Searching subtitrari.ro with URL: {search_url}")
            response = self.session.get(search_url, timeout=10)
            
            if response.status_code != 200:
                logger.warning(f"subtitrari.ro returned status {response.status_code}")
                return subtitles
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find subtitle entries
            results = soup.find_all('div', class_='title') or soup.find_all('a', href=re.compile(r'subtitrare'))
            
            for idx, result in enumerate(results[:10]):  # Limit to 10 results
                try:
                    if result.name == 'a':
                        link = result.get('href', '')
                        title = result.get_text(strip=True)
                    else:
                        link_tag = result.find('a')
                        if not link_tag:
                            continue
                        link = link_tag.get('href', '')
                        title = link_tag.get_text(strip=True)
                    
                    if not link or not title:
                        continue
                    
                    # Make absolute URL
                    if not link.startswith('http'):
                        link = urljoin(self.BASE_URL, link)
                    
                    # Extract subtitle ID from URL
                    sub_id = f"subtitrari_{idx}_{imdb_id}"
                    
                    subtitles.append({
                        "id": sub_id,
                        "url": link,
                        "lang": "rum",  # Romanian language code
                        "title": f"[subtitrari.ro] {title}"
                    })
                    
                except Exception as e:
                    logger.error(f"Error parsing subtitle entry: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error scraping subtitrari.ro: {e}")
        
        return subtitles

class SubsRoScraper(SubtitleScraper):
    """Scraper for subs.ro"""
    
    BASE_URL = "https://www.subs.ro"
    
    def search(self, imdb_id: str, type: str, season: Optional[int] = None, episode: Optional[int] = None) -> List[Dict]:
        subtitles = []
        try:
            # Search by IMDB ID
            search_url = f"{self.BASE_URL}/search.php?q={imdb_id}"
            
            logger.info(f"Searching subs.ro with URL: {search_url}")
            response = self.session.get(search_url, timeout=10)
            
            if response.status_code != 200:
                logger.warning(f"subs.ro returned status {response.status_code}")
                return subtitles
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find subtitle entries
            results = soup.find_all('a', href=re.compile(r'subtitrare|subtitle')) or soup.find_all('div', class_=re.compile(r'subtitle|result'))
            
            for idx, result in enumerate(results[:10]):
                try:
                    if result.name == 'a':
                        link = result.get('href', '')
                        title = result.get_text(strip=True)
                    else:
                        link_tag = result.find('a')
                        if not link_tag:
                            continue
                        link = link_tag.get('href', '')
                        title = link_tag.get_text(strip=True)
                    
                    if not link or not title:
                        continue
                    
                    # Make absolute URL
                    if not link.startswith('http'):
                        link = urljoin(self.BASE_URL, link)
                    
                    sub_id = f"subsro_{idx}_{imdb_id}"
                    
                    subtitles.append({
                        "id": sub_id,
                        "url": link,
                        "lang": "rum",
                        "title": f"[subs.ro] {title}"
                    })
                    
                except Exception as e:
                    logger.error(f"Error parsing subtitle entry: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error scraping subs.ro: {e}")
        
        return subtitles

class TitrariRoScraper(SubtitleScraper):
    """Scraper for titrari.ro"""
    
    BASE_URL = "https://www.titrari.ro"
    
    def search(self, imdb_id: str, type: str, season: Optional[int] = None, episode: Optional[int] = None) -> List[Dict]:
        subtitles = []
        try:
            # Search by IMDB ID
            search_url = f"{self.BASE_URL}/index.php?page=cauta&z7={imdb_id}"
            
            logger.info(f"Searching titrari.ro with URL: {search_url}")
            response = self.session.get(search_url, timeout=10)
            
            if response.status_code != 200:
                logger.warning(f"titrari.ro returned status {response.status_code}")
                return subtitles
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find subtitle entries
            results = soup.find_all('a', href=re.compile(r'subtitrare|id=')) or soup.find_all('div', class_='title')
            
            for idx, result in enumerate(results[:10]):
                try:
                    if result.name == 'a':
                        link = result.get('href', '')
                        title = result.get_text(strip=True)
                    else:
                        link_tag = result.find('a')
                        if not link_tag:
                            continue
                        link = link_tag.get('href', '')
                        title = link_tag.get_text(strip=True)
                    
                    if not link or not title:
                        continue
                    
                    # Make absolute URL
                    if not link.startswith('http'):
                        link = urljoin(self.BASE_URL, link)
                    
                    sub_id = f"titrari_{idx}_{imdb_id}"
                    
                    subtitles.append({
                        "id": sub_id,
                        "url": link,
                        "lang": "rum",
                        "title": f"[titrari.ro] {title}"
                    })
                    
                except Exception as e:
                    logger.error(f"Error parsing subtitle entry: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error scraping titrari.ro: {e}")
        
        return subtitles

# Initialize scrapers
scrapers = [
    SubtitrariRoScraper(),
    SubsRoScraper(),
    TitrariRoScraper()
]

@app.get("/")
async def root():
    return {"message": "Romanian Subtitles Stremio Addon", "version": MANIFEST["version"]}

@app.get("/manifest.json")
async def get_manifest():
    """Return the addon manifest"""
    return JSONResponse(content=MANIFEST)

@app.get("/subtitles/{type}/{id}.json")
async def get_subtitles(type: str, id: str):
    """
    Get subtitles for a video
    
    Args:
        type: Content type (movie or series)
        id: IMDB ID with optional season/episode (e.g., tt1234567 or tt1234567:1:5)
    """
    logger.info(f"Subtitle request - Type: {type}, ID: {id}")
    
    # Parse ID to extract IMDB ID and optional season/episode
    parts = id.split(':')
    imdb_id = parts[0]
    season = int(parts[1]) if len(parts) > 1 else None
    episode = int(parts[2]) if len(parts) > 2 else None
    
    # Validate IMDB ID format
    if not imdb_id.startswith('tt'):
        raise HTTPException(status_code=400, detail="Invalid IMDB ID format")
    
    all_subtitles = []
    
    # Search all platforms
    for scraper in scrapers:
        try:
            subs = scraper.search(imdb_id, type, season, episode)
            all_subtitles.extend(subs)
            # Add delay to avoid rate limiting
            time.sleep(0.5)
        except Exception as e:
            logger.error(f"Error with scraper {scraper.__class__.__name__}: {e}")
            continue
    
    logger.info(f"Found {len(all_subtitles)} subtitles for {imdb_id}")
    
    return JSONResponse(content={"subtitles": all_subtitles})

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "addon": "Romanian Subtitles"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)