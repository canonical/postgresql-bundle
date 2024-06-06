# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

import pytest
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

ACTIVE_APPS = [
    "pgbouncer-data-integrator",
    "pgbouncer-test-app",
    "postgresql",
    "postgresql-test-app",
    "self-signed-certificates",
    "sysbench",
]
BLOCKED_APPS = [
    "data-integrator",
    "grafana-agent",
    "landscape-client",
    "s3-integrator",
    "ubuntu-advantage",
]


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_setup(ops_test: OpsTest):
    async with ops_test.fast_forward():
        await ops_test.model.deploy("./releases/latest/postgresql-bundle.yaml")
        await ops_test.model.applications["postgresql"].set_config({"profile": "testing"})
        await ops_test.model.wait_for_idle(
            apps=ACTIVE_APPS,
            status="active",
            timeout=3000,
        )
        await ops_test.model.wait_for_idle(
            apps=BLOCKED_APPS,
            status="blocked",
            timeout=100,
        )
