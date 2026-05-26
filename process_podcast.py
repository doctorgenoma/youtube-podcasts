import os
import json
import yt_dlp
from datetime import datetime

REPO_NAME = os.environ.get('GITHUB_REPOSITORY', 'tu-usuario/tu-repositorio')
RELEASE_URL_TEMPLATE = f"https://github.com/{REPO_NAME}/releases/download/episodes/{{video_id}}.mp3"

def load_data():
    if os.path.exists('podcast_data.json'):
        try:
            with open('podcast_data.json', 'r', encoding='utf-8') as f:
                content = f.read().strip()
                return json.loads(content) if content else []
        except Exception:
            return []
    return []

def save_data(data):
    with open('podcast_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_urls():
    if not os.path.exists('urls.txt'):
        return []
    with open('urls.txt', 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

def clean_video_id(url):
    if 'watch?v=' in url:
        return url.split('v=')[1].split('&')[0]
    elif 'youtu.be/' in url:
        return url.split('youtu.be/')[1].split('?')[0]
    return None

def download_and_metadata(video_url):
    # PARÁMETROS DE CAMUFLAJE EXTREMO
    ydl_opts = {
        'format': 'ba/b',  # Descarga el mejor audio o lo que esté disponible
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128', 
        }],
        'quiet': False,       # Activamos logs para ver exactamente qué hace
        'no_warnings': False,
        # Fingimos ser un navegador Safari en MacOS legítimo
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9',
            'Sec-Fetch-Mode': 'navigate',
        },
        # Forzamos los clientes nativos simulados que mejor saltan las restricciones
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'android'],
                'skip': ['dash', 'hls']
            }
        },
        'sleep_interval': 3, # Espera 3 segundos para no saturar
    }
    
    cookie_path = os.path.abspath('cookies.txt')
    if os.path.exists(cookie_path):
        ydl_opts['cookiefile'] = cookie_path
        print("-> Añadiendo pasaporte de cookies al camuflaje...")
        
    os.makedirs('downloads', exist_ok=True)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(video_url, download=True)
            video_id = info['id']
            upload_date = info.get('upload_date', datetime.now().strftime('%Y%m%d'))
            dt = datetime.strptime(upload_date, '%Y%m%d')
            pub_date = dt.strftime('%a, %d %b %Y %H:%M:%S +0000')

            return {
                'id': video_id,
                'title': info.get('title', 'Sin título'),
                'description': info.get('description', 'Sin descripción')[:400] + '...',
                'pubDate': pub_date,
                'audio_url': RELEASE_URL_TEMPLATE.format(video_id=video_id),
                'duration': info.get('duration', 0)
            }
        except Exception as e:
            print(f"Error crítico en descarga: {e}")
            return None

def main():
    data = load_data()
    existing_ids = {ep['id'] for ep in data}
    urls = get_urls()
    new_episodes_added = False
    
    for url in urls:
        video_id = clean_video_id(url)
        if not video_id:
            print(f"URL no reconocida: {url}")
            continue
            
        print(f"Analizando origen limpio: https://www.youtube.com/watch?v={video_id}")
        
        if video_id in existing_ids:
            print(f"El vídeo {video_id} ya existe. Saltando...")
            continue
            
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"¡Nuevo episodio encontrado! Iniciando descarga en modo sigilo...")
        
        ep_meta = download_and_metadata(video_url)
        if ep_meta:
            data.insert(0, ep_meta)
            new_episodes_added = True
            
    generate_rss(data)
    
    if new_episodes_added:
        save_data(data)
        
    github_env = os.environ.get('GITHUB_ENV', 'dummy_env.txt')
    with open(github_env, 'a') as f:
        f.write(f"NEW_EPISODES={'true' if new_episodes_added else 'false'}\n")

if __name__ == '__main__':
    main()
