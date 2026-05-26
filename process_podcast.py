import os
import json
import urllib.request
import urllib.parse
from datetime import datetime

REPO_NAME = os.environ.get('GITHUB_REPOSITORY', 'tu-usuario/tu-repositorio')
RELEASE_URL_TEMPLATE = f"https://github.com/{REPO_NAME}/releases/download/episodes/{{video_id}}.mp3"

# Lista de servidores espejo alternativos de Invidious por si uno falla
INVIDIOUS_INSTANCES = [
    "https://inv.tux.digital",
    "https://invidious.nerdvpn.de",
    "https://yewtu.be",
    "https://invidious.flokinet.to"
]

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

def download_audio_via_invidious(video_id):
    os.makedirs('downloads', exist_ok=True)
    output_path = f"downloads/{video_id}.mp3"
    
    for instance in INVIDIOUS_INSTANCES:
        # Intentamos obtener los metadatos del vídeo desde la API de Invidious
        api_url = f"{instance}/api/v1/videos/{video_id}"
        print(f"-> Intentando conectar con espejo: {instance}")
        try:
            req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as response:
                video_data = json.loads(response.read().decode())
                
            # Buscamos la pista de audio en la lista de formatos devuelta
            adaptive_formats = video_data.get('adaptiveFormats', [])
            audio_url = None
            
            # Buscamos preferiblemente un formato tipo audio puro
            for f in adaptive_formats:
                if "audio/" in f.get('type', ''):
                    audio_url = f.get('url')
                    break
            
            # Si no hay audio puro, cogemos el formato de vídeo de menor calidad para extraer el audio
            if not audio_url and adaptive_formats:
                audio_url = adaptive_formats[0].get('url')
                
            if not audio_url:
                continue
                
            # Descargamos el archivo directamente usando FFmpeg para asegurar que se guarde como MP3 válido
            print(f"-> Descargando flujo de audio e indexando a MP3...")
            ffmpeg_cmd = f'ffmpeg -y -i "{audio_url}" -vn -ar 44100 -ac 2 -b:a 128k "{output_path}"'
            exit_code = os.system(ffmpeg_cmd)
            
            if exit_code == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
                # Extraemos metadatos básicos para el RSS
                duration = video_data.get('lengthSeconds', 0)
                title = video_data.get('title', 'Audio de YouTube')
                description = video_data.get('description', '')[:400] + '...'
                
                # Formateamos la fecha de publicación
                pub_date = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')
                try:
                    ts = video_data.get('published', 0)
                    if ts:
                        pub_date = datetime.fromtimestamp(ts).strftime('%a, %d %b %Y %H:%M:%S +0000')
                except Exception:
                    pass

                print(f"¡Éxito! Descargado: {title}")
                return {
                    'id': video_id,
                    'title': title,
                    'description': description,
                    'pubDate': pub_date,
                    'audio_url': RELEASE_URL_TEMPLATE.format(video_id=video_id),
                    'duration': duration
                }
        except Exception as e:
            print(f"Aviso: El espejo {instance} falló o dio error: {e}")
            continue
            
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
        video_id = clean_video_id(url)
        if not video_id:
            print(f"No se pudo extraer un ID de vídeo válido de: {url}")
            continue
            
        print(f"Analizando origen: {url} (ID: {video_id})")
        
        if video_id in existing_ids:
            print(f"El vídeo {video_id} ya existe en el historial. Saltando...")
            continue
            
        print(f"¡Nuevo episodio detectado! Procesando a través de pasarela alternativa...")
        ep_meta = download_audio_via_invidious(video_id)
        
        if ep_meta:
            data.insert(0, ep_meta)
            new_episodes_added = True
        else:
            print(f"No se pudo descargar el vídeo {video_id} tras intentar con todos los espejos.")
            
    generate_rss(data)
    if new_episodes_added:
        save_data(data)
        
    github_env = os.environ.get('GITHUB_ENV', 'dummy_env.txt')
    with open(github_env, 'a') as f:
        f.write(f"NEW_EPISODES={'true' if new_episodes_added else 'false'}\n")

if __name__ == '__main__':
    main()
