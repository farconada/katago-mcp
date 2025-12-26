"""
SGF Reader module for parsing Go game files.

Uses sgfmill library for robust SGF parsing.
"""
import os
import glob
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass, field

try:
    from sgfmill import sgf, boards
except ImportError:
    raise ImportError("Please install sgfmill: pip install sgfmill")


@dataclass
class GameState:
    """Represents the current state of a Go game."""
    board_size: int = 19
    moves: List[Tuple[str, Optional[Tuple[int, int]]]] = field(default_factory=list)
    current_player: str = "B"  # B or W
    komi: float = 7.5
    rules: str = "chinese"
    black_captures: int = 0
    white_captures: int = 0
    board: List[List[Optional[str]]] = field(default_factory=list)
    
    # Game info
    black_player: str = "Black"
    white_player: str = "White"
    game_name: str = ""
    result: str = ""
    
    def __post_init__(self):
        if not self.board:
            self.board = [[None for _ in range(self.board_size)] for _ in range(self.board_size)]


def coord_to_sgf(row: int, col: int, board_size: int = 19) -> str:
    """Convert board coordinates to SGF format."""
    return chr(ord('a') + col) + chr(ord('a') + row)


def sgf_to_coord(sgf_point: str) -> Tuple[int, int]:
    """Convert SGF point to board coordinates (row, col)."""
    col = ord(sgf_point[0]) - ord('a')
    row = ord(sgf_point[1]) - ord('a')
    return (row, col)


def coord_to_gtp(row: int, col: int, board_size: int = 19) -> str:
    """Convert board coordinates to GTP format (e.g., 'D4', 'Q16')."""
    # GTP uses letters A-T (excluding I) for columns, 1-19 for rows from bottom
    letters = "ABCDEFGHJKLMNOPQRST"  # No 'I'
    return f"{letters[col]}{board_size - row}"


def gtp_to_coord(gtp_point: str, board_size: int = 19) -> Tuple[int, int]:
    """Convert GTP point to board coordinates (row, col)."""
    letters = "ABCDEFGHJKLMNOPQRST"
    col = letters.index(gtp_point[0].upper())
    row = board_size - int(gtp_point[1:])
    return (row, col)


def find_latest_sgf(directory: str) -> Optional[str]:
    """Find the most recently modified SGF file in a directory."""
    pattern = os.path.join(directory, "**", "*.sgf")
    sgf_files = glob.glob(pattern, recursive=True)
    
    if not sgf_files:
        return None
    
    # Sort by modification time, most recent first
    sgf_files.sort(key=os.path.getmtime, reverse=True)
    return sgf_files[0]


def read_sgf_file(filepath: str) -> GameState:
    """
    Read an SGF file and extract the game state.
    
    Args:
        filepath: Path to the SGF file
        
    Returns:
        GameState object with the current position
    """
    with open(filepath, 'rb') as f:
        game = sgf.Sgf_game.from_bytes(f.read())
    
    root = game.get_root()
    
    # Get board size
    board_size = game.get_size()
    
    # Get game info
    komi = 7.5
    try:
        komi = game.get_komi()
    except Exception:
        pass
    
    # Get player names
    black_player = "Black"
    white_player = "White"
    try:
        black_player = root.get("PB") or "Black"
    except Exception:
        pass
    try:
        white_player = root.get("PW") or "White"
    except Exception:
        pass
    
    # Get result if available
    result = ""
    try:
        result = root.get("RE") or ""
    except Exception:
        pass
    
    # Get rules
    rules = "chinese"
    try:
        ru = root.get("RU")
        if ru:
            rules = ru.lower()
    except Exception:
        pass
    
    # Initialize game state
    state = GameState(
        board_size=board_size,
        komi=komi,
        rules=rules,
        black_player=black_player,
        white_player=white_player,
        result=result,
    )
    
    # Create a board for tracking position
    board = boards.Board(board_size)
    
    # Handle setup stones (handicap, etc.)
    try:
        ab = root.get("AB")  # Add Black
        if ab:
            for point in ab:
                row, col = point
                board.play(row, col, 'b')
    except Exception:
        pass
    
    try:
        aw = root.get("AW")  # Add White
        if aw:
            for point in aw:
                row, col = point
                board.play(row, col, 'w')
    except Exception:
        pass
    
    # Walk through the main line and collect moves
    moves = []
    main_sequence = game.get_main_sequence()
    
    for node in main_sequence:
        color, move = node.get_move()
        if color is not None:
            if move is not None:
                sgfmill_row, col = move
                # Apply move to board (using sgfmill coordinates)
                try:
                    board.play(sgfmill_row, col, color)
                except Exception:
                    pass  # Illegal move in SGF, skip
                
                # Convert to our internal coordinate system (row 0 = top)
                # sgfmill uses row 0 = bottom, so invert
                internal_row = board_size - 1 - sgfmill_row
                moves.append((color.upper(), (internal_row, col)))
            else:
                # Pass
                moves.append((color.upper(), None))
    
    state.moves = moves
    
    # Determine current player
    if moves:
        last_color = moves[-1][0]
        state.current_player = "W" if last_color == "B" else "B"
    else:
        state.current_player = "B"
    
    # Convert board state
    # IMPORTANT: sgfmill uses row 0 = BOTTOM of board (Go row 1)
    # But our internal array uses row 0 = TOP (Go row 19)
    # So we need to flip: sgfmill row R becomes internal row (board_size - 1 - R)
    for sgfmill_row in range(board_size):
        for col in range(board_size):
            stone = board.get(sgfmill_row, col)
            # Invert row: sgfmill's bottom (row 0) becomes our top row in array
            internal_row = board_size - 1 - sgfmill_row
            if stone == 'b':
                state.board[internal_row][col] = 'B'
            elif stone == 'w':
                state.board[internal_row][col] = 'W'
            else:
                state.board[internal_row][col] = None
    
    return state


def board_to_ascii(state: GameState) -> str:
    """
    Convert the board state to ASCII art representation.
    
    Returns a string with the board, suitable for display.
    """
    size = state.board_size
    letters = "ABCDEFGHJKLMNOPQRST"[:size]  # No 'I' in Go
    
    lines = []
    lines.append(f"   {' '.join(letters)}")
    
    for row in range(size):
        row_num = size - row
        row_str = f"{row_num:2d} "
        for col in range(size):
            stone = state.board[row][col]
            if stone == 'B':
                row_str += "X "
            elif stone == 'W':
                row_str += "O "
            else:
                # Mark star points
                if is_star_point(row, col, size):
                    row_str += "+ "
                else:
                    row_str += ". "
        row_str += f"{row_num:2d}"
        lines.append(row_str)
    
    lines.append(f"   {' '.join(letters)}")
    
    return "\n".join(lines)


def is_star_point(row: int, col: int, size: int) -> bool:
    """Check if a position is a star point (hoshi)."""
    if size == 19:
        star_positions = [3, 9, 15]
    elif size == 13:
        star_positions = [3, 6, 9]
    elif size == 9:
        star_positions = [2, 4, 6]
    else:
        return False
    
    return row in star_positions and col in star_positions


def format_move_history(state: GameState, last_n: int = 10) -> str:
    """Format the last N moves as a readable string."""
    if not state.moves:
        return "No moves played yet."
    
    recent_moves = state.moves[-last_n:]
    start_num = len(state.moves) - len(recent_moves) + 1
    
    lines = []
    for i, (color, coord) in enumerate(recent_moves, start=start_num):
        if coord is None:
            move_str = "pass"
        else:
            move_str = coord_to_gtp(coord[0], coord[1], state.board_size)
        player = "Black" if color == "B" else "White"
        lines.append(f"{i}. {player}: {move_str}")
    
    return "\n".join(lines)


def format_stone_positions(state: GameState) -> str:
    """
    Format stone positions in an explicit, unambiguous format for LLM parsing.
    
    Returns:
        String listing all stones grouped by color with coordinates
    """
    black_stones = []
    white_stones = []
    
    # Collect all stone positions
    for row in range(state.board_size):
        for col in range(state.board_size):
            stone = state.board[row][col]
            if stone == 'B':
                coord = coord_to_gtp(row, col, state.board_size)
                black_stones.append(coord)
            elif stone == 'W':
                coord = coord_to_gtp(row, col, state.board_size)
                white_stones.append(coord)
    
    # Sort stones for consistent output
    black_stones.sort()
    white_stones.sort()
    
    lines = []
    lines.append("=== Explicit Stone Positions ===")
    lines.append("")
    
    # Black stones
    if black_stones:
        lines.append(f"BLACK STONES (X): {len(black_stones)} stones")
        # Group in lines of 10 for readability
        for i in range(0, len(black_stones), 10):
            group = black_stones[i:i+10]
            lines.append(f"  {', '.join(group)}")
    else:
        lines.append("BLACK STONES (X): None")
    
    lines.append("")
    
    # White stones
    if white_stones:
        lines.append(f"WHITE STONES (O): {len(white_stones)} stones")
        for i in range(0, len(white_stones), 10):
            group = white_stones[i:i+10]
            lines.append(f"  {', '.join(group)}")
    else:
        lines.append("WHITE STONES (O): None")
    
    return "\n".join(lines)


def get_game_info(state: GameState) -> Dict[str, Any]:
    """Get summary information about the game."""
    return {
        "board_size": state.board_size,
        "komi": state.komi,
        "rules": state.rules,
        "black_player": state.black_player,
        "white_player": state.white_player,
        "move_count": len(state.moves),
        "current_player": "Black" if state.current_player == "B" else "White",
        "result": state.result if state.result else "Game in progress",
    }