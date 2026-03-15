"""Architecture tests — validate hexagonal layer boundaries."""

import ast
from pathlib import Path

import pytest

_SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "discord_against_humanity"

_DOMAIN_MODULES = [
    _SRC_ROOT / "domain" / "document.py",
    _SRC_ROOT / "domain" / "cards.py",
    _SRC_ROOT / "domain" / "game.py",
    _SRC_ROOT / "domain" / "player.py",
]

_ADAPTER_MODULES = [
    _SRC_ROOT / "adapters" / "commands" / "cah.py",
    _SRC_ROOT / "adapters" / "checks" / "game_checks.py",
]

_PORT_IMPL_MODULE = _SRC_ROOT / "ports" / "valkey.py"


def _extract_imports(filepath: Path) -> list[str]:
    """Return fully-qualified module strings from all imports in *filepath*."""
    tree = ast.parse(filepath.read_text(), filename=str(filepath))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.append(node.module)
    return modules


# ── Domain purity ────────────────────────────────────────────────────────────


class TestDomainPurity:
    """Domain modules must not depend on adapters or concrete port impls."""

    @pytest.mark.parametrize(
        "module_path",
        _DOMAIN_MODULES,
        ids=[p.stem for p in _DOMAIN_MODULES],
    )
    def test_domain_does_not_import_adapters(self, module_path: Path):
        imports = _extract_imports(module_path)
        adapter_imports = [
            m for m in imports if "discord_against_humanity.adapters" in m
        ]
        assert adapter_imports == [], (
            f"{module_path.name} imports adapter modules: {adapter_imports}"
        )

    @pytest.mark.parametrize(
        "module_path",
        _DOMAIN_MODULES,
        ids=[p.stem for p in _DOMAIN_MODULES],
    )
    def test_domain_does_not_import_valkey(self, module_path: Path):
        imports = _extract_imports(module_path)
        valkey_imports = [
            m for m in imports if "discord_against_humanity.ports.valkey" in m
        ]
        assert valkey_imports == [], (
            f"{module_path.name} imports concrete port: {valkey_imports}"
        )

    @pytest.mark.parametrize(
        "module_path",
        _DOMAIN_MODULES,
        ids=[p.stem for p in _DOMAIN_MODULES],
    )
    def test_domain_only_imports_allowed_packages(self, module_path: Path):
        """Domain may import from ports.repository, utils, domain, or stdlib."""
        imports = _extract_imports(module_path)
        internal = [
            m
            for m in imports
            if m.startswith("discord_against_humanity")
        ]
        for mod in internal:
            allowed = (
                mod.startswith("discord_against_humanity.ports.repository")
                or mod.startswith("discord_against_humanity.domain")
                or mod.startswith("discord_against_humanity.utils")
            )
            assert allowed, (
                f"{module_path.name} has disallowed internal import: {mod}"
            )


# ── Adapter → Domain dependency ─────────────────────────────────────────────


class TestAdapterDependsOnDomain:
    """Adapter modules should import from the domain layer."""

    @pytest.mark.parametrize(
        "module_path",
        _ADAPTER_MODULES,
        ids=[p.stem for p in _ADAPTER_MODULES],
    )
    def test_adapter_imports_domain(self, module_path: Path):
        imports = _extract_imports(module_path)
        domain_imports = [
            m for m in imports if "discord_against_humanity.domain" in m
        ]
        assert domain_imports, (
            f"{module_path.name} does not import any domain module"
        )


# ── Port implementation → Port interface ─────────────────────────────────────


class TestPortImplDependsOnInterface:
    """The concrete port (valkey) must import from the abstract port."""

    def test_valkey_imports_repository(self):
        imports = _extract_imports(_PORT_IMPL_MODULE)
        repo_imports = [
            m
            for m in imports
            if "discord_against_humanity.ports.repository" in m
        ]
        assert repo_imports, "valkey.py does not import from ports.repository"


# ── No circular dependencies ────────────────────────────────────────────────


class TestNoCircularDependencies:
    """Domain must never import from adapters (no cycles)."""

    @pytest.mark.parametrize(
        "module_path",
        _DOMAIN_MODULES,
        ids=[p.stem for p in _DOMAIN_MODULES],
    )
    def test_no_domain_to_adapter_cycle(self, module_path: Path):
        imports = _extract_imports(module_path)
        adapter_imports = [
            m for m in imports if "discord_against_humanity.adapters" in m
        ]
        assert adapter_imports == [], (
            f"Circular dependency: {module_path.name} → adapters: "
            f"{adapter_imports}"
        )

    def test_port_interface_does_not_import_adapters(self):
        repo_path = _SRC_ROOT / "ports" / "repository.py"
        imports = _extract_imports(repo_path)
        adapter_imports = [
            m for m in imports if "discord_against_humanity.adapters" in m
        ]
        assert adapter_imports == [], (
            f"Circular dependency: repository.py → adapters: {adapter_imports}"
        )
