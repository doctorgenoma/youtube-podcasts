import os
import json
import yt_dlp
from datetime import datetime

# Detectar el repositorio dinámicamente en GitHub
REPO_NAME = os.environ.get('GITHUB_REPOSITORY', 'tu-usuario/tu-repositorio')
RELEASE_URL_TEMPLATE = f"https://github.com/{REPO_NAME}/releases/download/episodes/{{video_id}}.mp3"

def load_data():
    if os.path.exists('podcast_data.json'):
        with open('podcast_data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_data(data):
    with open('podcast_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_urls():
    if not os.path.exists('urls.txt'):
        return []
    with open('urls.txt', 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

def download_and_metadata(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128', # 128kbps es ideal para podcast y ahorra espacio
        }],
        'quiet': True,
        'no_warnings': True,
    }
    
    os.makedirs('downloads', exist_ok=True)
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            video_id = info['id']
            
            # Formatear fecha al estándar de Podcasts (RFC 822)
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
            print(f"Error procesando {url}: {e}")
            return None

def generate_rss(episodes):
    rss_items = ""
    for ep in episodes:
        # Limpieza básica de caracteres inválidos para XML
        title = ep['title'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        desc = ep['description'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Formatear duración de segundos a hh:mm:ss
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
        # Extraer ID rápido para comprobar si ya lo tenemos
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                video_id = info['id']
            except:
                continue
                
        if video_id in existing_ids:
            continue
            
        print(f"Procesando nuevo vídeo: {video_id}")
        ep_meta = download_and_metadata(url)
        if ep_meta:
            data.insert(0, ep_meta) # Los nuevos aparecen arriba
            new_episodes_added = True
            
    # Forzar la generación del RSS siempre para mantenerlo actualizado
    generate_rss(data)
    
    if new_episodes_added:
        save_data(data)
        with open(os.environ['GITHUB_ENV'], 'a') as f:
            f.write("NEW_EPISODES=true\n")
    else:
        with open(os.environ['GITHUB_ENV'], 'a') as f:
            f.write("NEW_EPISODES=false\n")

if __name__ == '__main__':
    main()
