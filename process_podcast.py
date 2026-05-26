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
                if not content:
                    return []
                return json.loads(content)
        except Exception as e:
            print(f"Aviso: podcast_data.json no era válido. Se restablecerá de forma segura.")
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

def download_and_metadata(video_url):
    # Forzamos compatibilidad máxima de formatos y simuladores de clientes (iOS, Android, Web)
    ydl_opts = {
        'format': 'bestaudio/best', 
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128', 
        }],
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web'],
                'skip': ['dash', 'hls']
            }
        }
    }
    
    cookie_path = os.path.abspath('cookies.txt')
    if os.path.exists(cookie_path):
        ydl_opts['cookiefile'] = cookie_path
        print("-> Inyectando archivo de cookies para la descarga...")
        
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
            print(f"Error descargando el video {video_url}: {e}")
            return None

def generate_rss(episodes):
    rss_items = ""
    for ep in episodes:
        title = ep['title'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        desc = ep['description'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        seconds = ep['duration']
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        duration_str = f"{hours:02d}:{minutes:02d}:{secs:02d}"

        rss_items += f"""
        <item>
            <title>{title}</title>
            <description>{desc}</description>
            <pubDate>{ep['pubDate']}</pubDate>
            <enclosure url="{ep['audio_url']}" type="audio/mpeg" />
            <guid isPermaLink="false">{ep['id']}</guid>
            <itunes:duration>{duration_str}</itunes:duration>
        </item>"""

    rss_feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Mi Podcast Automatizado</title>
    <link>https://github.com/{REPO_NAME}</link>
    <language>es</language>
    <description>Audios de YouTube convertidos a Podcast.</description>
    <itunes:image href="https://raw.githubusercontent.com/{REPO_NAME}/main/podcast_cover.jpg"/>
    {rss_items}
  </channel>
</rss>"""
    with open('feed.xml', 'w', encoding='utf-8') as f:
        f.write(rss_feed)

def main():
    data = load_data()
    existing_ids = {ep['id'] for ep in data}
    urls = get_urls()
    new_episodes_added = False
    
    for url in urls:
        if 'watch?v=' in url:
            video_id_clean = url.split('v=')[1].split('&')[0]
            url = f"https://www.youtube.com/watch?v={video_id_clean}"

        # Configuración simplificada y robusta para la fase de análisis
        ydl_opts_flat = {
            'quiet': True,
            'extract_flat': True,
            'no_warnings': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'web']
                }
            }
        }
        cookie_path = os.path.abspath('cookies.txt')
        if os.path.exists(cookie_path):
            ydl_opts_flat['cookiefile'] = cookie_path
            
        print(f"Analizando origen: {url}")
        with yt_dlp.YoutubeDL(ydl_opts_flat) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                
                if 'entries' in info and info['entries']:
                    if 'list=' in url and 'watch?v=' not in url:
                        latest_entry = info['entries'][-1]
                        tipo = "playlist"
                    else:
                        latest_entry = info['entries'][0]
                        tipo = "canal"
                    video_id = latest_entry['id']
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    print(f"-> Detectado {tipo}. Objetivo: {video_id}")
                else:
                    video_id = info['id']
                    video_url = url
                    print(f"-> Detectado vídeo individual: {video_id}")
            except Exception as e:
                print(f"Error al analizar la URL {url}: {e}")
                continue
                
        if video_id in existing_ids:
            print(f"El vídeo {video_id} ya existe. Saltando...")
            continue
            
        print(f"¡Nuevo episodio encontrado! Descargando de forma autenticada: {video_id}")
        ep_meta = download_and_metadata(video_url)
        if ep_meta:
            data.insert(0, ep_meta)
            new_episodes_added = True
            
    generate_rss(data)
    
    if new_episodes_added:
        save_data(data)
        
    github_env = os.environ.get('GITHUB_ENV', 'dummy_env.txt')
    with open(github_env, 'a') as f:
        if new_episodes_added:
            f.write("NEW_EPISODES=true\n")
        else:
            f.write("NEW_EPISODES=false\n")

if __name__ == '__main__':
    main()
