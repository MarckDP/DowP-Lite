import sys
import os
import subprocess
import multiprocessing
import tempfile  
import atexit   
import tkinter as tk
import platform

from tkinter import messagebox
from PIL import Image, ImageTk

APP_VERSION = "1.3.5"

if getattr(sys, 'frozen', False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

BIN_DIR = os.path.join(PROJECT_ROOT, "bin")
FFMPEG_BIN_DIR = os.path.join(BIN_DIR, "ffmpeg")
DENO_BIN_DIR = os.path.join(BIN_DIR, "deno")


def get_icon_path():
    """
    Retorna la ruta del icono correcto según el sistema operativo.
    - Windows: DowP-icon.ico
    - macOS: DowP-icon.icns
    - Linux: DowP-icon.ico (aunque Linux puede usar PNG también)
    """
    if platform.system() == "Darwin":  # macOS
        icon_file = "DowP-icon.icns"
    else:  # Windows y Linux
        icon_file = "DowP-icon.ico"
    
    icon_path = os.path.join(PROJECT_ROOT, icon_file)
    
    # Verificar si existe, sino retornar None
    if os.path.exists(icon_path):
        return icon_path
    else:
        print(f"ADVERTENCIA: No se encontró el icono en: {icon_path}")
        return None


class SplashScreen:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()  # Ocultar inicialmente para evitar parpadeos
        
        # Configurar título
        self.root.title("DowP Lite")
        
        # Configuración visual
        bg_color = "#2B2B2B"
        text_color = "#FFFFFF"
        self.root.configure(bg=bg_color)
        
        # Dimensiones MUY compactas
        width, height = 200, 80
        
        # CRÍTICO para macOS: Configurar geometría ANTES de quitar bordes
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        
        # Forzar actualización de geometría
        self.root.update_idletasks()
        
        # Configuración específica por plataforma
        if platform.system() == "Darwin":
            # macOS: Configurar atributos en el orden correcto
            self.root.attributes("-topmost", True)
            # Pequeño delay antes de quitar bordes en macOS
            self.root.after(10, lambda: self._configure_borderless())
        else:
            # Windows/Linux: Quitar bordes inmediatamente
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", True)

        # Canvas para el contenido
        self.canvas = tk.Canvas(
            self.root, 
            width=width, 
            height=height, 
            bg=bg_color, 
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)

        # Centro absoluto de la ventana
        center_x = width // 2
        center_y = height // 2
        
        # Cargar y mostrar icono (centrado, arriba)
        self.photo = None
        icon_y = 22  # Parte superior
        try:
            # Usar la función multiplataforma
            icon_path = get_icon_path()
            if icon_path:
                img = Image.open(icon_path).resize((32, 32), Image.LANCZOS)
                self.photo = ImageTk.PhotoImage(img)
                self.canvas.create_image(center_x, icon_y, image=self.photo)
        except Exception as e:
            print(f"Error cargando icono en splash: {e}")

        # Título DowP + Versión (centrado, debajo del icono)
        self.canvas.create_text(
            center_x, 48, 
            text=f"DowP Lite {APP_VERSION}", 
            fill=text_color, 
            font=("Segoe UI", 10, "bold"), 
            anchor="center"
        )
        
        # Texto de Estado (centrado, abajo)
        self.status_text = self.canvas.create_text(
            center_x, 65, 
            text="Iniciando...", 
            fill="#999999", 
            font=("Segoe UI", 8), 
            anchor="center"
        )

        # Mostrar la ventana
        self.root.deiconify()
        
        # Forzar actualización y traer al frente
        self.root.update_idletasks()
        self.root.update()
        self.root.lift()
        self.root.focus_force()
        
    def _configure_borderless(self):
        """Configura la ventana sin bordes (usado en macOS con delay)"""
        try:
            if self.root and self.root.winfo_exists():
                self.root.overrideredirect(True)
                self.root.update_idletasks()
        except Exception as e:
            print(f"Error configurando borderless: {e}")

    def update_status(self, text):
        """Actualiza el texto y fuerza al OS a redibujar la ventana"""
        if self.root.winfo_exists():
            self.canvas.itemconfig(self.status_text, text=text)
            # Forzar actualización de píxeles
            self.root.update_idletasks()
            self.root.update()

    def destroy(self):
        if self.root:
            self.root.destroy()
            self.root = None


class SingleInstance:
    def __init__(self):
        self.lockfile = os.path.join(tempfile.gettempdir(), 'dowp.lock')
        if os.path.exists(self.lockfile):
            try:
                with open(self.lockfile, 'r') as f:
                    pid = int(f.read())
                if self._is_pid_running(pid):
                    messagebox.showwarning("DowP ya está abierto",
                                           f"Ya hay una instancia de DowP en ejecución (Proceso ID: {pid}).\n\n"
                                           "Por favor, busca la ventana existente.")
                    sys.exit(1)
                else:
                    print("INFO: Se encontró un archivo de cerrojo obsoleto. Eliminándolo.")
                    os.remove(self.lockfile)
            except Exception as e:
                print(f"ADVERTENCIA: No se pudo verificar el archivo de cerrojo. Eliminándolo. ({e})")
                try:
                    os.remove(self.lockfile)
                except OSError:
                    pass
        with open(self.lockfile, 'w') as f:
            f.write(str(os.getpid()))
        atexit.register(self.cleanup)

    def _is_pid_running(self, pid):
        """
        Comprueba si un proceso con un PID dado está corriendo Y si
        coincide con el nombre de este ejecutable.
        """
        try:
            if sys.platform == "win32":
                # Obtenemos el nombre del ejecutable actual (ej: "dowp.exe" o "python.exe")
                image_name = os.path.basename(sys.executable)
                
                # Comando de tasklist MEJORADO:
                # Filtra por PID Y por nombre de imagen.
                command = ['tasklist', '/fi', f'PID eq {pid}', '/fi', f'IMAGENAME eq {image_name}']
                
                # Usamos creationflags=0x08000000 para (CREATE_NO_WINDOW) y evitar que aparezca una consola
                output = subprocess.check_output(command, 
                                                 stderr=subprocess.STDOUT, 
                                                 text=True, 
                                                 creationflags=0x08000000)
                
                # Si el proceso (PID + Nombre) se encuentra, el PID estará en la salida.
                return str(pid) in output
            else: 
                try:
                    # 1. Comprobación rápida de existencia del PID
                    os.kill(pid, 0)
                    
                    # 2. Si existe, comprobar la identidad del proceso
                    expected_name = os.path.basename(sys.executable)
                    command = ['ps', '-p', str(pid), '-o', 'comm=']
                    
                    output = subprocess.check_output(command, 
                                                     stderr=subprocess.STDOUT, 
                                                     text=True)
                    
                    process_name = output.strip()
                    
                    # Compara el nombre del proceso (ej: 'python3' o 'dowp')
                    return process_name == expected_name
                    
                except (OSError, subprocess.CalledProcessError):
                    # OSError: "No such process" (el PID no existe)
                    # CalledProcessError: 'ps' falló
                    return False
        except (subprocess.CalledProcessError, FileNotFoundError):
            # CalledProcessError: Ocurre si el PID no existe (en Windows)
            # FileNotFoundError: tasklist/ps no encontrado (muy raro)
            return False
        except Exception as e:
            # Captura cualquier otro error inesperado
            print(f"Error inesperado en _is_pid_running: {e}")
            return False
        
    def cleanup(self):
        """Borra el archivo de cerrojo al cerrar."""
        try:
            if os.path.exists(self.lockfile):
                os.remove(self.lockfile)
        except Exception as e:
            print(f"ADVERTENCIA: No se pudo limpiar el archivo de cerrojo: {e}")

if __name__ == "__main__":
    # 1. Mostrar Splash INMEDIATAMENTE
    splash = SplashScreen()
    splash.update_status("Verificando instancia única...")

    SingleInstance()
    multiprocessing.freeze_support()

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # 2. Actualizar estado mientras configuras el entorno
    splash.update_status("Configurando entorno y rutas...")

    # Añadir el directorio 'bin' principal
    if os.path.isdir(BIN_DIR) and BIN_DIR not in os.environ['PATH']:
        os.environ['PATH'] = BIN_DIR + os.pathsep + os.environ['PATH']
    
    # Añadir el subdirectorio de FFmpeg
    if os.path.isdir(FFMPEG_BIN_DIR) and FFMPEG_BIN_DIR not in os.environ['PATH']:
        os.environ['PATH'] = FFMPEG_BIN_DIR + os.pathsep + os.environ['PATH']

    # Añadir el subdirectorio de Deno 
    if os.path.isdir(DENO_BIN_DIR) and DENO_BIN_DIR not in os.environ['PATH']:
        os.environ['PATH'] = DENO_BIN_DIR + os.pathsep + os.environ['PATH']

    print("Iniciando la aplicación...")
    launch_target = sys.argv[1] if len(sys.argv) > 1 else None
    
    # 3. Actualizar justo antes de la carga pesada
    splash.update_status("Cargando módulos e interfaz...")
    
    # Aquí ocurre la "pausa" de carga, pero el usuario verá la ventana flotante
    from src.gui.main_window import MainWindow 
    
    # 4. Pasar la referencia 'splash' a la ventana principal
    app = MainWindow(launch_target=launch_target, 
                     project_root=PROJECT_ROOT, 
                     splash_screen=splash,
                     app_version=APP_VERSION)
    
    app.mainloop()