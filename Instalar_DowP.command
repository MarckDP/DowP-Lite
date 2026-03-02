#!/bin/bash
# ==============================================================
# Instalador automático DowP Lite para macOS
# Soluciona el error "La aplicación está dañada y debe moverse a la papelera"
# ==============================================================

# Cambiar al directorio donde está este script
cd "$(dirname "$0")"

# Colores para los mensajes
VERDE='\033[0;32m'
ROJO='\033[0;31m'
AZUL='\033[0;34m'
NC='\033[0m' # Sin color

APP_NAME="DowP_Lite.app"

echo -e "${AZUL}==============================================${NC}"
echo -e "${AZUL}    Instalador de DowP Lite para macOS        ${NC}"
echo -e "${AZUL}==============================================${NC}"
echo ""
echo "Este instalador:"
echo " 1. Copiará DowP a tu carpeta de Aplicaciones (si no está allí)."
echo " 2. Eliminará el bloqueo de seguridad de macOS (Cuarentena)."
echo ""

# Verificar que la app está en la misma carpeta que el script
if [ ! -d "$APP_NAME" ]; then
    echo -e "${ROJO}⚠️ ERROR: No se encontró '$APP_NAME' en esta carpeta.${NC}"
    echo "Asegúrate de haber extraído todo el archivo ZIP y no separar este script de la aplicación."
    echo ""
    read -p "Presiona ENTER para salir..."
    exit 1
fi

echo "Se te pedirá tu contraseña de inicio de sesión de Mac para poder instalar:"
echo -e "${AZUL}(Las letras no se verán al escribir, es normal)${NC}"

# Pedir permisos de sudo por adelantado
sudo -v

# Mantener sudo activo mientras dure el script
while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &

echo ""
echo -e "${AZUL}➤ Instalando...${NC}"

# 1. Copiar la App a /Applications (Sobrescribiendo si existe)
echo "Copiando a Aplicaciones..."
sudo cp -R "$APP_NAME" "/Applications/"

# 2. Re-firmar la aplicación (Firma Ad-Hoc)
# Esto es vital para procesadores Apple Silicon (M1/M2/M3) donde se exige que
# toda app tenga al menos una firma básica local para no ser bloqueada o crashear.
echo "Aplicando firma digital local..."
sudo codesign --force --deep --sign - "/Applications/$APP_NAME"

# 3. Quitar el atributo de cuarentena
echo "Eliminando bloqueos de seguridad de macOS (Gatekeeper)..."
sudo xattr -rd com.apple.quarantine "/Applications/$APP_NAME"
sudo xattr -rd com.apple.macl "/Applications/$APP_NAME" 2>/dev/null

echo -e "${VERDE}==============================================${NC}"
echo -e "${VERDE}✅ INSTALACIÓN COMPLETADA EXITOSAMENTE!       ${NC}"
echo -e "${VERDE}==============================================${NC}"
echo ""
echo "Ya puedes abrir DowP Lite desde tu Launchpad o carpeta de Aplicaciones."
echo ""

# 4. Abrir la aplicación automáticamente
echo "Abriendo DowP Lite por primera vez..."
open "/Applications/$APP_NAME"

echo ""
read -p "Presiona ENTER para cerrar esta ventana..."
exit 0
