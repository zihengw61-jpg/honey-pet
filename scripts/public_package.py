"""Shared filtering for public artifacts; never include personal configuration."""

from __future__ import annotations

from pathlib import Path
import re
import shutil


SOURCE_FILES = (
    ".gitignore", "README.md", "WINDOWS.md", "LICENSE", "main.py",
    "requirements.txt", "requirements-build.txt", "start_windows.bat",
    "build_windows.bat", "notification_config.example.json",
)
SOURCE_DIRECTORIES = ("foxpet", "assets", "scripts", "tests", "third_party", ".github")
EXCLUDED_PARTS = {
    ".git", ".venv", ".build", "build", "dist", "artifacts", "private", ".private",
    "secrets", ".secrets", ".aws", ".ssh", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".idea", ".vscode",
}
PRIVATE_NAMES = {
    "notification_config.json", "credentials.json", "credentials.yaml", "credentials.yml",
    "credentials", "secrets.json", "secrets.yaml", "secrets.yml", "tokens.json", "id_rsa", "id_ed25519",
}
PRIVATE_SUFFIXES = (".local.json", ".pyc", ".pem", ".key", ".p12", ".pfx", ".log")
TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".bat", ".ps1", ".yml", ".yaml", ".toml", ".ini", ".cfg"}
WEBHOOK_CREDENTIAL = re.compile(
    rb"https://qyapi[.]weixin[.]qq[.]com/cgi-bin/webhook/send[?]key=([a-z0-9_-]{24,})",
    re.IGNORECASE,
)


def is_public_path(relative: Path) -> bool:
    parts = [part.lower() for part in relative.parts]
    if any(part in EXCLUDED_PARTS for part in parts):
        return False
    name = parts[-1] if parts else ""
    return not (
        name in PRIVATE_NAMES or name.startswith(".env") or name.endswith(PRIVATE_SUFFIXES)
        or ".secret." in name or ".private." in name or name.startswith("credentials.")
        or (name.startswith("notification_config.") and name != "notification_config.example.json")
    )


def assert_no_embedded_webhook(path: Path) -> None:
    """Fail closed on credential-shaped URLs without printing the credential."""
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return
    for match in WEBHOOK_CREDENTIAL.finditer(path.read_bytes()):
        token = match.group(1).lower()
        if any(marker in token for marker in (b"your_", b"example", b"placeholder", b"dummy")):
            continue
        raise ValueError(f"Potential webhook credential in public input: {path.name}")


def public_source_files(root: Path):
    for name in SOURCE_FILES:
        path = root / name
        if path.is_file() and not path.is_symlink() and is_public_path(path.relative_to(root)):
            yield path
    for name in SOURCE_DIRECTORIES:
        directory = root / name
        if not directory.is_dir() or directory.is_symlink():
            continue
        for path in sorted(directory.rglob("*")):
            if (path.is_file() and not path.is_symlink()
                    and not any(parent.is_symlink() for parent in path.parents if parent != root)
                    and is_public_path(path.relative_to(root))):
                yield path


def assert_public_inputs(root: Path) -> None:
    for path in public_source_files(root):
        assert_no_embedded_webhook(path)


def copy_public_tree(source: Path, destination: Path) -> None:
    def ignore(directory: str, names: list[str]) -> set[str]:
        base = Path(directory)
        return {
            name for name in names
            if (base / name).is_symlink() or not is_public_path((base / name).relative_to(source))
        }
    for path in source.rglob("*"):
        if path.is_file() and not path.is_symlink() and is_public_path(path.relative_to(source)):
            assert_no_embedded_webhook(path)
    shutil.copytree(source, destination, ignore=ignore)


def assert_public_distribution(directory: Path) -> None:
    for path in directory.rglob("*"):
        if path.is_symlink() or not is_public_path(path.relative_to(directory)):
            raise ValueError(f"Private or generated file in public distribution: {path.name}")
        if path.is_file():
            assert_no_embedded_webhook(path)
