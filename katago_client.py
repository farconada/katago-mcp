"""
KataGo Analysis Engine Client.

Communicates with KataGo using the Analysis Engine JSON protocol.
"""
import json
import os
import sys
import subprocess
import threading
import queue
import uuid
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

from sgf_reader import GameState, coord_to_gtp, gtp_to_coord


@dataclass
class MoveInfo:
    """Information about a candidate move from KataGo analysis."""
    move: str  # GTP format (e.g., "Q16")
    visits: int
    winrate: float  # 0 to 1
    score_lead: float  # Positive = good for current player
    pv: List[str]  # Principal variation
    prior: float = 0.0  # Policy prior
    utility: float = 0.0


@dataclass  
class AnalysisResult:
    """Result of KataGo position analysis."""
    id: str
    turn_number: int
    current_player: str
    
    # Root position stats
    root_winrate: float
    root_score_lead: float
    root_visits: int
    
    # Top moves
    move_infos: List[MoveInfo] = field(default_factory=list)
    
    # Territory ownership (-1 to 1, negative = white)
    ownership: Optional[List[float]] = None
    
    # Raw response for debugging
    raw_response: Optional[Dict] = None


class KataGoClient:
    """Client for communicating with KataGo analysis engine."""
    
    def __init__(
        self,
        katago_path: str,
        model_path: str,
        config_path: str,
        analysis_threads: int = 2,
        debug: bool = False
    ):
        self.katago_path = katago_path
        self.model_path = model_path
        self.config_path = config_path
        self.analysis_threads = analysis_threads
        self.debug = debug
        
        self.process: Optional[subprocess.Popen] = None
        self.response_queue: queue.Queue = queue.Queue()
        self.pending_requests: Dict[str, threading.Event] = {}
        self.responses: Dict[str, Dict] = {}
        self._reader_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._startup_error: Optional[str] = None
        self._stderr_lines: List[str] = []
        
    def start(self) -> None:
        """Start the KataGo analysis engine process."""
        if self.process is not None and self.process.poll() is None:
            return
            
        self._startup_error = None
        
        if not os.path.exists(self.katago_path):
            self._startup_error = f"KataGo executable not found: {self.katago_path}"
            raise FileNotFoundError(self._startup_error)
            
        if not os.path.exists(self.model_path):
            self._startup_error = f"KataGo model not found: {self.model_path}"
            raise FileNotFoundError(self._startup_error)
        
        cmd = [
            self.katago_path,
            "analysis",
            "-model", self.model_path,
            "-config", self.config_path,
            "-analysis-threads", str(self.analysis_threads),
        ]
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            self._startup_error = f"Failed to start KataGo: {e}"
            raise RuntimeError(self._startup_error) from e
        
        import time
        time.sleep(0.5)
        
        if self.process.poll() is not None:
            stderr_output = self.process.stderr.read() if self.process.stderr else ""
            self._startup_error = f"KataGo process died immediately. Stderr: {stderr_output}"
            raise RuntimeError(self._startup_error)
        
        self._reader_thread = threading.Thread(target=self._read_responses, daemon=True)
        self._reader_thread.start()
        
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stderr_thread.start()
        
    def _read_stderr(self) -> None:
        """Background thread to read stderr from KataGo."""
        while self.process and self.process.stderr:
            try:
                line = self.process.stderr.readline()
                if not line:
                    break
                line = line.strip()
                if line and self.debug:
                    print(f"[KataGo stderr] {line}", file=sys.stderr)
                self._stderr_lines.append(line)
            except Exception:
                break
    
    def _is_alive(self) -> bool:
        """Check if the KataGo process is alive."""
        return self.process is not None and self.process.poll() is None
        
    def stop(self) -> None:
        """Stop the KataGo process."""
        if self.process is not None:
            self.process.terminate()
            self.process.wait()
            self.process = None
            
    def _read_responses(self) -> None:
        """Background thread to read responses from KataGo."""
        while self.process and self.process.stdout:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break
                    
                line = line.strip()
                if not line:
                    continue
                
                if self.debug:
                    print(f"[KataGo stdout] {line[:200]}...", file=sys.stderr)
                    
                try:
                    response = json.loads(line)
                    request_id = response.get("id")
                    
                    if self.debug:
                        print(f"[KataGo] Received response for request {request_id}", file=sys.stderr)
                    
                    if request_id:
                        with self._lock:
                            self.responses[request_id] = response
                            if request_id in self.pending_requests:
                                self.pending_requests[request_id].set()
                                
                except json.JSONDecodeError as e:
                    if self.debug:
                        print(f"[KataGo] JSON decode error: {e}", file=sys.stderr)
                    continue
                    
            except Exception as e:
                if self.debug:
                    print(f"[KataGo] Reader exception: {e}", file=sys.stderr)
                break
                
    def _send_query(self, query: Dict) -> str:
        """Send a query to KataGo and return the request ID."""
        if not self._is_alive():
            self.start()
        
        if not self._is_alive():
            raise RuntimeError(f"KataGo process failed to start: {self._startup_error}")
            
        request_id = query.get("id", str(uuid.uuid4()))
        query["id"] = request_id
        
        event = threading.Event()
        with self._lock:
            self.pending_requests[request_id] = event
            
        query_json = json.dumps(query)
        
        if self.debug:
            print(f"[KataGo] Sending query {request_id}: {query_json[:200]}...", file=sys.stderr)
        
        try:
            self.process.stdin.write(query_json + "\n")
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            stderr_output = "\n".join(self._stderr_lines[-20:]) if self._stderr_lines else ""
            
            error_msg = f"KataGo process died (broken pipe). Recent stderr:\n{stderr_output}"
            with self._lock:
                if request_id in self.pending_requests:
                    del self.pending_requests[request_id]
            raise RuntimeError(error_msg) from e
        
        return request_id
        
    def _wait_for_response(self, request_id: str, timeout: float = 120.0) -> Optional[Dict]:
        """Wait for a response to a specific request. Default timeout increased to 120s for large models."""
        event = self.pending_requests.get(request_id)
        if event is None:
            return None
        
        if self.debug:
            print(f"[KataGo] Waiting up to {timeout}s for response to {request_id}", file=sys.stderr)
            
        if event.wait(timeout=timeout):
            with self._lock:
                response = self.responses.pop(request_id, None)
                if self.debug:
                    if response:
                        print(f"[KataGo] Got response for {request_id}", file=sys.stderr)
                    else:
                        print(f"[KataGo] No response found for {request_id} (event was set but no data)", file=sys.stderr)
                return response
        
        if self.debug:
            print(f"[KataGo] Timeout waiting for {request_id}", file=sys.stderr)
        
        return None
        
    def analyze_position(
        self,
        state: GameState,
        max_visits: int = 100,
        include_ownership: bool = True,
        include_policy: bool = False,
        analysis_pv_len: int = 10,
    ) -> Optional[AnalysisResult]:
        """
        Analyze a position and return the analysis result.
        
        Args:
            state: Current game state
            max_visits: Maximum MCTS visits for analysis
            include_ownership: Include territory ownership estimates
            include_policy: Include raw policy network output
            analysis_pv_len: Length of principal variations to return
            
        Returns:
            AnalysisResult with analysis data, or None if failed
        """
        query = self._build_query(
            state, 
            max_visits=max_visits,
            include_ownership=include_ownership,
            include_policy=include_policy,
            analysis_pv_len=analysis_pv_len,
        )
        
        if self.debug:
            print(f"[KataGo] Built query: {json.dumps(query, indent=2)}", file=sys.stderr)
        
        request_id = self._send_query(query)
        response = self._wait_for_response(request_id, timeout=120.0)
        
        if response is None:
            stderr_tail = "\n".join(self._stderr_lines[-10:]) if self._stderr_lines else "(no stderr)"
            if self.debug:
                print(f"[KataGo] Analysis failed. Recent stderr:\n{stderr_tail}", file=sys.stderr)
            return None
            
        return self._parse_response(response, state)
        
    def _build_query(
        self,
        state: GameState,
        max_visits: int = 100,
        include_ownership: bool = True,
        include_policy: bool = False,
        analysis_pv_len: int = 10,
    ) -> Dict:
        """Build a KataGo analysis query from game state."""
        
        # Convert moves to KataGo format
        moves = []
        for color, coord in state.moves:
            if coord is None:
                move_str = "pass"
            else:
                move_str = coord_to_gtp(coord[0], coord[1], state.board_size)
            moves.append([color, move_str])
        
        # Build initial stones from any setup in position
        # (For simplicity, we're assuming all stones come from moves)
        initial_stones = []
        
        # Map rules
        rules_map = {
            "chinese": "chinese",
            "japanese": "japanese", 
            "korean": "korean",
            "aga": "aga",
            "nz": "nz",
            "tromp-taylor": "tromp-taylor",
            "stone-scoring": "stone-scoring",
        }
        rules = rules_map.get(state.rules.lower(), "chinese")
        
        query = {
            "id": str(uuid.uuid4()),
            "moves": moves,
            "initialStones": initial_stones,
            "rules": rules,
            "komi": state.komi,
            "boardXSize": state.board_size,
            "boardYSize": state.board_size,
            "analyzeTurns": [len(moves)],  # Analyze current position
            "maxVisits": max_visits,
            "analysisPVLen": analysis_pv_len,
            "includeOwnership": include_ownership,
            "includePolicy": include_policy,
        }
        
        return query
        
    def _parse_response(self, response: Dict, state: GameState) -> AnalysisResult:
        """Parse KataGo response into AnalysisResult."""
        
        root_info = response.get("rootInfo", {})
        move_infos_raw = response.get("moveInfos", [])
        
        # Parse move infos
        move_infos = []
        for mi in move_infos_raw:
            move_info = MoveInfo(
                move=mi.get("move", ""),
                visits=mi.get("visits", 0),
                winrate=mi.get("winrate", 0.5),
                score_lead=mi.get("scoreLead", 0.0),
                pv=mi.get("pv", []),
                prior=mi.get("prior", 0.0),
                utility=mi.get("utility", 0.0),
            )
            move_infos.append(move_info)
        
        # Sort by visits (most visited = best move)
        move_infos.sort(key=lambda x: x.visits, reverse=True)
        
        result = AnalysisResult(
            id=response.get("id", ""),
            turn_number=response.get("turnNumber", len(state.moves)),
            current_player=state.current_player,
            root_winrate=root_info.get("winrate", 0.5),
            root_score_lead=root_info.get("scoreLead", 0.0),
            root_visits=root_info.get("visits", 0),
            move_infos=move_infos,
            ownership=response.get("ownership"),
            raw_response=response,
        )
        
        return result


def format_analysis_result(result: AnalysisResult, state: GameState, top_n: int = 5) -> str:
    """Format analysis result as human-readable text."""
    lines = []
    
    # Current position evaluation
    current = "Black" if result.current_player == "B" else "White"
    winrate_pct = result.root_winrate * 100
    
    # Determine who is winning
    if result.current_player == "B":
        black_winrate = winrate_pct
        white_winrate = 100 - winrate_pct
        score_for_black = result.root_score_lead
    else:
        white_winrate = winrate_pct
        black_winrate = 100 - winrate_pct
        score_for_black = -result.root_score_lead
    
    lines.append(f"=== Position Analysis (Move {len(state.moves)}) ===")
    lines.append(f"Turn: {current} to play")
    lines.append("")
    lines.append(f"Win Rate: Black {black_winrate:.1f}% - White {white_winrate:.1f}%")
    
    if score_for_black > 0:
        lines.append(f"Score: Black leads by {abs(score_for_black):.1f} points")
    elif score_for_black < 0:
        lines.append(f"Score: White leads by {abs(score_for_black):.1f} points")
    else:
        lines.append(f"Score: Even position")
    
    lines.append("")
    lines.append(f"=== Top {min(top_n, len(result.move_infos))} Recommended Moves ===")
    
    for i, mi in enumerate(result.move_infos[:top_n], 1):
        wr_pct = mi.winrate * 100
        pv_str = " → ".join(mi.pv[:5]) if mi.pv else ""
        
        lines.append(f"{i}. {mi.move}")
        lines.append(f"   Win rate: {wr_pct:.1f}%, Score: {mi.score_lead:+.1f}")
        if pv_str:
            lines.append(f"   Variation: {pv_str}")
        lines.append("")
    
    return "\n".join(lines)


def format_ownership_map(ownership: List[float], board_size: int) -> str:
    """Format ownership data as ASCII territory map."""
    if not ownership or len(ownership) != board_size * board_size:
        return "Ownership data not available"
    
    lines = []
    lines.append("=== Territory Map ===")
    lines.append("(B = Black territory, W = White territory, . = neutral)")
    lines.append("")
    
    letters = "ABCDEFGHJKLMNOPQRST"[:board_size]
    lines.append(f"   {' '.join(letters)}")
    
    for row in range(board_size):
        row_num = board_size - row
        row_str = f"{row_num:2d} "
        
        for col in range(board_size):
            idx = row * board_size + col
            own = ownership[idx]
            
            if own > 0.6:
                row_str += "B "
            elif own > 0.2:
                row_str += "b "
            elif own < -0.6:
                row_str += "W "
            elif own < -0.2:
                row_str += "w "
            else:
                row_str += ". "
        
        row_str += f"{row_num:2d}"
        lines.append(row_str)
    
    lines.append(f"   {' '.join(letters)}")
    
    return "\n".join(lines)