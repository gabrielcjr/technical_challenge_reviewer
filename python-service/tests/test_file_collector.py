import tempfile
from pathlib import Path
from app.file_collector import collect_files, should_ignore, is_relevant_file

def test_should_ignore():
    assert should_ignore(Path(".git/config")) is True
    assert should_ignore(Path("node_modules/package")) is True
    assert should_ignore(Path("vendor/autoload")) is True
    assert should_ignore(Path("src/Controller")) is False

def test_is_relevant_file():
    assert is_relevant_file(Path("README.md")) is True
    assert is_relevant_file(Path("src/Controller.py")) is True
    assert is_relevant_file(Path("package-lock.json")) is False
    assert is_relevant_file(Path("Dockerfile")) is True

def test_collect_files_simple():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        (tmp / "README.md").write_text("# Test\nThis is a readme")
        (tmp / "src").mkdir()
        (tmp / "src" / "app.py").write_text("print('hello')")
        (tmp / "node_modules").mkdir()
        (tmp / "node_modules" / "ignored.js").write_text("should be ignored")

        tree, contents, meta = collect_files(tmp, max_files=10, max_total_chars=5000)

        assert "README.md" in tree
        assert "app.py" in tree
        assert "node_modules" not in tree or "ignored.js" not in contents
        assert meta["total_files"] >= 2
        assert meta["collected_files"] >= 1
        assert "This is a readme" in contents

def test_collect_files_truncation():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        # Create large file
        large_content = "x" * 150000
        (tmp / "large.txt").write_text(large_content)

        tree, contents, meta = collect_files(tmp, max_files=10, max_total_chars=25000)
        # Large file should be noted as skipped
        assert "too large" in contents or "large.txt" in tree
