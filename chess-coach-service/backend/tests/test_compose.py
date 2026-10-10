from pathlib import Path

import yaml


def test_backend_maps_local_ai_hostname_to_linux_host_gateway():
    compose = yaml.safe_load((Path(__file__).parents[2] / "docker-compose.yml").read_text())
    assert "host.docker.internal:host-gateway" in compose["services"]["backend"]["extra_hosts"]