"""The compose stack must actually serve the API it advertises.

Audit DEP-01. ``docker-compose.yml`` built the ``backend`` service from the
repository-root ``Dockerfile``, whose CMD is ``python -m ingestion.main`` — a
long-running ingestion engine that never binds a port. The service still
published ``8000:8000`` and the frontend pointed ``NEXT_PUBLIC_API_URL`` at
``http://backend:8000``, so every deployment answered 502 with the health probe
of the API image never running.

These are static checks on the compose file and the Dockerfiles: they need no
daemon and no network. Runtime proof (a container answering
``/api/v1/health``) remains a separate, BLOCKED acceptance step.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.yml"


@pytest.fixture(scope="module")
def services() -> dict:
    data = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    return data["services"]


def test_backend_builds_the_api_image(services: dict) -> None:
    build = services["backend"]["build"]

    assert build["dockerfile"] == "Dockerfile.api", (
        "backend must build Dockerfile.api; the root Dockerfile runs ingestion.main "
        "and never binds port 8000"
    )


def test_backend_publishes_the_api_port(services: dict) -> None:
    assert "8000:8000" in services["backend"]["ports"]


def test_api_image_runs_uvicorn_on_the_published_port() -> None:
    dockerfile = (ROOT / "Dockerfile.api").read_text(encoding="utf-8")

    assert "apps.api.app:app" in dockerfile
    assert "uvicorn" in dockerfile
    assert '"8000"' in dockerfile


def test_ingestion_entrypoint_keeps_its_own_service(services: dict) -> None:
    """Moving the API off the root image must not drop the ingestion process."""
    ingestion = services["ingestion"]

    assert ingestion["build"]["dockerfile"] == "Dockerfile"
    assert "INGESTION_DB_DSN" in " ".join(ingestion["environment"])
    assert "INGESTION_REDIS_URL" in " ".join(ingestion["environment"])


def test_dead_ingestion_env_is_not_left_on_the_api_service(services: dict) -> None:
    """The API never imports ``ingestion``; those vars only belong to the engine."""
    environment = " ".join(services["backend"]["environment"])

    assert "INGESTION_DB_DSN" not in environment
    assert "INGESTION_REDIS_URL" not in environment


def test_build_dockerfiles_exist_for_the_api_and_ingestion(services: dict) -> None:
    for name in ("backend", "ingestion"):
        build = services[name]["build"]
        context = ROOT / build.get("context", ".")
        assert (context / build["dockerfile"]).is_file(), f"{name}: missing {build['dockerfile']}"


def test_every_base_service_builds_from_a_file_that_exists(services: dict) -> None:
    """Audit DEP-02: ``frontend`` pointed at ``./frontend/Dockerfile`` (absent)."""
    missing: list[str] = []
    for name, service in services.items():
        build = service.get("build")
        if not build:
            continue
        context = ROOT / str(build.get("context", "."))
        dockerfile = build.get("dockerfile", "Dockerfile")
        if not (context / dockerfile).is_file():
            missing.append(f"{name}: {context / dockerfile}")

    assert not missing, "compose build targets missing:\n  " + "\n  ".join(missing)


@pytest.fixture(scope="module")
def override_services() -> dict:
    path = ROOT / "docker-compose.override.yml"
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8"))["services"]


def test_override_only_targets_services_defined_in_base(
    services: dict, override_services: dict
) -> None:
    """An override entry for an unknown service makes the whole project invalid."""
    unknown = set(override_services) - set(services)

    assert not unknown, (
        f"docker-compose.override.yml declares services absent from docker-compose.yml: "
        f"{sorted(unknown)} — compose cannot materialise a service without image/build"
    )


def test_override_build_contexts_exist(override_services: dict) -> None:
    for name, service in override_services.items():
        build = service.get("build")
        if not build:
            continue
        context = ROOT / str(build.get("context", "."))
        dockerfile = build.get("dockerfile", "Dockerfile")
        assert (context / dockerfile).is_file(), f"{name}: missing {context / dockerfile}"
