import subprocess
import re
from concurrent.futures import ThreadPoolExecutor
import time
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Dit staat cross-origin requests toe

class SpotifyToYouTube:
    def __init__(self, process_timeout=30, total_timeout=35):
        """
        Initialiseer de converter met configureerbare timeouts
        
        Args:
            process_timeout (int): Timeout voor het spotdl proces in seconden
            total_timeout (int): Totale timeout voor de hele conversie in seconden
        """
        self.process_timeout = process_timeout
        self.total_timeout = total_timeout

    def get_youtube_url_from_spotify(self, spotify_url):
        """Gebruikt spotdl om de overeenkomstige YouTube URL te vinden"""
        try:
            # Controleer eerst de geïnstalleerde versie van spotdl
            version_check = subprocess.run(
                ["spotdl", "--version"],
                capture_output=True,
                text=True
            )
            print(f"Spotdl versie: {version_check.stdout.strip()}")
            
            print(f"Zoeken naar YouTube URL voor: {spotify_url}")
            
            # Laten we een eenvoudigere aanpak proberen met het basis 'download' commando
            result = subprocess.run(
                ["spotdl", "download", spotify_url, "--output", "-", "--print-errors", "--debug"],
                capture_output=True,
                text=True,
                timeout=self.process_timeout
            )
            
            output = result.stdout + result.stderr
            print(f"Volledige output lengte: {len(output)} tekens")
            print(f"Spotdl output begin: {output[:300]}...")
            print(f"Spotdl output eind: {output[-300:] if len(output) >= 300 else output}")
            
            # Probeer verschillende URL-patronen te herkennen
            url_patterns = [
                r'(https?://(?:www\.)?(?:music\.)?youtube\.com/watch\?v=[a-zA-Z0-9_-]+)',
                r'URL: (https?://(?:www\.)?(?:music\.)?youtube\.com/watch\?v=[a-zA-Z0-9_-]+)',
                r'Song URL: (https?://(?:www\.)?(?:music\.)?youtube\.com/watch\?v=[a-zA-Z0-9_-]+)',
                r'Using youtube-music\s+URL: (https?://(?:www\.)?(?:music\.)?youtube\.com/watch\?v=[a-zA-Z0-9_-]+)'
            ]
            
            for pattern in url_patterns:
                url_match = re.search(pattern, output)
                if url_match:
                    url = url_match.group(1)
                    return url.replace("music.youtube.com", "youtube.com")
            
            # Controleer of er specifieke foutmeldingen zijn
            if "HTTP Error" in output:
                print("HTTP fout gedetecteerd, mogelijk blokkering of toegangsprobleem")
            if "Connection Error" in output:
                print("Verbindingsfout gedetecteerd, controleer je internetverbinding")
            if "Traceback" in output:
                print("Python traceback gedetecteerd - spotdl heeft een bug of configuratieprobleem")
            
            print("Geen YouTube URL gevonden in de output")
            
            # Probeer een alternatieve aanpak - spotdl op commando-niveau aanroepen
            print("Probeer alternatieve aanpak...")
            spotdl_cmd = f"spotdl download \"{spotify_url}\""
            console_output = subprocess.run(
                spotdl_cmd, 
                shell=True, 
                capture_output=True, 
                text=True,
                timeout=self.process_timeout
            )
            
            console_text = console_output.stdout + console_output.stderr
            print(f"Shell commando output: {console_text[:300]}")
            
            for pattern in url_patterns:
                url_match = re.search(pattern, console_text)
                if url_match:
                    url = url_match.group(1)
                    return url.replace("music.youtube.com", "youtube.com")
            
            return None
        except subprocess.TimeoutExpired:
            print("Timeout: Het proces duurde te lang")
            return None
        except Exception as e:
            print(f"Fout: {e}")
            return None

    def process_url_with_timeout(self, spotify_url):
        """Verwerk URL met timeout"""
        start_time = time.time()
        youtube_url = self.get_youtube_url_from_spotify(spotify_url)
        processing_time = time.time() - start_time
        print(f"\nVerwerking duurde {processing_time:.2f} seconden")
        return youtube_url

    def convert_url(self, spotify_url):
        """
        Converteer een Spotify URL naar een YouTube URL
        
        Args:
            spotify_url (str): De Spotify URL om te converteren
            
        Returns:
            str: YouTube URL als succesvol, None als er een fout optreedt
        """
        with ThreadPoolExecutor() as executor:
            future = executor.submit(self.process_url_with_timeout, spotify_url)
            try:
                youtube_url = future.result(timeout=self.total_timeout)
                return youtube_url
            except TimeoutError:
                print("\nTotale verwerking duurde te lang")
                return None

@app.route('/convert', methods=['POST'])
def convert():
    data = request.get_json()
    spotify_url = data.get('spotify_url')
    
    if not spotify_url:
        return jsonify({"error": "Geen spotify_url opgegeven"}), 400
    
    converter = SpotifyToYouTube()
    youtube_url = converter.convert_url(spotify_url)
    
    if youtube_url:
        return jsonify({"youtube_url": youtube_url})
    else:
        return jsonify({"error": "Kon geen YouTube URL vinden", "youtube_url": None}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
