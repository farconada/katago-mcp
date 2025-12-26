#!/usr/bin/env python3
"""
Debug script for KataGo communication.

This script runs KataGo with debug output enabled to see exactly what's happening.
"""
import os
import sys

# Enable debug mode
os.environ['KATAGO_DEBUG'] = 'true'

from config import KATAGO_PATH, KATAGO_MODEL, KATAGO_CONFIG, SGF_WATCH_PATH
from sgf_reader import find_latest_sgf, read_sgf_file
from katago_client import KataGoClient

print("=" * 70)
print("KataGo Debug Test")
print("=" * 70)
print()

print("Configuration:")
print(f"  KataGo: {KATAGO_PATH}")
print(f"  Model: {KATAGO_MODEL}")
print(f"  Config: {KATAGO_CONFIG}")
print(f"  SGF Path: {SGF_WATCH_PATH}")
print()

# Check files exist
if not os.path.exists(KATAGO_PATH):
    print(f"ERROR: KataGo not found at {KATAGO_PATH}")
    sys.exit(1)

if not os.path.exists(KATAGO_MODEL):
    print(f"ERROR: Model not found at {KATAGO_MODEL}")
    sys.exit(1)

print("✓ KataGo and model files exist")
print()

# Find SGF
sgf_path = find_latest_sgf(SGF_WATCH_PATH)
if not sgf_path:
    print(f"ERROR: No SGF files found in {SGF_WATCH_PATH}")
    sys.exit(1)

print(f"✓ Found SGF: {sgf_path}")

# Read game state
state = read_sgf_file(sgf_path)
print(f"✓ Read SGF: {len(state.moves)} moves")
print()

# Create client with debug enabled
print("Creating KataGo client with debug output enabled...")
print("=" * 70)
print()

client = KataGoClient(
    katago_path=KATAGO_PATH,
    model_path=KATAGO_MODEL,
    config_path=KATAGO_CONFIG,
    debug=True  # Enable debug output
)

try:
    print("Starting KataGo...")
    client.start()
    print("✓ KataGo process started")
    print()
    
    print("Sending analysis query...")
    print("(Watch for debug output above)")
    print()
    
    result = client.analyze_position(
        state,
        max_visits=10,  # Small number for faster testing
        include_ownership=False,
    )
    
    if result:
        print("=" * 70)
        print("SUCCESS: Got analysis result!")
        print("=" * 70)
        print(f"Win rate: {result.root_winrate * 100:.1f}%")
        print(f"Score lead: {result.root_score_lead:+.1f}")
        print(f"Top moves: {len(result.move_infos)}")
        if result.move_infos:
            print(f"Best move: {result.move_infos[0].move}")
    else:
        print("=" * 70)
        print("FAILURE: Analysis returned None (timeout or error)")
        print("=" * 70)
        print("Check the debug output above for clues.")
        print("Common issues:")
        print("  - Query format incorrect")
        print("  - Timeout too short for large model")
        print("  - KataGo crashed silently")
        
finally:
    print()
    print("Stopping KataGo...")
    client.stop()
    print("Done.")