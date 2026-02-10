import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
import requests
import stat
import platform

from packaging import version
from main import PROJECT_ROOT, BIN_DIR, FFMPEG_BIN_DIR

DENO_BIN_DIR = os.path.join(PROJECT_ROOT, "bin", "deno")

DENO_VERSION_FILE = os.path.join(DENO_BIN_DIR, "deno_version.txt")
FFMPEG_VERSION_FILE = os.path.join(FFMPEG_BIN_DIR, "ffmpeg_version.txt")

def get_system_context():
    """Identifica el sistema operativo y la arquitectura (Intel vs Apple Silicon)."""
    system = platform.system()
    machine = platform.machine().lower()
    # Simplificamos: arm64 para Apple Silicon, x86_64 para el resto
    arch = 'arm64' if machine in ['arm64', 'aarch64'] else 'x86_64'
    return system, arch

def check_and_install_python_dependencies(progress_callback):
    """Verifica e instala dependencias de Python, reportando el progreso."""
    progress_callback("Verificando dependencias de Python...", 5)
    try:
        import customtkinter
        import PIL
        import requests
        import yt_dlp
        import flask_socketio
        import gevent
        progress_callback("Dependencias de Python verificadas.", 15)
        return True
    except ImportError:
        progress_callback("Instalando dependencias necesarias...", 10)
    requirements_path = os.path.join(PROJECT_ROOT, "requirements.txt")
    if not os.path.exists(requirements_path):
        progress_callback("ERROR: No se encontró 'requirements.txt'.", -1)
        return False
    try:
        process = subprocess.Popen(
            [sys.executable, "-m", "pip", "install", "-r", requirements_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, process.args, output=stdout, stderr=stderr)
        progress_callback("Dependencias instaladas.", 15)
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Falló la instalación de dependencias con pip: {e.stderr}")
        progress_callback(f"Error al instalar dependencias.", -1)
        return False

def get_latest_ffmpeg_info(progress_callback):
    system, arch = get_system_context()
    try:
        if system == "Darwin":
            # Para Mac necesitamos dos descargas separadas
            tools = ["ffmpeg", "ffprobe"]
            results = {}
            for tool in tools:
                api_url = f"https://evermeet.cx/ffmpeg/info/{tool}/release"
                r = requests.get(api_url, timeout=15)
                data = r.json()
                results[tool] = {
                    "tag": data.get("version"),
                    "url": data.get("download", {}).get("zip", {}).get("url")
                }
            # Devolvemos el tag del primero y el diccionario de URLs
            return results["ffmpeg"]["tag"], results
        
        else:  # Windows / Linux (BtbN GitHub)
            api_url = "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases"
            response = requests.get(api_url, timeout=15)
            response.raise_for_status()
            releases = response.json()
            latest_release_data = next((r for r in releases if r['tag_name'] != 'latest'), None)
            
            if not latest_release_data: return None, None
            
            tag_name = latest_release_data["tag_name"]
            file_identifier = "win64-gpl.zip" if system == "Windows" else "linux64-gpl.tar.xz"
            
            for asset in latest_release_data["assets"]:
                if file_identifier in asset["name"] and "shared" not in asset["name"]:
                    progress_callback("Información de FFmpeg (GitHub) encontrada.", 10)
                    return tag_name, asset["browser_download_url"]
                    
        return None, None
    except Exception as e:
        progress_callback(f"Error al buscar FFmpeg: {e}", -1)
        return None, None
    
def download_and_install_ffmpeg(tag, url_data, progress_callback):
    """
    Descarga e instala FFmpeg. En Windows extrae todo del mismo ZIP.
    En macOS descarga cada herramienta por separado.
    """
    system = platform.system()
    # Si es Windows, el 'url_data' es un string. Creamos un dict para el bucle.
    downloads = url_data if isinstance(url_data, dict) else {"ffmpeg_package": {"url": url_data}}
    
    try:
        os.makedirs(FFMPEG_BIN_DIR, exist_ok=True)
        
        for tool_key, info in downloads.items():
            url = info["url"] if isinstance(info, dict) else url_data
            file_name = url.split('/')[-1]
            archive_name = os.path.join(PROJECT_ROOT, file_name)
            
            # 1. Descarga (Se mantiene igual)
            with requests.get(url, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(archive_name, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk: f.write(chunk)

            # 2. Extracción temporal
            temp_path = os.path.join(PROJECT_ROOT, f"temp_{tool_key}")
            if os.path.exists(temp_path): shutil.rmtree(temp_path)
            
            if archive_name.endswith(".zip"):
                with zipfile.ZipFile(archive_name, 'r') as zip_ref: zip_ref.extractall(temp_path)
            else:
                with tarfile.open(archive_name, 'r:xz') as tar_ref: tar_ref.extractall(temp_path)

            # 3. Mover binarios (Lógica inteligente para Windows vs Mac)
            # En Windows queremos ffmpeg y ffprobe. En Mac, tool_key es el nombre específico.
            target_tools = ["ffmpeg", "ffprobe"] if system == "Windows" else [tool_key]
            
            for root, dirs, files in os.walk(temp_path):
                for f in files:
                    clean_name = f.replace(".exe", "").lower()
                    if clean_name in target_tools:
                        src = os.path.join(root, f)
                        dst = os.path.join(FFMPEG_BIN_DIR, f)
                        
                        if os.path.exists(dst): os.remove(dst)
                        shutil.move(src, dst)
                        
                        # Permisos para Mac/Linux
                        if system != "Windows":
                            st = os.stat(dst)
                            os.chmod(dst, st.st_mode | stat.S_IEXEC)

            # Limpieza
            shutil.rmtree(temp_path)
            os.remove(archive_name)

        # 4. LA DIETA: Eliminar ffplay si existe
        ffplay_exe = "ffplay.exe" if system == "Windows" else "ffplay"
        ffplay_path = os.path.join(FFMPEG_BIN_DIR, ffplay_exe)
        if os.path.exists(ffplay_path):
            try: os.remove(ffplay_path)
            except: pass

        with open(FFMPEG_VERSION_FILE, "w") as f: f.write(tag)
        progress_callback(f"FFmpeg {tag} instalado.", 95)
        return True

    except Exception as e:
        progress_callback(f"Error: {e}", -1)
        return False

def get_latest_deno_info(progress_callback):
    """Consulta la API de GitHub para Deno con los nombres de archivo exactos."""
    system, arch = get_system_context()
    progress_callback("Consultando última versión de Deno...", 5)
    try:
        api_url = "https://api.github.com/repos/denoland/deno/releases/latest"
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        data = response.json()
        tag_name = data["tag_name"]
        
        # Mapeo exacto basado en la arquitectura y sistema
        if system == "Windows":
            file_identifier = "deno-x86_64-pc-windows-msvc.zip"
        elif system == "Darwin": # macOS
            if arch == "arm64":
                file_identifier = "deno-aarch64-apple-darwin.zip"
            else:
                file_identifier = "deno-x86_64-apple-darwin.zip"
        elif system == "Linux":
            if arch == "arm64":
                file_identifier = "deno-aarch64-unknown-linux-gnu.zip"
            else:
                file_identifier = "deno-x86_64-unknown-linux-gnu.zip"
        else:
            return None, None
        
        for asset in data["assets"]:
            if file_identifier == asset["name"]: # Búsqueda exacta
                progress_callback(f"Deno para {arch} encontrado.", 10)
                return tag_name, asset["browser_download_url"]
                
        return tag_name, None
    except Exception as e:
        progress_callback(f"Error al buscar Deno: {e}", -1)
        return None, None

import stat

def download_and_install_deno(tag, url, progress_callback):
    """Descarga e instala Deno, aplicando permisos de ejecución en macOS/Linux."""
    system, arch = get_system_context()
    try:
        file_name = url.split('/')[-1]
        archive_name = os.path.join(PROJECT_ROOT, file_name)
        
        # --- Lógica de descarga ---
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            downloaded_size = 0
            with open(archive_name, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            progress = 40 + (downloaded_size / total_size) * 40
                            progress_callback(f"Descargando Deno: {downloaded_size/1024/1024:.1f} MB", progress)
                            
        progress_callback("Extrayendo archivos de Deno...", 85)
        os.makedirs(DENO_BIN_DIR, exist_ok=True)
        
        with zipfile.ZipFile(archive_name, 'r') as zip_ref:
            for member in zip_ref.namelist():
                # Deno suele venir como un solo binario en la raíz del zip
                if member.lower().startswith('deno'):
                    zip_ref.extract(member, DENO_BIN_DIR)
                    extracted_path = os.path.join(DENO_BIN_DIR, member)
                    final_path = os.path.join(DENO_BIN_DIR, os.path.basename(member))
                    
                    if extracted_path != final_path:
                        if os.path.exists(final_path): os.remove(final_path)
                        shutil.move(extracted_path, final_path)
                    
                    # --- CRÍTICO: PERMISOS EN MAC/LINUX ---
                    if system != "Windows":
                        st = os.stat(final_path)
                        os.chmod(final_path, st.st_mode | stat.S_IEXEC)
        
        os.remove(archive_name)
        with open(DENO_VERSION_FILE, "w") as f: f.write(tag)
        progress_callback(f"Deno {tag} instalado correctamente.", 95)
        return True
    except Exception as e:
        progress_callback(f"Error al instalar Deno: {e}", -1)
        return False

def check_environment_status(progress_callback, check_updates=True): # <--- NUEVO PARAMETRO
    """
    Verifica el estado del entorno.
    Si check_updates=False, salta las consultas lentas a GitHub.
    """
    try:
        # Importar dependencias (Esto es rápido si ya están instaladas)
        if not check_and_install_python_dependencies(progress_callback):
            return {"status": "error", "message": "Fallo crítico en dependencias Python."}
        
        # --- 1. Chequeo Local (Rápido) ---
        # Definir rutas (esto ya lo tienes, asegúrate de que coincida con tu código)
        ffmpeg_exe = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
        ffmpeg_path = os.path.join(FFMPEG_BIN_DIR, ffmpeg_exe)
        ffmpeg_exists = os.path.exists(ffmpeg_path)
        
        local_tag = ""
        if os.path.exists(FFMPEG_VERSION_FILE):
            with open(FFMPEG_VERSION_FILE, 'r') as f: local_tag = f.read().strip()
        
        # --- 1. FFmpeg ---
        ffmpeg_path = os.path.join(FFMPEG_BIN_DIR, "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg")
        ffmpeg_exists = os.path.exists(ffmpeg_path)
        
        local_tag = ""
        if os.path.exists(FFMPEG_VERSION_FILE):
            with open(FFMPEG_VERSION_FILE, 'r') as f:
                local_tag = f.read().strip()
        # Deno...
        deno_exe = "deno.exe" if platform.system() == "Windows" else "deno"
        deno_path = os.path.join(DENO_BIN_DIR, deno_exe)
        deno_exists = os.path.exists(deno_path)
        local_deno_tag = ""
        if os.path.exists(DENO_VERSION_FILE):
            with open(DENO_VERSION_FILE, 'r') as f: local_deno_tag = f.read().strip()

        # --- 2. Chequeo Remoto (Lento) - SOLO SI ES NECESARIO ---
        latest_tag, download_url = None, None
        latest_deno_tag, deno_download_url = None, None
        latest_poppler_tag, poppler_download_url = None, None

        if check_updates:
            # Solo consultamos GitHub si nos lo piden explícitamente
            latest_tag, download_url = get_latest_ffmpeg_info(progress_callback)
            latest_deno_tag, deno_download_url = get_latest_deno_info(progress_callback)
        else:
            progress_callback("Verificación rápida de entorno completada.", 20)

        # --- Construir diccionario FINAL ---
        return {
            "status": "success", 
            
            # FFmpeg
            "ffmpeg_path_exists": ffmpeg_exists,
            "local_version": local_tag,
            "latest_version": latest_tag,     # Será None si check_updates=False
            "download_url": download_url,
            
            # Deno
            "deno_path_exists": deno_exists,
            "local_deno_version": local_deno_tag,
            "latest_deno_version": latest_deno_tag,
            "deno_download_url": deno_download_url,

        }
        
    except Exception as e:
        return {"status": "error", "message": f"Error en la verificación del entorno: {e}"}
    
def check_ffmpeg_status(progress_callback):
    """
    Verifica el estado únicamente de FFmpeg.
    """
    try:
        ffmpeg_path = os.path.join(FFMPEG_BIN_DIR, "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg")
        ffmpeg_exists = os.path.exists(ffmpeg_path)

        local_tag = ""
        if os.path.exists(FFMPEG_VERSION_FILE):
            with open(FFMPEG_VERSION_FILE, 'r') as f:
                local_tag = f.read().strip()

        latest_tag, download_url = get_latest_ffmpeg_info(progress_callback)

        return {
            "status": "success",
            "ffmpeg_path_exists": ffmpeg_exists,
            "local_version": local_tag,
            "latest_version": latest_tag,
            "download_url": download_url
        }
    except Exception as e:
        return {"status": "error", "message": f"Error en la verificación de FFmpeg: {e}"}

def check_deno_status(progress_callback):
    """
    Verifica el estado únicamente de Deno.
    """
    try:
        deno_exe_name = "deno.exe" if platform.system() == "Windows" else "deno"
        deno_path = os.path.join(DENO_BIN_DIR, deno_exe_name)
        deno_exists = os.path.exists(deno_path)

        local_deno_tag = ""
        if os.path.exists(DENO_VERSION_FILE):
            with open(DENO_VERSION_FILE, 'r') as f:
                local_deno_tag = f.read().strip()

        latest_deno_tag, deno_download_url = get_latest_deno_info(progress_callback)

        return {
            "status": "success",
            "deno_path_exists": deno_exists,
            "local_deno_version": local_deno_tag,
            "latest_deno_version": latest_deno_tag,
            "deno_download_url": deno_download_url
        }
    except Exception as e:
        return {"status": "error", "message": f"Error en la verificación de Deno: {e}"}
    
def check_app_update(current_version_str):
    """Consulta GitHub para ver si hay una nueva versión y busca el instalador LIGHT en ZIP."""
    print(f"INFO: Verificando actualizaciones para la versión actual: {current_version_str}")
    try:
        api_url = "https://api.github.com/repos/MarckDP/DowP/releases"

        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        releases = response.json()

        if not releases:
            return {"update_available": False}

        # Encontrar la release más reciente
        latest_release = None
        for r in releases:
            if not r.get("prerelease", False):
                latest_release = r
                break
        if not latest_release: 
            latest_release = releases[0]

        latest_version_str = latest_release.get("tag_name", "0.0.0").lstrip('v')
        release_url = latest_release.get("html_url")

        installer_url = None
        
        # --- CAMBIO: Buscamos el ZIP ---
        expected_suffix = "Light_setup.zip" 
        
        for asset in latest_release.get("assets", []):
            asset_name = asset.get("name", "")
            
            # Verificamos versión y sufijo
            if f"v{latest_version_str}" in asset_name and asset_name.endswith(expected_suffix):
                installer_url = asset.get("browser_download_url")
                print(f"INFO: Instalador Light (ZIP) encontrado: {asset_name}")
                break 
        
        # Fallback: Si no encuentra el Light ZIP, buscar cualquier .zip (Full o normal)
        if not installer_url:
             print("ADVERTENCIA: No se encontró ZIP 'Light', buscando ZIP genérico...")
             for asset in latest_release.get("assets", []):
                if asset.get("name", "").endswith(".zip") and "setup" in asset.get("name", "").lower():
                    installer_url = asset.get("browser_download_url")
                    break

        current_v = version.parse(current_version_str)
        latest_v = version.parse(latest_version_str)

        if latest_v > current_v:
            return {
                "update_available": True,
                "latest_version": latest_version_str,
                "release_url": release_url,
                "installer_url": installer_url, # URL del .zip
                "is_prerelease": latest_release.get("prerelease", False)
            }
        else:
            return {"update_available": False}

    except Exception as e:
        print(f"ERROR verificando actualización: {e}")
        return {"error": "Error al verificar."}
    
def get_remote_file_size(url):
    """Obtiene el tamaño de un archivo remoto en bytes sin descargarlo."""
    try:
        response = requests.head(url, allow_redirects=True, timeout=5)
        if response.status_code == 200:
            return int(response.headers.get('content-length', 0))
        return 0
    except Exception:
        return 0

def format_size(size_bytes):
    """Formatea bytes a MB/GB."""
    if size_bytes == 0:
        return "Desconocido"
    
    size_mb = size_bytes / (1024 * 1024)
    if size_mb >= 1024:
        return f"{size_mb / 1024:.2f} GB"
    return f"{size_mb:.1f} MB"