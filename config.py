"""
Configuration for KataGo MCP Server.

You can override these settings via environment variables.
"""
import os

# KataGo executable path
KATAGO_PATH = os.environ.get("KATAGO_PATH", "/usr/local/bin/katago")

# KataGo model file (.bin.gz)
KATAGO_MODEL = os.environ.get("KATAGO_MODEL", "/usr/share/katago/models/kata1-b18c384nbt-s9131461376-d4087399203.bin.gz")

# KataGo config file for analysis
KATAGO_CONFIG = os.environ.get("KATAGO_CONFIG", "/etc/katago/analysis.cfg")

# Directory where Sabaki saves SGF files
SGF_WATCH_PATH = os.environ.get("SGF_WATCH_PATH", os.path.expanduser("~/go/games"))

# Analysis settings
ANALYSIS_VISITS = int(os.environ.get("ANALYSIS_VISITS", "100"))
MAX_VARIATIONS = int(os.environ.get("MAX_VARIATIONS", "5"))
ANALYSIS_PV_LEN = int(os.environ.get("ANALYSIS_PV_LEN", "10"))

# Include ownership/territory analysis
INCLUDE_OWNERSHIP = os.environ.get("INCLUDE_OWNERSHIP", "true").lower() == "true"

# Default rules (can be overridden per game from SGF)
DEFAULT_RULES = os.environ.get("DEFAULT_RULES", "chinese")
DEFAULT_KOMI = float(os.environ.get("DEFAULT_KOMI", "7.5"))