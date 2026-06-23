import json
import sys
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import check_python_versions as cpv


def _mock_urlopen(payload: dict):
    body = BytesIO(json.dumps(payload).encode())
    cm = MagicMock()
    cm.__enter__ = lambda s: body
    cm.__exit__ = MagicMock(return_value=False)
    return cm


PYPI_RESPONSE = {
    "urls": [
        {"filename": "duckdb-1.3.0-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"},
        {"filename": "duckdb-1.3.0-cp311-cp311-manylinux_2_17_aarch64.manylinux2014_aarch64.whl"},
        {"filename": "duckdb-1.3.0-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"},
        {"filename": "duckdb-1.3.0-cp310-cp310-macosx_11_0_arm64.whl"},
        {"filename": "duckdb-1.3.0-py3-none-any.whl"},
    ]
}


class TestFetchDuckdbPythons:
    def test_extracts_manylinux_versions(self):
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(PYPI_RESPONSE)):
            result = cpv.fetch_duckdb_pythons("1.3.0")
        assert result == {"3.10", "3.11", "3.12"}

    def test_ignores_non_manylinux_wheels(self):
        payload = {
            "urls": [
                {"filename": "duckdb-1.3.0-cp313-cp313-macosx_11_0_arm64.whl"},
                {"filename": "duckdb-1.3.0-cp313-cp313-win_amd64.whl"},
            ]
        }
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(payload)):
            result = cpv.fetch_duckdb_pythons("1.3.0")
        assert result == set()

    def test_exits_on_404(self):
        err = urllib.error.HTTPError(url=None, code=404, msg="Not Found", hdrs=None, fp=None)
        with patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(SystemExit):
                cpv.fetch_duckdb_pythons("0.0.0")

    def test_exits_on_other_http_error(self):
        err = urllib.error.HTTPError(url=None, code=500, msg="Server Error", hdrs=None, fp=None)
        with patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(SystemExit):
                cpv.fetch_duckdb_pythons("1.3.0")


class TestReadPythonVersions:
    def test_parses_versions(self, tmp_path):
        _write_build_layer(tmp_path, 'PYTHON_VERSIONS: "3.10,3.11,3.12"')
        with patch.object(cpv, "repo_root", tmp_path):
            result = cpv.read_python_versions()
        assert result == {"3.10", "3.11", "3.12"}

    def test_strips_whitespace(self, tmp_path):
        _write_build_layer(tmp_path, 'PYTHON_VERSIONS: " 3.10 , 3.11 "')
        with patch.object(cpv, "repo_root", tmp_path):
            result = cpv.read_python_versions()
        assert result == {"3.10", "3.11"}

    def test_exits_when_key_missing(self, tmp_path):
        _write_build_layer(tmp_path, "env:\n  ARCHITECTURES: x86_64\n")
        with patch.object(cpv, "repo_root", tmp_path):
            with pytest.raises(SystemExit):
                cpv.read_python_versions()


def _write_build_layer(root: Path, content: str) -> None:
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    (workflows / "build-layer.yml").write_text(content)
