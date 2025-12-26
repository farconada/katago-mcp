#!/usr/bin/env python3
"""
Test script to verify KataGo MCP server setup.

Run this to check if all components are properly configured.
"""
import os
import sys
import subprocess


def check_dependencies():
    """Check if all required packages are installed."""
    print("=== Checking Dependencies ===")
    
    packages = [
        ("fastmcp", "FastMCP"),
        ("sgfmill", "sgfmill"),
    ]
    
    all_ok = True
    for package, display_name in packages:
        try:
            __import__(package)
            print(f"  ✓ {display_name} installed")
        except ImportError:
            print(f"  ✗ {display_name} NOT installed - run: pip install {package}")
            all_ok = False
    
    return all_ok


def check_config():
    """Check configuration settings."""
    print("\n=== Checking Configuration ===")
    
    from config import (
        KATAGO_PATH,
        KATAGO_MODEL, 
        KATAGO_CONFIG,
        SGF_WATCH_PATH,
    )
    
    all_ok = True
    
    # Check KataGo executable
    if os.path.isfile(KATAGO_PATH):
        print(f"  ✓ KataGo found at: {KATAGO_PATH}")
    else:
        print(f"  ✗ KataGo NOT found at: {KATAGO_PATH}")
        print(f"    Set KATAGO_PATH environment variable to the correct path")
        all_ok = False
    
    # Check model file
    if os.path.isfile(KATAGO_MODEL):
        print(f"  ✓ Model found at: {KATAGO_MODEL}")
    else:
        print(f"  ✗ Model NOT found at: {KATAGO_MODEL}")
        print(f"    Set KATAGO_MODEL environment variable to your model path")
        all_ok = False
    
    # Check config file
    if os.path.isfile(KATAGO_CONFIG):
        print(f"  ✓ Config found at: {KATAGO_CONFIG}")
    else:
        print(f"  ⚠ Config NOT found at: {KATAGO_CONFIG}")
        print(f"    Using default analysis config. Set KATAGO_CONFIG if needed.")
    
    # Check SGF directory
    if os.path.isdir(SGF_WATCH_PATH):
        print(f"  ✓ SGF directory exists: {SGF_WATCH_PATH}")
    else:
        print(f"  ✗ SGF directory NOT found: {SGF_WATCH_PATH}")
        print(f"    Create the directory or set SGF_WATCH_PATH environment variable")
        all_ok = False
    
    return all_ok


def check_sgf_files():
    """Check for SGF files in the watch directory."""
    print("\n=== Checking SGF Files ===")
    
    from config import SGF_WATCH_PATH
    from sgf_reader import find_latest_sgf, read_sgf_file, get_game_info
    
    if not os.path.isdir(SGF_WATCH_PATH):
        print(f"  SGF directory does not exist")
        return False
    
    sgf_path = find_latest_sgf(SGF_WATCH_PATH)
    
    if sgf_path is None:
        print(f"  ⚠ No SGF files found in {SGF_WATCH_PATH}")
        print(f"    Save a game from Sabaki to this directory to test")
        return True  # Not a fatal error
    
    print(f"  ✓ Found SGF file: {sgf_path}")
    
    try:
        state = read_sgf_file(sgf_path)
        info = get_game_info(state)
        print(f"    Board size: {info['board_size']}x{info['board_size']}")
        print(f"    Moves: {info['move_count']}")
        print(f"    Players: {info['black_player']} vs {info['white_player']}")
        return True
    except Exception as e:
        print(f"  ✗ Error reading SGF: {e}")
        return False


def check_katago():
    """Check if KataGo can start."""
    print("\n=== Checking KataGo ===")
    
    from config import KATAGO_PATH, KATAGO_MODEL, KATAGO_CONFIG
    
    if not os.path.isfile(KATAGO_PATH):
        print("  ⚠ Skipping KataGo test - executable not found")
        return True
    
    if not os.path.isfile(KATAGO_MODEL):
        print("  ⚠ Skipping KataGo test - model not found")
        return True
    
    print("  Testing KataGo startup...")
    
    try:
        # Test version command
        result = subprocess.run(
            [KATAGO_PATH, "version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            version = result.stdout.strip().split('\n')[0]
            print(f"  ✓ KataGo version: {version}")
            return True
        else:
            print(f"  ✗ KataGo failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("  ✗ KataGo timed out")
        return False
    except Exception as e:
        print(f"  ✗ Error testing KataGo: {e}")
        return False


def check_server_import():
    """Check if the server can be imported."""
    print("\n=== Checking Server Module ===")
    
    try:
        from server import mcp
        print("  ✓ Server module imported successfully")
        print(f"    Server name: {mcp.name}")
        return True
    except Exception as e:
        print(f"  ✗ Error importing server: {e}")
        return False


def main():
    """Run all checks."""
    print("=" * 50)
    print("KataGo MCP Server - Setup Verification")
    print("=" * 50)
    
    results = []
    
    results.append(("Dependencies", check_dependencies()))
    results.append(("Configuration", check_config()))
    results.append(("SGF Files", check_sgf_files()))
    results.append(("KataGo", check_katago()))
    results.append(("Server Import", check_server_import()))
    
    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("All checks passed! Your setup is ready.")
        print("\nNext steps:")
        print("1. Configure Claude Desktop with the server path")
        print("2. Save a Go game in Sabaki to your SGF directory")
        print("3. Ask Claude about your position!")
    else:
        print("Some checks failed. Please fix the issues above.")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())