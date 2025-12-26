# Guía de Solución de Problemas - KataGo MCP Server

## Error: "[Errno 32] Broken pipe"

Este error ocurre cuando el proceso de KataGo se cierra inesperadamente. Causas comunes:

### 1. KataGo no está instalado o la ruta es incorrecta

**Síntomas**:
- Error inmediato al usar cualquier herramienta de análisis
- Mensaje: "KataGo executable not found"

**Solución**:
```bash
# Verificar que KataGo está instalado
which katago
# O si está en otra ruta:
/ruta/a/katago version

# Actualizar la ruta en Claude Desktop config
{
  "env": {
    "KATAGO_PATH": "/ruta/correcta/a/katago"
  }
}
```

### 2. El modelo no existe o la ruta es incorrecta

**Síntomas**:
- Error: "KataGo model not found"
- KataGo no puede iniciar

**Solución**:
```bash
# Verificar que el modelo existe
ls -la /ruta/a/tu/modelo.bin.gz

# Actualizar en Claude Desktop config
{
  "env": {
    "KATAGO_MODEL": "/ruta/correcta/a/modelo.bin.gz"
  }
}
```

### 3. Configuración de análisis incompatible

**Síntomas**:
- KataGo se inicia pero se cierra inmediatamente
- Mensaje en stderr sobre parámetros no válidos

**Solución**:

Usa la configuración de análisis incluida:

```json
{
  "env": {
    "KATAGO_CONFIG": "/home/usuario/katago-mcp/analysis.cfg"
  }
}
```

O crea una configuración minimalista:

```ini
# minimal_analysis.cfg
numAnalysisThreads = 2
maxVisits = 100
logSearchInfo = false
logToStderr = false
```

### 4. Permisos insuficientes

**Síntomas**:
- Error de permisos al ejecutar KataGo

**Solución**:
```bash
# Dar permisos de ejecución
chmod +x /ruta/a/katago
```

### 5. GPU no disponible o drivers incorrectos

**Síntomas**:
- KataGo se cierra cuando intenta usar CUDA
- Mensaje sobre CUDA no disponible

**Soluciones**:

Opción A - Forzar CPU:
```bash
# Descargar versión CPU de KataGo
# O usar configuración sin CUDA
```

Opción B - Verificar drivers:
```bash
# Verificar que CUDA funciona
nvidia-smi

# Verificar drivers NVIDIA
nvidia-smi --query-gpu=driver_version --format=csv
```

## Tablero mostrado al revés

**Síntomas**:
- Claude piensa que las piedras en F2 están en F18
- El tablero ASCII está invertido verticalmente

**Solución**:
- Este problema fue corregido en el commit 8
- Asegúrate de tener la última versión de `sgf_reader.py`
- La corrección invierte las coordenadas de sgfmill al sistema interno

## Claude no ve las herramientas MCP

**Síntomas**:
- Claude no responde a preguntas sobre Go
- No hay herramientas disponibles

**Solución**:

1. Verificar configuración de Claude Desktop:
```bash
# Linux
cat ~/.config/Claude/claude_desktop_config.json

# Verificar que el JSON es válido
python3 -m json.tool ~/.config/Claude/claude_desktop_config.json
```

2. Verificar rutas absolutas:
```json
{
  "mcpServers": {
    "katago": {
      "command": "/home/USUARIO/katago-mcp/.venv/bin/python",
      "args": ["/home/USUARIO/katago-mcp/server.py"]
    }
  }
}
```

3. Reiniciar Claude Desktop completamente:
```bash
# Cerrar Claude Desktop
pkill -f Claude

# Abrir de nuevo
```

4. Verificar logs de Claude Desktop:
```bash
# Los logs suelen estar en:
tail -f ~/.config/Claude/logs/mcp*.log
```

## No encuentra archivos SGF

**Síntomas**:
- Error: "No SGF files found in ..."

**Solución**:

1. Verificar que el directorio existe:
```bash
ls -la ~/go/games
```

2. Guardar un SGF desde Sabaki:
- Archivo → Guardar Como...
- Navegar a `~/go/games`
- Guardar con cualquier nombre

3. Verificar permisos:
```bash
# El directorio debe ser legible
chmod 755 ~/go/games
```

## El análisis es muy lento

**Síntomas**:
- Las herramientas tardan mucho en responder
- Timeout errors

**Soluciones**:

1. Reducir la profundidad de análisis:
```bash
export ANALYSIS_VISITS=50  # Más rápido, menos preciso
```

2. Usar un modelo más pequeño:
```bash
# b6c96 es mucho más rápido que b18
export KATAGO_MODEL=/ruta/a/modelo_b6.bin.gz
```

3. Verificar que KataGo usa GPU:
```bash
# En analysis.cfg, asegúrate de tener:
cudaDeviceToUse = 0
cudaUseFP16 = true
```

## Debugging avanzado

### Ver logs de KataGo

```bash
# Ejecutar KataGo manualmente para ver errores
cd ~/katago-mcp
source .venv/bin/activate

python3 << 'EOF'
from config import KATAGO_PATH, KATAGO_MODEL, KATAGO_CONFIG
from katago_client import KataGoClient

client = KataGoClient(KATAGO_PATH, KATAGO_MODEL, KATAGO_CONFIG)
try:
    client.start()
    print("KataGo started successfully")
    input("Press Enter to stop...")
finally:
    client.stop()
EOF
```

### Verificar que el servidor MCP carga

```bash
# Test mínimo
python3 -c "from server import mcp; print(f'Server: {mcp.name}')"
```

### Test de integración completa

```bash
# Ejecutar test completo
python3 test_all_tools.py
```

## Contacto

Si ninguna de estas soluciones funciona, revisa:
1. Versión de Python (debe ser 3.10+)
2. Versión de KataGo (recomendado 1.13+)
3. Versión de FastMCP (latest)
4. Logs de Claude Desktop para mensajes de error específicos