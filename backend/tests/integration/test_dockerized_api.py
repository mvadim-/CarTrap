from pathlib import Path


def test_docker_artifacts_exist() -> None:
    root = Path(__file__).resolve().parents[3]

    assert (root / "backend" / "Dockerfile").exists()
    assert (root / "frontend" / "Dockerfile").exists()
    assert (root / "docker-compose.yml").exists()
