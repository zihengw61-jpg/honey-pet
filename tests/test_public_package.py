"""Public downloads must remain safe even if a checkout contains private data."""

import importlib.util
from pathlib import Path
import sys
import zipfile

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from public_package import assert_no_embedded_webhook, assert_public_distribution, copy_public_tree

WEBHOOK_BASE = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key="
FAKE_KEY = "01234567" + "-89ab-cdef-0123-456789abcdef"


def private_assets(root):
    assets = root / "assets"
    assets.mkdir()
    (assets / "pet.ico").write_bytes(b"public-icon")
    for name in (
        "notification_config.json", "nested/NOTIFICATION_CONFIG.JSON", "settings.local.json",
        "notification_config.private.json", "nested/credentials.json", ".env",
        "private/secret.txt", "nested/private.key",
    ):
        file = assets / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(WEBHOOK_BASE + FAKE_KEY, encoding="utf-8")
    return assets


def test_asset_copy_cannot_publish_nested_personal_configuration(tmp_path):
    assets = private_assets(tmp_path)
    copied = tmp_path / "public-assets"
    copy_public_tree(assets, copied)
    files = [path for path in copied.rglob("*") if path.is_file()]
    assert [path.relative_to(copied).as_posix() for path in files] == ["pet.ico"]
    assert all(FAKE_KEY.encode() not in path.read_bytes() for path in files)


def test_asset_symlink_cannot_publish_an_external_secret(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    outside = tmp_path / "private-data.txt"
    outside.write_text(WEBHOOK_BASE + FAKE_KEY)
    try:
        (assets / "innocent.txt").symlink_to(outside)
    except OSError:
        pytest.skip("Host does not allow creating symlinks")
    copied = tmp_path / "public-assets"
    copy_public_tree(assets, copied)
    assert not list(copied.iterdir())


def test_embedded_credential_aborts_without_exposing_the_key(tmp_path):
    file = tmp_path / "README.md"
    file.write_text(WEBHOOK_BASE + FAKE_KEY)
    with pytest.raises(ValueError) as error:
        assert_no_embedded_webhook(file)
    assert FAKE_KEY not in str(error.value)


def test_distribution_audit_rejects_a_config_added_after_staging(tmp_path):
    file = tmp_path / "notification_config.json"
    file.write_text(WEBHOOK_BASE + FAKE_KEY)
    with pytest.raises(ValueError) as error:
        assert_public_distribution(tmp_path)
    assert FAKE_KEY not in str(error.value)


def test_source_zip_excludes_secrets_and_is_reproducible(tmp_path, monkeypatch):
    private_assets(tmp_path)
    (tmp_path / "main.py").write_text('print("public")\n')
    (tmp_path / "notification_config.json").write_text(WEBHOOK_BASE + FAKE_KEY)
    private = tmp_path / ".private"
    private.mkdir()
    (private / "credentials.json").write_text(WEBHOOK_BASE + FAKE_KEY)
    spec = importlib.util.spec_from_file_location("source_bundle_under_test", SCRIPTS / "build_source_bundle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    results = []
    for number in range(2):
        output = tmp_path / f"source-{number}.zip"
        monkeypatch.setattr(sys, "argv", [str(SCRIPTS / "build_source_bundle.py"), "--output", str(output)])
        assert module.main() == 0
        results.append(output.read_bytes())
        with zipfile.ZipFile(output) as archive:
            assert archive.testzip() is None
            assert set(archive.namelist()) == {"HoneyPet-Python/main.py", "HoneyPet-Python/assets/pet.ico"}
            assert all(FAKE_KEY.encode() not in archive.read(name) for name in archive.namelist())
    assert results[0] == results[1]
