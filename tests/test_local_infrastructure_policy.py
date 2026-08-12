import json
import subprocess
from pathlib import Path
from typing import Any, cast


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PATH = ROOT / "infra" / "compose.yaml"
EXPECTED_IMAGES = {
    "alertmanager": "prom/alertmanager:v0.28.1",
    "etcd": "quay.io/coreos/etcd:v3.5.18",
    "minio": "minio/minio:RELEASE.2024-12-18T13-15-44Z",
    "milvus": "milvusdb/milvus:v3.0-beta",
    "attu": "zilliz/attu:v2.5.12",
}


def _compose_config() -> dict[str, Any]:
    result = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_PATH), "config", "--format", "json"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return cast(dict[str, Any], json.loads(result.stdout))


def test_compose_has_exact_services_images_healthchecks_and_persistent_volumes() -> None:
    config = _compose_config()
    services = cast(dict[str, dict[str, Any]], config["services"])

    assert set(services) == set(EXPECTED_IMAGES)
    assert {name: service["image"] for name, service in services.items()} == EXPECTED_IMAGES
    assert all("healthcheck" in service for service in services.values())

    volumes = cast(dict[str, object], config["volumes"])
    for name in EXPECTED_IMAGES:
        mounts = cast(list[dict[str, Any]], services[name]["volumes"])
        assert any(mount.get("type") == "volume" for mount in mounts)
    assert set(volumes) == {
        "alertmanager_data",
        "attu_data",
        "etcd_data",
        "milvus_data",
        "minio_data",
    }


def test_compose_dependency_graph_and_alertmanager_read_only_config() -> None:
    services = cast(dict[str, dict[str, Any]], _compose_config()["services"])

    assert services["milvus"]["depends_on"] == {
        "etcd": {"condition": "service_healthy", "required": True},
        "minio": {"condition": "service_healthy", "required": True},
    }
    assert services["attu"]["depends_on"] == {
        "milvus": {"condition": "service_healthy", "required": True},
    }
    assert services["milvus"]["environment"]["ETCD_ENDPOINTS"] == "etcd:2379"
    assert services["milvus"]["environment"]["MINIO_ADDRESS"] == "minio:9000"

    alertmanager = services["alertmanager"]
    assert any(port["published"] == "9093" for port in alertmanager["ports"])
    assert any(
        mount.get("source", "").endswith("infra/alertmanager/alertmanager.yml")
        and mount.get("target") == "/etc/alertmanager/alertmanager.yml"
        and mount.get("read_only") is True
        for mount in alertmanager["volumes"]
    )


def test_compose_and_repository_reject_legacy_full_stack_assets() -> None:
    raw = COMPOSE_PATH.read_text(encoding="utf-8")
    lowered = raw.lower()
    for forbidden in (
        "env_file",
        "${",
        "cls-mcp-server",
        "log-upload",
        "sop-seed",
    ):
        assert forbidden not in lowered

    config = _compose_config()
    assert "backend" not in config["services"]
    assert "frontend" not in config["services"]
    assert not list(ROOT.rglob("app.Dockerfile"))
    assert not list(ROOT.rglob("project.compose.json"))


def test_templates_do_not_duplicate_compose_image_versions() -> None:
    for path in (
        ROOT / "config" / "project.template.json",
        ROOT / "config" / "user.project.template.json",
    ):
        template = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
        assert "docker" not in template
        serialized = json.dumps(template)
        for legacy_key in ("appImageTag", "clsMcpServerVersion", "milvusImage"):
            assert legacy_key not in serialized
