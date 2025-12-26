#!/usr/bin/env python3
"""
KataGo MCP Server - Connect Claude Desktop with KataGo for Go coaching.

This server exposes tools for:
- Reading current board state from SGF files
- Getting KataGo analysis (win rate, score, recommendations)
- Getting coaching-oriented explanations and move suggestions
"""
import os
import sys
from typing import Optional

from fastmcp import FastMCP

# Import our modules
from config import (
    KATAGO_PATH,
    KATAGO_MODEL,
    KATAGO_CONFIG,
    SGF_WATCH_PATH,
    ANALYSIS_VISITS,
    MAX_VARIATIONS,
    ANALYSIS_PV_LEN,
    INCLUDE_OWNERSHIP,
)
from sgf_reader import (
    find_latest_sgf,
    read_sgf_file,
    board_to_ascii,
    format_move_history,
    get_game_info,
    coord_to_gtp,
    GameState,
)
from katago_client import (
    KataGoClient,
    format_analysis_result,
    format_ownership_map,
)


# Initialize MCP server
mcp = FastMCP("KataGo Go Coach")

# Global KataGo client (lazy initialization)
_katago_client: Optional[KataGoClient] = None


def get_katago_client() -> KataGoClient:
    """Get or create the KataGo client."""
    global _katago_client
    if _katago_client is None:
        _katago_client = KataGoClient(
            katago_path=KATAGO_PATH,
            model_path=KATAGO_MODEL,
            config_path=KATAGO_CONFIG,
        )
        _katago_client.start()
    return _katago_client


def get_current_game() -> tuple[GameState, str]:
    """
    Get the current game state from the most recent SGF file.
    
    Returns:
        Tuple of (GameState, filepath)
    """
    sgf_path = find_latest_sgf(SGF_WATCH_PATH)
    if sgf_path is None:
        raise FileNotFoundError(
            f"No SGF files found in {SGF_WATCH_PATH}. "
            "Please save your game in Sabaki first."
        )
    
    state = read_sgf_file(sgf_path)
    return state, sgf_path


def format_stone_positions(state: GameState) -> str:
    """
    Format the explicit stone positions in a clear, LLM-friendly format.
    
    Returns a string listing all black and white stones on the board.
    """
    black_stones = []
    white_stones = []
    
    for row in range(state.board_size):
        for col in range(state.board_size):
            stone = state.board[row][col]
            if stone == 'B':
                black_stones.append(coord_to_gtp(row, col, state.board_size))
            elif stone == 'W':
                white_stones.append(coord_to_gtp(row, col, state.board_size))
    
    lines = []
    lines.append("=== Stone Positions ===")
    lines.append(f"Black stones ({len(black_stones)}): {', '.join(black_stones) if black_stones else 'none'}")
    lines.append(f"White stones ({len(white_stones)}): {', '.join(white_stones) if white_stones else 'none'}")
    
    return "\n".join(lines)


# ============================================================================
# MCP Prompts - Conversation starters for Go learning
# ============================================================================

@mcp.prompt()
def enseñanza_principiante() -> str:
    """Activa el modo de enseñanza para principiantes de Go.
    
    Este prompt configura a Claude como un profesor de Go paciente y didáctico.
    """
    return """Eres un profesor experimentado del juego de Go (Baduk/Weiqi). Tu estudiante es principiante y necesita explicaciones claras y sencillas.

Tu enfoque de enseñanza debe ser:

1. **Vocabulario Simple**: Evita jerga técnica sin explicarla. Cuando uses términos de Go (como "influencia", "territorio", "aji", "kikashi"), explica qué significan con ejemplos.

2. **Didáctico y Paciente**: 
   - Explica el "por qué" detrás de cada concepto
   - Usa analogías cuando sea útil
   - No asumas conocimientos previos
   - Repite conceptos importantes de diferentes formas

3. **Estrategia Fundamental**:
   - Prioriza conceptos básicos: vida y muerte de grupos, territorio vs influencia
   - Explica el balance entre atacar y defender
   - Enseña a identificar puntos grandes del tablero
   - Muestra cómo pensar en términos de toda la partida, no solo movimientos locales

4. **Retroalimentación Constructiva**:
   - Cuando analices movimientos, señala tanto aciertos como errores
   - Explica qué habría sido mejor y por qué
   - Conecta cada movimiento con principios estratégicos

5. **Progresión del Aprendizaje**:
   - Empieza con conceptos simples antes de avanzar
   - Relaciona nuevos conceptos con lo ya aprendido
   - Anima al estudiante a pensar antes de dar la respuesta

Usa las herramientas MCP disponibles para:
- Mostrar el tablero actual
- Analizar posiciones
- Evaluar movimientos
- Recomendar jugadas con explicación

Tu objetivo es ayudar al estudiante a mejorar su comprensión del Go, no solo a ganar esta partida."""


@mcp.prompt()
def explicar_jugada(numero_movimiento: str = "última") -> str:
    """Solicita una explicación detallada de una jugada específica.
    
    Args:
        numero_movimiento: Qué movimiento explicar (ej: "5", "última", "anterior")
    """
    return f"""Analiza y explica la jugada número {numero_movimiento} de la partida actual.

Para tu explicación, considera:

1. **Propósito del Movimiento**:
   - ¿Qué intenta lograr este movimiento?
   - ¿Es defensivo, ofensivo, o de desarrollo?

2. **Análisis Táctico**:
   - ¿El movimiento cumple su propósito?
   - ¿Hay debilidades inmediatas que crea?
   - ¿Qué amenazas genera o previene?

3. **Contexto Estratégico**:
   - ¿Cómo afecta al balance de territorio e influencia?
   - ¿Es el punto más grande del tablero en este momento?
   - ¿Cómo se relaciona con la estrategia general de la partida?

4. **Alternativas**:
   - ¿Qué otros movimientos eran posibles?
   - ¿Por qué el movimiento jugado es mejor o peor que las alternativas?

5. **Lecciones de Aprendizaje**:
   - ¿Qué principio de Go ilustra este movimiento?
   - ¿Qué puede aprender el estudiante de esta situación?

Usa las herramientas MCP para:
- Obtener el estado del tablero (`get_board_state`)
- Evaluar el movimiento (`evaluate_move`)
- Comparar con las mejores opciones (`analyze_position`)

Presenta la explicación de forma clara y estructurada, usando vocabulario sencillo adecuado para principiantes."""


@mcp.prompt()
def analizar_situacion() -> str:
    """Solicita un análisis completo de la situación actual del tablero.
    
    Analiza la posición actual, perspectivas de cada jugador, y oportunidades de mejora.
    """
    return """Realiza un análisis completo de la situación actual del tablero de Go.

Tu análisis debe cubrir:

1. **Evaluación General de la Posición**:
   - ¿Quién va ganando y por cuánto?
   - ¿Cuál es el balance de territorio e influencia?
   - ¿Hay grupos en peligro?

2. **Análisis por Zonas del Tablero**:
   - Esquinas: ¿Están definidas? ¿Quién las controla?
   - Laterales: ¿Hay oportunidades de invasión o extensión?
   - Centro: ¿Quién tiene más influencia?

3. **Grupos Críticos**:
   - Identifica grupos débiles que necesitan atención
   - Señala grupos fuertes que pueden usarse para atacar
   - Explica qué grupos tienen buena forma vs mala forma

4. **Perspectivas de Cada Jugador**:
   - ¿Qué objetivos debería tener el negro?
   - ¿Qué objetivos debería tener el blanco?
   - ¿Cuáles son los puntos grandes pendientes?

5. **Análisis de Movimientos Recientes**:
   - ¿Las últimas 3-5 jugadas fueron buenas?
   - ¿Qué oportunidades se perdieron?
   - ¿Qué se podría haber mejorado?

6. **Recomendaciones para Adelante**:
   - ¿Cuáles son las prioridades ahora?
   - ¿Qué tipo de movimientos debería considerar el jugador?
   - ¿Hay alguna urgencia táctica?

Usa estas herramientas MCP:
- `get_board_state` - Ver el tablero actual
- `analyze_position` - Evaluación de KataGo
- `get_territory_analysis` - Análisis de territorio
- `get_move_recommendation` - Mejores movimientos

Presenta el análisis de forma estructurada y educativa, explicando conceptos para que el estudiante aprenda, no solo reciba respuestas."""


# ============================================================================
# MCP Tools
# ============================================================================

@mcp.tool()
def get_board_state(sgf_path: Optional[str] = None) -> str:
    """
    Get the current board state from the Go game.
    
    Shows the board position, recent moves, and game information.
    If no path is provided, uses the most recently modified SGF file.
    
    Args:
        sgf_path: Optional path to a specific SGF file
        
    Returns:
        ASCII representation of the board with game info
    """
    try:
        if sgf_path:
            state = read_sgf_file(sgf_path)
            filepath = sgf_path
        else:
            state, filepath = get_current_game()
        
        # Build response
        lines = []
        lines.append(f"=== Current Game State ===")
        lines.append(f"File: {os.path.basename(filepath)}")
        lines.append("")
        
        # Game info
        info = get_game_info(state)
        lines.append(f"Black: {info['black_player']}")
        lines.append(f"White: {info['white_player']}")
        lines.append(f"Board: {info['board_size']}x{info['board_size']}")
        lines.append(f"Komi: {info['komi']}")
        lines.append(f"Rules: {info['rules']}")
        lines.append(f"Move: {info['move_count']}")
        lines.append(f"Turn: {info['current_player']} to play")
        if info['result'] != "Game in progress":
            lines.append(f"Result: {info['result']}")
        lines.append("")
        
        # Board
        lines.append(board_to_ascii(state))
        lines.append("")
        
        # Explicit stone positions (LLM-friendly)
        lines.append(format_stone_positions(state))
        lines.append("")
        
        # Recent moves
        lines.append("=== Recent Moves ===")
        lines.append(format_move_history(state, last_n=10))
        
        return "\n".join(lines)
        
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        return f"Error reading game state: {e}"


@mcp.tool()
def analyze_position(
    max_visits: int = ANALYSIS_VISITS,
    sgf_path: Optional[str] = None
) -> str:
    """
    Run KataGo analysis on the current position.
    
    Returns win rate, score estimation, and top recommended moves
    with principal variations.
    
    Args:
        max_visits: Analysis depth (more visits = stronger analysis, slower)
        sgf_path: Optional path to a specific SGF file
        
    Returns:
        Detailed analysis with win rates and move recommendations
    """
    try:
        if sgf_path:
            state = read_sgf_file(sgf_path)
        else:
            state, _ = get_current_game()
        
        client = get_katago_client()
        result = client.analyze_position(
            state,
            max_visits=max_visits,
            include_ownership=INCLUDE_OWNERSHIP,
            analysis_pv_len=ANALYSIS_PV_LEN,
        )
        
        if result is None:
            return "Error: KataGo analysis timed out or failed"
        
        # Format the analysis
        output = []
        output.append(format_analysis_result(result, state, top_n=MAX_VARIATIONS))
        
        # Add territory map if available
        if result.ownership and INCLUDE_OWNERSHIP:
            output.append("")
            output.append(format_ownership_map(result.ownership, state.board_size))
        
        return "\n".join(output)
        
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        return f"Error analyzing position: {e}"


@mcp.tool()
def get_move_recommendation(
    explain_for_level: str = "intermediate",
    sgf_path: Optional[str] = None
) -> str:
    """
    Get a move recommendation with explanation suitable for learning.
    
    Provides the best move with an explanation of why it's good,
    tailored to the player's level.
    
    Args:
        explain_for_level: Player level - "beginner", "intermediate", or "advanced"
        sgf_path: Optional path to a specific SGF file
        
    Returns:
        Move recommendation with teaching-oriented explanation
    """
    try:
        if sgf_path:
            state = read_sgf_file(sgf_path)
        else:
            state, _ = get_current_game()
        
        client = get_katago_client()
        result = client.analyze_position(
            state,
            max_visits=ANALYSIS_VISITS,
            include_ownership=True,
            analysis_pv_len=ANALYSIS_PV_LEN,
        )
        
        if result is None:
            return "Error: Analysis failed"
        
        if not result.move_infos:
            return "No moves available (game may be over)"
        
        # Get top moves
        top_moves = result.move_infos[:3]
        best = top_moves[0]
        
        current = "Black" if result.current_player == "B" else "White"
        winrate_pct = result.root_winrate * 100
        
        lines = []
        lines.append(f"=== Move Recommendation for {current} ===")
        lines.append("")
        
        # Current assessment
        if winrate_pct > 55:
            assessment = "You're in a good position!"
        elif winrate_pct < 45:
            assessment = "The position is difficult, but there's still hope."
        else:
            assessment = "The game is close."
        
        lines.append(f"Position assessment: {assessment}")
        lines.append(f"Win probability: {winrate_pct:.0f}%")
        lines.append("")
        
        # Best move recommendation
        lines.append(f"📍 Recommended move: {best.move}")
        lines.append(f"   Expected win rate after: {best.winrate * 100:.0f}%")
        lines.append(f"   Score change: {best.score_lead:+.1f} points")
        lines.append("")
        
        # Show the expected continuation
        if best.pv:
            lines.append("Expected sequence:")
            pv_display = best.pv[:6]
            for i, move in enumerate(pv_display, 1):
                who = current if i % 2 == 1 else ("White" if current == "Black" else "Black")
                lines.append(f"   {i}. {who}: {move}")
        lines.append("")
        
        # Alternative moves
        if len(top_moves) > 1:
            lines.append("Alternative moves to consider:")
            for mi in top_moves[1:]:
                wr_diff = (mi.winrate - best.winrate) * 100
                lines.append(f"   • {mi.move} (win rate: {mi.winrate * 100:.0f}%, {wr_diff:+.0f}% compared to best)")
        
        # Level-appropriate advice
        lines.append("")
        if explain_for_level == "beginner":
            lines.append("💡 Tip: Focus on making solid moves that secure territory or keep your groups connected.")
        elif explain_for_level == "intermediate":
            lines.append("💡 Tip: Consider the balance between territory and influence. The best move often addresses the biggest point on the board.")
        else:
            lines.append("💡 Tip: Evaluate the whole-board position and consider aji (potential) in your moves.")
        
        return "\n".join(lines)
        
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        return f"Error getting recommendation: {e}"


@mcp.tool()
def get_territory_analysis(sgf_path: Optional[str] = None) -> str:
    """
    Get a territory/influence analysis of the current position.
    
    Shows which areas of the board each player controls or has influence over.
    
    Args:
        sgf_path: Optional path to a specific SGF file
        
    Returns:
        Territory map and analysis
    """
    try:
        if sgf_path:
            state = read_sgf_file(sgf_path)
        else:
            state, _ = get_current_game()
        
        client = get_katago_client()
        result = client.analyze_position(
            state,
            max_visits=ANALYSIS_VISITS,
            include_ownership=True,
        )
        
        if result is None:
            return "Error: Analysis failed"
        
        lines = []
        lines.append(f"=== Territory Analysis (Move {len(state.moves)}) ===")
        lines.append("")
        
        # Score estimation
        score = result.root_score_lead
        if result.current_player == "B":
            if score > 0:
                lines.append(f"Estimated score: Black leads by {score:.1f} points")
            elif score < 0:
                lines.append(f"Estimated score: White leads by {abs(score):.1f} points")
            else:
                lines.append(f"Estimated score: Even")
        else:
            if score > 0:
                lines.append(f"Estimated score: White leads by {score:.1f} points")
            elif score < 0:
                lines.append(f"Estimated score: Black leads by {abs(score):.1f} points")
            else:
                lines.append(f"Estimated score: Even")
        
        lines.append("")
        
        # Territory map
        if result.ownership:
            lines.append(format_ownership_map(result.ownership, state.board_size))
            lines.append("")
            lines.append("Legend:")
            lines.append("  B = Strong Black territory")
            lines.append("  b = Likely Black territory")
            lines.append("  W = Strong White territory")
            lines.append("  w = Likely White territory")
            lines.append("  . = Neutral / contested")
        else:
            lines.append("Territory map not available")
        
        return "\n".join(lines)
        
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        return f"Error analyzing territory: {e}"


@mcp.tool()
def evaluate_move(
    move: str,
    sgf_path: Optional[str] = None
) -> str:
    """
    Evaluate a specific move to see if it's good or bad.
    
    Compares the suggested move against KataGo's top recommendations.
    
    Args:
        move: The move to evaluate in GTP format (e.g., "Q16", "D4", "pass")
        sgf_path: Optional path to a specific SGF file
        
    Returns:
        Evaluation of the move compared to the best options
    """
    try:
        if sgf_path:
            state = read_sgf_file(sgf_path)
        else:
            state, _ = get_current_game()
        
        client = get_katago_client()
        result = client.analyze_position(
            state,
            max_visits=ANALYSIS_VISITS,
            include_ownership=False,
        )
        
        if result is None:
            return "Error: Analysis failed"
        
        move_upper = move.upper().strip()
        
        # Find the move in analysis
        found_move = None
        for mi in result.move_infos:
            if mi.move.upper() == move_upper:
                found_move = mi
                break
        
        best = result.move_infos[0] if result.move_infos else None
        
        lines = []
        lines.append(f"=== Evaluation of {move_upper} ===")
        lines.append("")
        
        current = "Black" if result.current_player == "B" else "White"
        lines.append(f"For: {current}")
        lines.append("")
        
        if best:
            lines.append(f"Best move according to KataGo: {best.move}")
            lines.append(f"Best move win rate: {best.winrate * 100:.1f}%")
            lines.append("")
        
        if found_move:
            rank = result.move_infos.index(found_move) + 1
            lines.append(f"Your move {move_upper}:")
            lines.append(f"  Rank: #{rank} out of {len(result.move_infos)} considered moves")
            lines.append(f"  Win rate: {found_move.winrate * 100:.1f}%")
            lines.append(f"  Score: {found_move.score_lead:+.1f}")
            
            if best:
                wr_diff = (found_move.winrate - best.winrate) * 100
                score_diff = found_move.score_lead - best.score_lead
                
                lines.append("")
                if wr_diff > -1:
                    lines.append(f"✅ Excellent choice! This is one of the best moves.")
                elif wr_diff > -3:
                    lines.append(f"👍 Good move! Only slightly suboptimal ({wr_diff:+.1f}% win rate difference)")
                elif wr_diff > -7:
                    lines.append(f"⚠️ Decent move, but there are better options ({wr_diff:+.1f}% win rate difference)")
                else:
                    lines.append(f"❌ This move loses significant value ({wr_diff:+.1f}% win rate difference)")
                    lines.append(f"   Consider {best.move} instead")
        else:
            lines.append(f"⚠️ Move {move_upper} was not in KataGo's top candidates.")
            lines.append("This might be a mistake, or the position requires deeper analysis.")
            if best:
                lines.append(f"Consider: {best.move} (win rate: {best.winrate * 100:.1f}%)")
        
        return "\n".join(lines)
        
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        return f"Error evaluating move: {e}"


@mcp.tool()
def list_sgf_files() -> str:
    """
    List available SGF files in the watch directory.
    
    Shows all SGF files that can be analyzed, ordered by modification time.
    
    Returns:
        List of SGF files with their paths
    """
    import glob
    
    pattern = os.path.join(SGF_WATCH_PATH, "**", "*.sgf")
    sgf_files = glob.glob(pattern, recursive=True)
    
    if not sgf_files:
        return f"No SGF files found in {SGF_WATCH_PATH}"
    
    # Sort by modification time
    sgf_files.sort(key=os.path.getmtime, reverse=True)
    
    lines = []
    lines.append(f"=== SGF Files in {SGF_WATCH_PATH} ===")
    lines.append("")
    
    for i, filepath in enumerate(sgf_files[:20], 1):  # Show max 20
        mtime = os.path.getmtime(filepath)
        from datetime import datetime
        dt = datetime.fromtimestamp(mtime)
        relative = os.path.relpath(filepath, SGF_WATCH_PATH)
        lines.append(f"{i}. {relative}")
        lines.append(f"   Modified: {dt.strftime('%Y-%m-%d %H:%M')}")
    
    if len(sgf_files) > 20:
        lines.append(f"\n... and {len(sgf_files) - 20} more files")
    
    return "\n".join(lines)


# ============================================================================
# Main entry point
# ============================================================================

if __name__ == "__main__":
    # Run the MCP server
    mcp.run()