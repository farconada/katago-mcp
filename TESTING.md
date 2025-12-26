# Guía de Testing - KataGo MCP Server

## test_all_tools.py - Test Comprehensivo

Este script prueba todos los componentes del servidor MCP con logs detallados.

### Uso

```bash
cd ~/katago-mcp
source .venv/bin/activate
python test_all_tools.py 2>&1 | tee test_output.log
```

El script redirige **stderr** a **stdout** con `2>&1` para capturar los logs de debug de KataGo.

### Qué Prueba

El script valida 6 componentes en orden:

| # | Herramienta | Qué prueba | Requiere KataGo |
|---|-------------|------------|-----------------|
| 1 | `list_sgf_files` | Búsqueda de archivos SGF | No |
| 2 | `get_board_state` | Parser SGF + display ASCII | No |
| 3 | `analyze_position` | Comunicación con KataGo | Sí |
| 4 | `get_move_recommendation` | Análisis + formatting | Sí |
| 5 | `get_territory_analysis` | Ownership/territory | Sí |
| 6 | `evaluate_move` | Evaluación de movimientos | Sí |

### Interpretar los Resultados

#### Estado PASS (✓)

```
✓ get_board_state                PASS
```

La herramienta funciona correctamente. El test muestra:
- Datos de entrada
- Procesamiento
- Salida generada

#### Estado FAIL (✗)

```
✗ analyze_position               FAIL
```

La herramienta falló. El test muestra:
- Tipo de error
- Mensaje de error
- Stack trace completo

**Causas comunes**:
- Broken pipe → KataGo no está disponible o usa config incorrecta
- Timeout → Modelo muy grande, aumentar timeout
- JSON decode error → Respuesta de KataGo incorrecta

#### Estado SKIP (⊝)

```
⊝ get_move_recommendation        SKIP
```

Test saltado por dependencias no satisfechas (ej: KataGo no disponible).

### Ejemplo de Salida Exitosa

```
======================================================================
 Test 2: get_board_state
======================================================================

→ Finding latest SGF file
  ✓ Using: sample_game.sgf

→ Reading SGF file
  ✓ SGF parsed successfully

→ Extracting game information

  📄 Game Info:
    {
      "board_size": 19,
      "komi": 7.5,
      "rules": "chinese",
      ...
    }

→ Generating board display

  📄 Board State:
       A B C D E F G H J K L M N O P Q R S T
    19 . . . . . . . . . . . . . . . . . . . 19
    ...

  ✓ get_board_state functionality verified
```

### Ejemplo de Salida con Error

```
======================================================================
 Test 3: analyze_position
======================================================================

→ Checking KataGo configuration
    KataGo path: /usr/bin/katago
    Model path: /usr/share/katago/model.bin.gz
    Config path: /home/fernando/gtp.cfg

→ Creating KataGo client
  ✓ Client created

→ Starting KataGo process
  ✗ Failed: RuntimeError: KataGo process died (broken pipe)
     Recent stderr:
     Warning: Config file contains GTP-mode parameters
     Error: numAnalysisThreads not valid for GTP mode
```

Este output te dice exactamente el problema: estás usando `gtp.cfg` en vez de `analysis.cfg`.

## debug_katago.py - Debug Detallado

Para problemas más complejos, usa el script de debug:

```bash
python debug_katago.py 2>&1 | tee debug.log
```

Este script:
1. Habilita debug logging en KataGoClient
2. Muestra TODAS las queries enviadas
3. Muestra TODAS las respuestas recibidas  
4. Captura stderr de KataGo en tiempo real
5. Usa solo 10 visits para testing rápido

### Qué Buscar en el Debug Output

#### Query enviada

```
[KataGo] Sending query abc123: {"id":"abc123","moves":[["B","Q16"],["W","D4"]],...}
```

Verifica que:
- El JSON es válido
- Los movimientos están en formato correcto ([Color, GTPcoord])
- Las reglas y komi son correctos

#### Respuesta recibida

```
[KataGo stdout] {"id":"abc123","turnNumber":9,"moveInfos":[...]}
[KataGo] Received response for request abc123
```

Si ves esto, KataGo está funcionando.

#### No hay respuesta

```
[KataGo] Waiting up to 120s for response to abc123
... (silencio)
[KataGo] Timeout waiting for abc123
```

Causas:
1. KataGo no recibió la query (broken pipe antes de enviar)
2. KataGo está procesando pero tarda >120s
3. KataGo crasheó silenciosamente

#### Stderr de KataGo

```
[KataGo stderr] Loaded config /home/user/analysis.cfg
[KataGo stderr] Loaded model /path/to/model.bin.gz
[KataGo stderr] Model name: kata1-b28...
[KataGo stderr] GTP ready, beginning main protocol loop
```

**¡CUIDADO!**: Si ves "GTP ready", significa que estás usando una config de modo GTP, no analysis.
El modo analysis NO imprime "GTP ready".

### Ejemplo de Session Exitosa

```
[KataGo stderr] Loaded config analysis.cfg
[KataGo stderr] Loaded model kata1-b28...
[KataGo stderr] Starting analysis engine
[KataGo] Sending query abc123: {...}
[KataGo stdout] {"id":"abc123","turnNumber":9,...}
[KataGo] Received response for request abc123
[KataGo] Got response for abc123

SUCCESS: Got analysis result!
Win rate: 52.3%
Score lead: +1.2
Best move: R10
```

## test_setup.py - Verificación Inicial

Para verificar la instalación básica antes de probar las herramientas:

```bash
python test_setup.py
```

Valida:
- Dependencias Python instaladas
- Rutas de configuración correctas
- Archivos SGF disponibles
- KataGo ejecutable
- Servidor MCP importable

## Workflow de Debugging Recomendado

1. **Primera ejecución**: `python test_setup.py`
   - Verifica configuración básica
   - Identifica problemas de instalación

2. **Test de componentes**: `python test_all_tools.py`
   - Prueba cada herramienta
   - Identifica qué falla específicamente
   - Muestra output detallado

3. **Si hay broken pipe**: `python debug_katago.py 2>&1 | tee debug.log`
   - Debug completo de comunicación
   - Ve exactamente qué envía/recibe KataGo
   - Identifica si el problema es config, modelo, o query

4. **Revisar logs**: `less test_output.log` o `less debug.log`
   - Busca mensajes de error específicos
   - Verifica que las rutas son correctas
   - Confirma que usas `analysis.cfg`, no `gtp.cfg`

## Problemas Comunes y Sus Señales

### Config GTP en vez de Analysis

**Señal en debug**:
```
[KataGo stderr] GTP ready, beginning main protocol loop
[KataGo stderr] WARNING: Unused key 'numAnalysisThreads'
```

**Solución**: Cambia `KATAGO_CONFIG` a apuntar a `analysis.cfg`.

### Modelo muy Grande / Timeout

**Señal**:
```
→ Sending analysis query (maxVisits=10)
  (esperando...)
✗ Analysis returned None (timeout or error)
```

**Solución**: 
- Reduce `maxVisits` a 5
- Usa un modelo más pequeño (b6 o b10)
- O aumenta timeout en el código

### Query Format Incorrecto

**Señal en debug**:
```
[KataGo] Sending query: {...}
[KataGo stderr] Error parsing JSON query
[KataGo] Timeout waiting for response
```

**Solución**: Reporta el bug con el JSON exacto que falló.

## Logs que el Usuario Debe Compartir

Si necesitas ayuda debugging, comparte:

1. Output completo de `test_all_tools.py`
2. Si hay broken pipe, output de `debug_katago.py`
3. Tu configuración:
   - Versión de KataGo (`katago version`)
   - Nombre del modelo
   - Primer trozo de `analysis.cfg`

```bash
# Generar reporte completo
{
  echo "=== System Info ==="
  katago version
  echo
  echo "=== Config ==="
  head -30 ~/katago-mcp/analysis.cfg
  echo  
  echo "=== Test Output ==="
  python test_all_tools.py
} 2>&1 | tee full_report.log
```