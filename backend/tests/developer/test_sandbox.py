import pytest
from pathlib import Path

from app.developer.mcp.utils.sandbox import resolve_safe_path
from app.developer.errors import ValidationError


def test_resolve_safe_path_valid(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    
    file_path = "src/main.py"
    resolved = resolve_safe_path(root, file_path)
    
    assert str(resolved) == str(root / "src" / "main.py")


def test_resolve_safe_path_traversal(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    
    traversal_path = "../outside.py"
    
    with pytest.raises(ValidationError) as exc:
        resolve_safe_path(root, traversal_path)
    
    assert exc.value.code.value == "E1xx"


def test_resolve_safe_path_absolute(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    
    # Passing an absolute path that is outside the root
    if root.drive:  # Windows
        abs_path = root.drive + "\\Windows\\System32\\cmd.exe"
    else:  # Linux/Mac
        abs_path = "/etc/passwd"
        
    with pytest.raises(ValidationError) as exc:
        resolve_safe_path(root, abs_path)
    
    assert exc.value.code.value == "E1xx"
