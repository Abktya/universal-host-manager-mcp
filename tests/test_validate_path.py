"""_validate_path()'in workspace disina cikisi engelledigini dogrular."""

import pytest

from universal_host_manager_mcp import server


def test_relative_path_resolves_inside_workspace():
    result = server._validate_path("foo.txt")
    assert result.parent == server.WORKSPACE_ROOT


def test_parent_traversal_is_rejected():
    with pytest.raises(PermissionError):
        server._validate_path("../outside.txt")


def test_absolute_path_outside_workspace_is_rejected():
    with pytest.raises(PermissionError):
        server._validate_path("/etc/passwd")


def test_workspace_root_itself_is_allowed():
    result = server._validate_path(".")
    assert result == server.WORKSPACE_ROOT
