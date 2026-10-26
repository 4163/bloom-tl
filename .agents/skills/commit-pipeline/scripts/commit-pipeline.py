import os
import sys
sys.dont_write_bytecode = True
import subprocess
import shutil
import urllib.request
import configparser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]

# Configuration for AI Committer
AI_CLI = shutil.which("opencode") or "opencode"
AI_CMD = "run --auto"
AI_MODEL = "opencode/deepseek-v4.1-flash-free"
AI_VARIANT = "high"
INSTRUCTIONS_PATH = ".agents/skills/commit-pipeline/SKILL.md"

def get_config():
    config = {}
    current = None
    if not os.path.exists('.exclusion-config'):
        return config

    with open('.exclusion-config', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            if line.startswith('[') and line.endswith(']'):
                current = line[1:-1]
                config[current] = []
            elif current:
                config[current].append(line)
    return config

def apply_submodule_sparse_checkout(config):
    root = Path.cwd().resolve()
    modules = configparser.ConfigParser(interpolation=None)
    modules.read(root / ".gitmodules", encoding="utf-8")
    registered = {modules[section]["path"] for section in modules.sections()}
    for section, patterns in config.items():
        if section == "remote:/":
            continue
        folder = (root / section).resolve()
        if section not in registered or folder == root or not folder.is_relative_to(root):
            raise ValueError(f"Not a registered submodule inside this repository: {section}")
        if not (folder / ".git").exists():
            raise ValueError(f"Initialize the {section} submodule before pruning.")
        checkout = subprocess.check_output(["git", "rev-parse", "--show-toplevel"],
                                           cwd=folder, text=True, encoding="utf-8").strip()
        if Path(checkout).resolve() != folder:
            raise ValueError(f"Not a submodule checkout: {section}")
        dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"],
                                        cwd=folder, text=True, encoding="utf-8")
        if dirty:
            raise ValueError(f"Preserve or resolve tracked changes in {section} before pruning.")
        sparse_patterns = ["/*"]
        for pattern in patterns:
            parts = pattern.rstrip("/").split("/")
            if (pattern.startswith(("/", "!", "#")) or "\\" in pattern
                    or any(part in {"", ".", "..", ".git"} for part in parts)):
                raise ValueError(f"Invalid submodule exclusion: {pattern}")
            sparse_patterns.append("!/" + pattern)
        subprocess.run(["git", "sparse-checkout", "set", "--no-cone", "--stdin"], cwd=folder,
                       input="\n".join(sparse_patterns) + "\n", text=True, encoding="utf-8", check=True)
        print(f"Applied {len(patterns)} local exclusions to {section}.")


def download_remote_files(config):
    lines = []
    if "remote:/" in config:
        lines.extend(config["remote:/"])
    if os.path.exists('.filemodules'):
        with open('.filemodules', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    lines.append(line)
    if not lines:
        return
    print("=== Downloading remote files ===")
    for line in lines:
        if '=' in line:
            url, dest = [x.strip() for x in line.split('=', 1)]
            try:
                dest_dir = os.path.dirname(dest)
                if dest_dir:
                    os.makedirs(dest_dir, exist_ok=True)
                print(f"Downloading {url} -> {dest}")
                urllib.request.urlretrieve(url, dest)
            except Exception as e:
                print(f"Failed to download {url}: {e}")

def read_additional_info():
    """Prompt the user for additional commit/push info from the terminal.
    Read lines until an empty line or EOF; returns a single string."""
    print("=== Additional commit/push info (type your notes, end with an empty line) ===")
    lines = []
    try:
        while True:
            line = input("> ")
            if line.strip() == "":
                break
            lines.append(line)
    except EOFError:
        pass
    return "\n".join(lines).strip()


def read_header():
    return input("Enter a short commit header: ") or "Commit"


def read_body():
    print("Enter commit body (empty line or EOF to finish):")
    lines = []
    try:
        while True:
            line = input("> ")
            if line.strip() == "":
                break
            lines.append(line)
    except EOFError:
        pass
    return "\n".join(lines) or "No body provided"


def prepare(update=False):
    print("=== Updating submodules ===" if update else "=== Initializing pinned submodules ===")
    command = ["git", "submodule", "update", "--init", "--recursive"]
    if update:
        command.append("--remote")
    subprocess.run(command, check=True)
    config = get_config()
    apply_submodule_sparse_checkout(config)
    download_remote_files(config)


def do_push(manual=False, additional=""):
    prepare(update=True)

    print("=== Staging all changes ===")
    subprocess.run(["git", "add", "-A"], check=True)

    if manual:
        print("=== Manual commit ===")
        header = read_header()
        body = read_body()
        msg = f"{header}\n\n{body}".strip()
        subprocess.run(["git", "commit", "-m", msg], check=True)
        subprocess.run(["git", "push"], check=True)
        print("=== Done ===")
        return

    print("=== Running AI committer ===")

    cmd = [AI_CLI] + AI_CMD.split()
    if AI_MODEL:
        cmd.extend(["--model", AI_MODEL])
    if AI_VARIANT:
        cmd.extend(["--variant", AI_VARIANT])

    prompt = f"[COMMIT_PIPELINE]\nFollow the workflow in '{INSTRUCTIONS_PATH}'. Commit the reviewed changes and push them."
    if additional:
        # Prioritized user-provided context: takes precedence over anything the
        # AI infers from the diff/session data.
        prompt += (
            "\n\nUser-provided context about this commit/push (PRIORITIZED - "
            "treat this as the user's intent for what to commit and what the "
            "commit messages should emphasize):\n"
            f"{additional}"
        )

    cmd.append(prompt)
    subprocess.run(cmd, check=True)
    print("=== Done ===")

if __name__ == "__main__":
    os.chdir(ROOT)
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help"}:
        print("Usage: commit-pipeline.py prepare [--update] | push [-x] [-a]")
        sys.exit(0 if len(sys.argv) > 1 else 1)

    command = sys.argv[1]
    if command == "prepare":
        prepare(update="--update" in sys.argv[2:])
    elif command == "push":
        info = read_additional_info() if "-a" in sys.argv[2:] else ""
        do_push(manual="-x" in sys.argv[2:], additional=info)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
