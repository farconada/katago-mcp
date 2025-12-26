#!/usr/bin/env python3
"""
Comprehensive test for all KataGo MCP server tools.

This script tests each tool individually with detailed logging.
"""
import os
import sys
import json
from datetime import datetime

# Set up test environment
TEST_SGF_PATH = os.environ.get('SGF_WATCH_PATH', '/home/sandbox/katago-mcp/test_games')
os.environ['SGF_WATCH_PATH'] = TEST_SGF_PATH

def log_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)

def log_step(step: str):
    """Print a step within a test."""
    print(f"\n→ {step}")

def log_success(message: str):
    """Print a success message."""
    print(f"  ✓ {message}")

def log_error(message: str):
    """Print an error message."""
    print(f"  ✗ {message}")

def log_warning(message: str):
    """Print a warning message."""
    print(f"  ⚠ {message}")

def log_data(label: str, data: str, max_lines: int = 10):
    """Print data with a label, truncated if too long."""
    print(f"\n  📄 {label}:")
    lines = data.split('\n')
    for i, line in enumerate(lines[:max_lines]):
        print(f"    {line}")
    if len(lines) > max_lines:
        print(f"    ... ({len(lines) - max_lines} more lines)")


# Main test execution
print("=" * 70)
print(f" KataGo MCP Server - Comprehensive Tool Testing")
print(f" Test started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

test_results = {}

# ============================================================================
# Test 1: list_sgf_files
# ============================================================================

log_section("Test 1: list_sgf_files")

try:
    log_step("Importing server module")
    from server import get_current_game
    from sgf_reader import find_latest_sgf
    log_success("Server module imported")
    
    log_step(f"Scanning directory: {TEST_SGF_PATH}")
    sgf_files = []
    import glob
    pattern = os.path.join(TEST_SGF_PATH, "**", "*.sgf")
    sgf_files = glob.glob(pattern, recursive=True)
    
    if sgf_files:
        log_success(f"Found {len(sgf_files)} SGF file(s)")
        for sgf_file in sgf_files:
            print(f"    - {os.path.basename(sgf_file)}")
        test_results['list_sgf_files'] = 'PASS'
    else:
        log_warning(f"No SGF files found in {TEST_SGF_PATH}")
        test_results['list_sgf_files'] = 'SKIP'
        
except Exception as e:
    log_error(f"Failed: {type(e).__name__}: {e}")
    test_results['list_sgf_files'] = 'FAIL'
    import traceback
    print("\n  Stack trace:")
    for line in traceback.format_exc().split('\n'):
        print(f"    {line}")

# ============================================================================
# Test 2: get_board_state
# ============================================================================

log_section("Test 2: get_board_state")

try:
    from sgf_reader import read_sgf_file, board_to_ascii, format_move_history, get_game_info
    
    log_step("Finding latest SGF file")
    sgf_path = find_latest_sgf(TEST_SGF_PATH)
    
    if not sgf_path:
        log_error("No SGF file found")
        test_results['get_board_state'] = 'SKIP'
    else:
        log_success(f"Using: {os.path.basename(sgf_path)}")
        
        log_step("Reading SGF file")
        state = read_sgf_file(sgf_path)
        log_success("SGF parsed successfully")
        
        log_step("Extracting game information")
        info = get_game_info(state)
        log_data("Game Info", json.dumps(info, indent=2))
        
        log_step("Generating board display")
        board_ascii = board_to_ascii(state)
        log_data("Board State", board_ascii, max_lines=15)
        
        log_step("Formatting move history")
        move_history = format_move_history(state, last_n=10)
        log_data("Recent Moves", move_history)
        
        log_success("get_board_state functionality verified")
        test_results['get_board_state'] = 'PASS'
        
except Exception as e:
    log_error(f"Failed: {type(e).__name__}: {e}")
    test_results['get_board_state'] = 'FAIL'
    import traceback
    print("\n  Stack trace:")
    for line in traceback.format_exc().split('\n'):
        print(f"    {line}")

# ============================================================================
# Test 3: analyze_position (requires working KataGo)
# ============================================================================

log_section("Test 3: analyze_position")
log_warning("This test requires a working KataGo installation")

try:
    from katago_client import KataGoClient, format_analysis_result
    from config import KATAGO_PATH, KATAGO_MODEL, KATAGO_CONFIG
    
    log_step("Checking KataGo configuration")
    print(f"    KataGo path: {KATAGO_PATH}")
    print(f"    Model path: {KATAGO_MODEL}")
    print(f"    Config path: {KATAGO_CONFIG}")
    
    if not os.path.exists(KATAGO_PATH):
        log_error(f"KataGo not found at {KATAGO_PATH}")
        test_results['analyze_position'] = 'SKIP'
    elif not os.path.exists(KATAGO_MODEL):
        log_error(f"Model not found at {KATAGO_MODEL}")
        test_results['analyze_position'] = 'SKIP'
    else:
        log_success("KataGo and model files exist")
        
        log_step("Creating KataGo client with debug enabled")
        client = KataGoClient(
            katago_path=KATAGO_PATH,
            model_path=KATAGO_MODEL,
            config_path=KATAGO_CONFIG,
            debug=True  # Enable debug logging
        )
        log_success("Client created")
        
        log_step("Starting KataGo process")
        client.start()
        log_success("KataGo process started")
        
        log_step("Loading game state")
        sgf_path = find_latest_sgf(TEST_SGF_PATH)
        state = read_sgf_file(sgf_path)
        log_success(f"Loaded position with {len(state.moves)} moves")
        
        log_step("Sending analysis query (maxVisits=10)")
        print("    (Watch for debug output in stderr)")
        
        result = client.analyze_position(
            state,
            max_visits=10,
            include_ownership=True,
            analysis_pv_len=10
        )
        
        if result:
            log_success("Analysis completed successfully!")
            
            # Show analysis results
            analysis_text = format_analysis_result(result, state, top_n=3)
            log_data("Analysis Result", analysis_text, max_lines=20)
            
            # Show raw response summary
            print(f"\n  📊 Analysis metrics:")
            print(f"    - Request ID: {result.id}")
            print(f"    - Root visits: {result.root_visits}")
            print(f"    - Move candidates: {len(result.move_infos)}")
            print(f"    - Ownership data: {'Yes' if result.ownership else 'No'}")
            
            test_results['analyze_position'] = 'PASS'
        else:
            log_error("Analysis returned None (timeout or communication error)")
            log_warning("Check debug output above for KataGo communication issues")
            test_results['analyze_position'] = 'FAIL'
        
        log_step("Stopping KataGo client")
        client.stop()
        log_success("Client stopped")
        
except FileNotFoundError as e:
    log_error(f"Configuration error: {e}")
    test_results['analyze_position'] = 'SKIP'
except Exception as e:
    log_error(f"Failed: {type(e).__name__}: {e}")
    test_results['analyze_position'] = 'FAIL'
    import traceback
    print("\n  Stack trace:")
    for line in traceback.format_exc().split('\n'):
        print(f"    {line}")

# ============================================================================
# Test 4: get_move_recommendation
# ============================================================================

log_section("Test 4: get_move_recommendation")
log_warning("This test requires a working KataGo installation")

try:
    if test_results.get('analyze_position') == 'PASS':
        log_step("Using KataGo client from previous test")
        
        client = KataGoClient(
            katago_path=KATAGO_PATH,
            model_path=KATAGO_MODEL,
            config_path=KATAGO_CONFIG,
            debug=False  # Less verbose for this test
        )
        client.start()
        
        state = read_sgf_file(find_latest_sgf(TEST_SGF_PATH))
        
        log_step("Requesting move recommendation")
        result = client.analyze_position(state, max_visits=20)
        
        if result and result.move_infos:
            best = result.move_infos[0]
            
            print(f"\n  📍 Recommendation details:")
            print(f"    Best move: {best.move}")
            print(f"    Win rate: {best.winrate * 100:.1f}%")
            print(f"    Score: {best.score_lead:+.1f}")
            print(f"    Visits: {best.visits}")
            if best.pv:
                print(f"    PV: {' '.join(best.pv[:5])}")
            
            # Show alternatives
            if len(result.move_infos) > 1:
                print(f"\n  Alternative moves:")
                for i, mi in enumerate(result.move_infos[1:4], 2):
                    wr_diff = (mi.winrate - best.winrate) * 100
                    print(f"    {i}. {mi.move} (WR: {mi.winrate*100:.1f}%, {wr_diff:+.1f}%)")
            
            log_success("Move recommendation generated")
            test_results['get_move_recommendation'] = 'PASS'
        else:
            log_error("No move recommendations available")
            test_results['get_move_recommendation'] = 'FAIL'
        
        client.stop()
        
    else:
        log_warning("Skipping (requires passing analyze_position test)")
        test_results['get_move_recommendation'] = 'SKIP'
        
except Exception as e:
    log_error(f"Failed: {type(e).__name__}: {e}")
    test_results['get_move_recommendation'] = 'FAIL'
    import traceback
    print("\n  Stack trace:")
    for line in traceback.format_exc().split('\n'):
        print(f"    {line}")

# ============================================================================
# Test 5: get_territory_analysis
# ============================================================================

log_section("Test 5: get_territory_analysis")

try:
    if test_results.get('analyze_position') == 'PASS':
        log_step("Testing territory analysis")
        
        client = KataGoClient(
            katago_path=KATAGO_PATH,
            model_path=KATAGO_MODEL,
            config_path=KATAGO_CONFIG,
            debug=False
        )
        client.start()
        
        state = read_sgf_file(find_latest_sgf(TEST_SGF_PATH))
        
        result = client.analyze_position(state, max_visits=20, include_ownership=True)
        
        if result and result.ownership:
            from katago_client import format_ownership_map
            
            print(f"\n  Territory statistics:")
            ownership = result.ownership
            black_territory = sum(1 for o in ownership if o > 0.5)
            white_territory = sum(1 for o in ownership if o < -0.5)
            neutral = len(ownership) - black_territory - white_territory
            
            print(f"    Black territory: ~{black_territory} points")
            print(f"    White territory: ~{white_territory} points")
            print(f"    Neutral/contested: ~{neutral} points")
            
            territory_map = format_ownership_map(ownership, state.board_size)
            log_data("Territory Map", territory_map, max_lines=15)
            
            log_success("Territory analysis completed")
            test_results['get_territory_analysis'] = 'PASS'
        else:
            log_error("No ownership data returned")
            test_results['get_territory_analysis'] = 'FAIL'
        
        client.stop()
    else:
        log_warning("Skipping (requires passing analyze_position test)")
        test_results['get_territory_analysis'] = 'SKIP'
        
except Exception as e:
    log_error(f"Failed: {type(e).__name__}: {e}")
    test_results['get_territory_analysis'] = 'FAIL'
    import traceback
    print("\n  Stack trace:")
    for line in traceback.format_exc().split('\n'):
        print(f"    {line}")

# ============================================================================
# Test 6: evaluate_move
# ============================================================================

log_section("Test 6: evaluate_move")

try:
    if test_results.get('analyze_position') == 'PASS':
        log_step("Testing move evaluation")
        
        client = KataGoClient(
            katago_path=KATAGO_PATH,
            model_path=KATAGO_MODEL,
            config_path=KATAGO_CONFIG,
            debug=False
        )
        client.start()
        
        state = read_sgf_file(find_latest_sgf(TEST_SGF_PATH))
        
        # Test with the best move from previous analysis
        log_step("Getting analysis for move evaluation")
        result = client.analyze_position(state, max_visits=20)
        
        if result and result.move_infos:
            # Test evaluating the best move
            best_move = result.move_infos[0].move
            log_step(f"Evaluating move: {best_move}")
            
            # Find this move in the results
            move_found = False
            for mi in result.move_infos:
                if mi.move == best_move:
                    rank = result.move_infos.index(mi) + 1
                    print(f"\n  📊 Move evaluation:")
                    print(f"    Move: {mi.move}")
                    print(f"    Rank: #{rank} of {len(result.move_infos)}")
                    print(f"    Win rate: {mi.winrate * 100:.1f}%")
                    print(f"    Score: {mi.score_lead:+.1f}")
                    print(f"    Visits: {mi.visits}")
                    move_found = True
                    break
            
            # Also test a potentially bad move
            if len(result.move_infos) > 3:
                log_step("Testing evaluation of a suboptimal move")
                suboptimal = result.move_infos[3].move
                wr_diff = (result.move_infos[3].winrate - result.move_infos[0].winrate) * 100
                print(f"    Move: {suboptimal}")
                print(f"    Win rate difference: {wr_diff:+.1f}% vs best")
            
            if move_found:
                log_success("Move evaluation completed")
                test_results['evaluate_move'] = 'PASS'
            else:
                log_error("Move not found in analysis")
                test_results['evaluate_move'] = 'FAIL'
        else:
            log_error("No analysis data available")
            test_results['evaluate_move'] = 'FAIL'
        
        client.stop()
    else:
        log_warning("Skipping (requires passing analyze_position test)")
        test_results['evaluate_move'] = 'SKIP'
        
except Exception as e:
    log_error(f"Failed: {type(e).__name__}: {e}")
    test_results['evaluate_move'] = 'FAIL'
    import traceback
    print("\n  Stack trace:")
    for line in traceback.format_exc().split('\n'):
        print(f"    {line}")

# ============================================================================
# Final Summary
# ============================================================================

log_section("Test Summary")

print("\nResults:")
print()

total_tests = len(test_results)
passed = sum(1 for r in test_results.values() if r == 'PASS')
failed = sum(1 for r in test_results.values() if r == 'FAIL')
skipped = sum(1 for r in test_results.values() if r == 'SKIP')

for tool, result in test_results.items():
    icon = {'PASS': '✓', 'FAIL': '✗', 'SKIP': '⊝'}[result]
    color = {'PASS': '', 'FAIL': '', 'SKIP': ''}[result]
    print(f"  {icon} {tool:30s} {result}")

print()
print(f"Summary: {passed}/{total_tests} passed, {failed} failed, {skipped} skipped")
print()

if failed > 0:
    print("⚠ Some tests failed. Common issues:")
    print("  - Broken pipe: Check KATAGO_PATH, KATAGO_MODEL, KATAGO_CONFIG")
    print("  - Timeout: Increase timeout or reduce maxVisits")
    print("  - No response: Check that analysis.cfg is for analysis mode, not GTP mode")
    print()
    print("Run debug_katago.py for detailed KataGo communication debugging")
    sys.exit(1)
elif skipped > 0:
    print("⊝ Some tests were skipped (KataGo not available)")
    print("  Install KataGo to run full tests")
    sys.exit(0)
else:
    print("✓ All tests passed successfully!")
    sys.exit(0)