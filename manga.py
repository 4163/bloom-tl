"""Repository entry point. Uses only the Python standard library."""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from manga_pipeline.cli import main

if __name__ == "__main__":
    main()
