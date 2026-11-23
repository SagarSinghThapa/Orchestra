"""
Automated Security & Topology Verification for docker-compose.prod.yml and Operations Runbook.
"""

from pathlib import Path
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
PROD_COMPOSE_PATH = REPO_ROOT / "docker-compose.prod.yml"
DEPLOYMENT_MD_PATH = REPO_ROOT / "DEPLOYMENT.md"


def test_production_compose_file_exists_and_valid_yaml():
    """Verify docker-compose.prod.yml exists and parses as valid YAML."""
    assert PROD_COMPOSE_PATH.exists(), f"Missing production compose file at {PROD_COMPOSE_PATH}"
    content = PROD_COMPOSE_PATH.read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    assert isinstance(data, dict)
    assert "services" in data
    assert "networks" in data
    assert "volumes" in data


def test_production_compose_ports_and_edge_proxy():
    """Verify only reverse-proxy exposes ports 80 and 443, and no data ports are exposed."""
    data = yaml.safe_load(PROD_COMPOSE_PATH.read_text(encoding="utf-8"))
    services = data["services"]

    # 1. Reverse proxy must expose 80 and 443
    proxy = services.get("reverse-proxy")
    assert proxy is not None
    assert "80:80" in proxy.get("ports", [])
    assert "443:443" in proxy.get("ports", [])

    # 2. No other services may expose ports to the host
    for svc_name, svc_cfg in services.items():
        if svc_name == "reverse-proxy":
            continue
        assert "ports" not in svc_cfg, f"Insecure host port exposure found on {svc_name}"


def test_production_compose_data_network_internal():
    """Verify orchestra_data network is marked internal to prevent external ingress."""
    data = yaml.safe_load(PROD_COMPOSE_PATH.read_text(encoding="utf-8"))
    networks = data.get("networks", {})
    assert "orchestra_data" in networks
    assert networks["orchestra_data"].get("internal") is True


def test_production_compose_resource_limits():
    """Verify CPU and memory resource limits are defined on production containers."""
    data = yaml.safe_load(PROD_COMPOSE_PATH.read_text(encoding="utf-8"))
    services = data["services"]

    for svc_name in ["backend", "frontend", "postgres", "redis", "qdrant"]:
        cfg = services.get(svc_name, {})
        deploy = cfg.get("deploy", {})
        resources = deploy.get("resources", {})
        limits = resources.get("limits", {})
        assert "memory" in limits, f"Missing memory limit on {svc_name}"
        assert "cpus" in limits, f"Missing cpus limit on {svc_name}"


def test_production_compose_read_only_certificate_mount():
    """Verify production certificates are mounted read-only (:ro)."""
    data = yaml.safe_load(PROD_COMPOSE_PATH.read_text(encoding="utf-8"))
    proxy_volumes = data["services"]["reverse-proxy"].get("volumes", [])

    ro_cert_mount = False
    for v in proxy_volumes:
        if "/etc/nginx/certs/live:ro" in v:
            ro_cert_mount = True
            break
    assert ro_cert_mount, "Production certificates must be mounted with :ro flag"


def test_deployment_runbook_human_gated_destructive_protocol():
    """Verify DEPLOYMENT.md contains the human-gated destructive operations protocol."""
    assert DEPLOYMENT_MD_PATH.exists()
    content = DEPLOYMENT_MD_PATH.read_text(encoding="utf-8")

    assert "Human-Gated Destructive Operations Protocol" in content
    assert "Pre-Flight Verified Checksummed Backup" in content
    assert "sha256sum" in content
    assert "Migration Compatibility & Impact Analysis" in content
    assert "Explicit Human Operator Execution" in content
    assert "alembic downgrade" in content
