"""
Script de compilación unificado (Windows / macOS)

Compila para tu sistema actual y empaqueta la app usando PyInstaller.
En Windows genera un ejecutable `.exe` y en macOS un `.app`.

Ejecutar:
python build_cross_platform.py
"""

import PyInstaller.__main__
import os
import sys
import platform
import shutil

# Intentar importar la versión de la app
try:
    from main import APP_VERSION
except ImportError:
    APP_VERSION = "1.3.8"

# ---------------------------------------------------------
# CONFIG APP
# ---------------------------------------------------------
APP_NAME = "DowP_Lite"

# ---------------------------------------------------------
# RUTAS
# ---------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_SCRIPT = os.path.join(SCRIPT_DIR, "main.py")
SRC_DIR = os.path.join(SCRIPT_DIR, "src")

# ---------------------------------------------------------
# DETECTAR SISTEMA Y ARQUITECTURA
# ---------------------------------------------------------
CURRENT_SYSTEM = platform.system()
CURRENT_ARCH = platform.machine()
IS_MACOS = CURRENT_SYSTEM == "Darwin"
IS_WINDOWS = CURRENT_SYSTEM == "Windows"

# Seleccionar Icono
if IS_MACOS:
    ICON_FILE = "DowP-icon.icns"
else:
    ICON_FILE = "DowP-icon.ico"
ICON_PATH = os.path.join(SCRIPT_DIR, ICON_FILE)

print("\n" + "="*50)
print(f"🔨 Compilador PyInstaller Multiplataforma")
print("="*50)
print(f"📦 App: {APP_NAME} v{APP_VERSION}")
print(f"💻 Sistema: {CURRENT_SYSTEM} ({CURRENT_ARCH})")
print(f"📁 Directorio: {SCRIPT_DIR}")
print("="*50 + "\n")

# ---------------------------------------------------------
# VALIDACIONES
# ---------------------------------------------------------
if not os.path.exists(MAIN_SCRIPT):
    print(f"❌ ERROR: No se encontró main.py en {MAIN_SCRIPT}")
    sys.exit(1)

# ---------------------------------------------------------
# CONFIGURACIÓN BUILD
# ---------------------------------------------------------
DIST_DIR = os.path.join(SCRIPT_DIR, 'dist')
BUILD_DIR = os.path.join(SCRIPT_DIR, 'build')

# Separador de PATH en PyInstaller según SO
path_sep = ':' if not IS_WINDOWS else ';'

args = [
    MAIN_SCRIPT,
    
    '--name', APP_NAME,
    '--onedir',         # Modo directorio (recomendado para velocidad y .app)
    '--windowed',       # Ocultar consola, crucial para UI / crear .app bundle
    
    '--clean',
    '--noconfirm',
    
    '--distpath', DIST_DIR,
    '--workpath', BUILD_DIR,
    '--specpath', BUILD_DIR,
    
    # ------------------------------
    # DATOS
    # ------------------------------
    f'--add-data={SRC_DIR}{path_sep}src',
    f'--add-data={ICON_PATH}{path_sep}.',
    
    # ------------------------------
    # HIDDEN IMPORTS
    # ------------------------------
    '--hidden-import=tkinterdnd2',
    '--hidden-import=customtkinter',
    '--hidden-import=PIL._tkinter_finder',
    
    '--hidden-import=flask',
    '--hidden-import=flask_socketio',
    '--hidden-import=engineio',
    '--hidden-import=socketio',
    '--hidden-import=engineio.async_drivers.threading',
    
    '--hidden-import=yt_dlp',
    '--hidden-import=packaging',
    
    # ------------------------------
    # COLLECT ALL
    # ------------------------------
    '--collect-all=customtkinter',
    '--collect-all=tkinterdnd2',
    '--collect-all=flask_socketio',
    '--collect-all=engineio',
    '--collect-all=yt_dlp',
]

# ---------------------------------------------------------
# CONFIGURACIÓN MAC
# ---------------------------------------------------------
if IS_MACOS:
    args.extend([
        '--target-arch', CURRENT_ARCH,
        f'--osx-bundle-identifier=com.dowp.{APP_NAME.lower()}'
    ])

# ---------------------------------------------------------
# ICONO
# ---------------------------------------------------------
if os.path.exists(ICON_PATH):
    print(f"🎨 Icono {ICON_FILE} encontrado, agregando...")
    args.extend(['--icon', ICON_PATH])
else:
    print(f"⚠️  Icono {ICON_FILE} no encontrado (opcional)")

# ---------------------------------------------------------
# EJECUTAR BUILD
# ---------------------------------------------------------
print(f"\n🚀 Iniciando compilación para {CURRENT_SYSTEM}...\n")
print("⏳ Esto puede tardar varios minutos...\n")

try:
    PyInstaller.__main__.run(args)
    
    # ---------------------------------------------------------
    # LIMPIEZA POST-BUILD
    # ---------------------------------------------------------
    print("\n🧹 Limpiando archivos temporales...")
    
    if IS_MACOS:
        app_path = os.path.join(DIST_DIR, f"{APP_NAME}.app")
        extra_folder = os.path.join(DIST_DIR, APP_NAME)
        # Si existe una carpeta adicional (no debería para .app en onedir con PyInstaller reciente), elimínala
        if os.path.exists(extra_folder) and os.path.isdir(extra_folder):
            print(f"   Eliminando carpeta extra: {extra_folder}")
            shutil.rmtree(extra_folder)
        
        if not os.path.exists(app_path):
            print(f"❌ ERROR: No se generó el archivo .app")
            sys.exit(1)
        final_target = app_path
    else:
        app_path = os.path.join(DIST_DIR, APP_NAME)
        exe_path = os.path.join(app_path, f"{APP_NAME}.exe")
        if not os.path.exists(exe_path):
            print(f"❌ ERROR: No se generó el ejecutable en {exe_path}")
            sys.exit(1)
        final_target = exe_path

    # ---------------------------------------------------------
    # RESULTADO
    # ---------------------------------------------------------
    print("\n" + "="*50)
    print("✅ BUILD COMPLETADO EXITOSAMENTE")
    print("="*50)
    
    # Calcular tamaño
    def get_size(path):
        total = 0
        if os.path.isfile(path):
            return os.path.getsize(path)
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total += os.path.getsize(fp)
        return total
    
    size_bytes = get_size(final_target)
    size_mb = size_bytes / (1024 * 1024)
    
    print(f"\n📦 Aplicación generada:")
    print(f"   Ubicación: {final_target}")
    print(f"   Tamaño: {size_mb:.1f} MB")
    
    if IS_MACOS:
        print(f"\n💡 Para ejecutar:")
        print(f"   open \"{final_target}\"")
        print("\n🎉 ¡Todo listo! Tienes tu bundle .app listo.\n")
    else:
        print(f"\n💡 Ejecutable listo en la carpeta {app_path}, lánzalo con:")
        print(f"   {final_target}\n")
    
except Exception as e:
    print("\n" + "="*50)
    print("❌ ERROR EN LA COMPILACIÓN")
    print("="*50)
    print(f"\n{e}\n")
    sys.exit(1)
