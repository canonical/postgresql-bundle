# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import time

import pytest
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

POSTGRES_NAME = "db"
TEST_APP_NAME = "app-int"
ACTIVE_APPS = [
    "app-ext",
    "app-ext-admin",
    "lb-ext",
    TEST_APP_NAME,
    "app-int-perf",
    "lb-int",
    POSTGRES_NAME,
    "tls",
]
BLOCKED_APPS = [
    "cos-agent-app-ext",
    "cos-agent-app-int",
    "cos-agent-app-int-perf",
    "cos-agent-db",
    "cos-agent-lb-ext",
    "cos-agent-lb-int",
    "lp-client",
    "s3",
    "ubuntu-pro",
]


@pytest.mark.group(1)
@pytest.mark.abort_on_fail
async def test_setup(ops_test: OpsTest):
    async with ops_test.fast_forward():
        await ops_test.model.deploy("./releases/latest/postgresql-bundle.yaml")
        await ops_test.model.applications[POSTGRES_NAME].set_config({"profile": "testing"})
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

    logger.info("Test continuous writes")
    await (
        await ops_test.model.applications[TEST_APP_NAME]
        .units[0]
        .run_action("start-continuous-writes")
    ).wait()

    time.sleep(10)

    results = await (
        await ops_test.model.applications[TEST_APP_NAME]
        .units[0]
        .run_action("stop-continuous-writes")
    ).wait()

    writes = int(results.results["writes"])
    assert writes > 0

    params = {
        "dbname": f"{TEST_APP_NAME.replace('-', '_')}_database",
        "query": "SELECT COUNT(number), MAX(number) FROM continuous_writes;",
        "relation-name": "database",
        "readonly": False,
    }
    results = await (
        await ops_test.model.applications[TEST_APP_NAME].units[0].run_action("run-sql", **params)
    ).wait()
    count, maximum = results.results["results"].strip("[]").split(", ")
    count = int(count)
    maximum = int(maximum)

    assert writes == count == maximum
