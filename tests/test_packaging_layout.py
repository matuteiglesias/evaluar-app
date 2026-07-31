from pathlib import Path


def test_python_package_directories_are_valid_identifiers():
    root = Path(__file__).resolve().parents[1]
    package_directories = {
        init.parent.relative_to(root)
        for init in root.rglob("__init__.py")
        if ".venv" not in init.parts
    }
    assert package_directories
    for directory in package_directories:
        assert all(part.isidentifier() for part in directory.parts), directory


def test_evaluar_is_an_importable_src_package():
    import evaluar

    assert Path(evaluar.__file__).resolve().name == "__init__.py"


def test_phase2_distribution_excludes_legacy_runtime():
    import tomllib

    root = Path(__file__).resolve().parents[1]
    configuration = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    wheel = configuration["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert wheel["packages"] == ["src/evaluar"]

    production_dependencies = configuration["project"]["dependencies"]
    forbidden = ("flask", "firebase", "authlib", "openai", "oauthlib", "pandas")
    assert not any(
        dependency.lower().startswith(forbidden) for dependency in production_dependencies
    )

    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    for legacy_directory in ("llm", "models", "routes", "services"):
        assert f"COPY {legacy_directory} " not in dockerfile
