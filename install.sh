#!/usr/bin/env bash
#
# Instala Boiler a nivel global:
#   1. Crea el venv del repo e instala dependencias.
#   2. Enlaza `boiler` en /usr/local/bin (o ~/.local/bin como fallback).
#
# Después: `boiler init` en cualquier carpeta (vacía o con proyectos).
set -euo pipefail
cd "$(dirname "$0")"

echo "→ Entorno virtual + dependencias…"
[ -d .venv ] || python3 -m venv .venv
./.venv/bin/pip install -q -r requirements.txt

TARGET="/usr/local/bin/boiler"
if ln -sf "$PWD/bin/boiler" "$TARGET" 2>/dev/null; then
  echo "✓ Instalado: $TARGET"
else
  mkdir -p "$HOME/.local/bin"
  ln -sf "$PWD/bin/boiler" "$HOME/.local/bin/boiler"
  echo "✓ Instalado: ~/.local/bin/boiler"
  case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) echo "  ⚠ Agrega a tu ~/.zshrc:  export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
  esac
fi

echo
echo "Listo. Prueba:"
echo "  cd /alguna/carpeta && boiler init"
echo "  boiler hub"
