# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
import logging

import pytest
from pytest_operator.plugin import OpsTest
from mailmanclient import Client
from constants import PG, PGB

from tests.integration.helpers.helpers import (
    deploy_postgres_bundle,
    scale_application,
    deploy_and_relate_application_with_pgbouncer

)

logger = logging.getLogger(__name__)

MAILMAN3_CORE_APP_NAME = "mailman3-core"

@pytest.mark.bundle
@pytest.mark.abort_on_fail
async def deploy_bundle(ops_test: OpsTest):
    """Deploy bundle and set up mailman for testing.

    We're adding an application to ensure that related applications stay online during service
    interruptions.
    """
    async with ops_test.fast_forward():
        await deploy_postgres_bundle(ops_test)
        await asyncio.gather(
            scale_application(ops_test, PG, 3),
            scale_application(ops_test, PGB, 3),
        )
        await ops_test.model.applications[PGB].set_config({"listen_port": "5432"})
        await ops_test.model.wait_for_idle(
            apps=[PG], status="active", timeout=600
        )

        # Extra config option for Mailman3 Core.
        mailman_config = {"hostname": "example.org"}
        # Deploy and test the deployment of Mailman3 Core.
        db_relation = await deploy_and_relate_application_with_pgbouncer(
            ops_test,
            MAILMAN3_CORE_APP_NAME,
            MAILMAN3_CORE_APP_NAME,
            1,
            mailman_config,
        )

    # Assert Mailman3 Core is configured to use PostgreSQL instead of SQLite.
    mailman_unit = ops_test.model.applications[MAILMAN3_CORE_APP_NAME].units[0]
    action = await mailman_unit.run("mailman info")
    result = action.results.get("Stdout", action.results.get("Stderr", None))
    assert "db url: postgres://" in result, f"no postgres db url, Stderr: {result}"


@pytest.mark.bundle
async def test_kill_pg_primary(ops_test: OpsTest):
    """Kill primary, check that all proxy instances switched traffic for a new primary."""

    # TODO kill primary
    # Get postgres primary through action
    unit_name = ops_test.model.applications[PG].units[0].name
    action = await ops_test.model.units.get(unit_name).run_action("get-primary")
    action = await action.wait()
    primary = action.results["primary"]

    await ops_test.model.destroy_units(primary)
    await ops_test.model.wait_for_idle(apps=[PG, PGB, MAILMAN3_CORE_APP_NAME], status="active", timeout=600)

    # Do some CRUD operations using Mailman3 Core client to ensure it's still working.
    mailman_unit = ops_test.model.applications[MAILMAN3_CORE_APP_NAME].units[0]
    action = await mailman_unit.run("mailman info")
    result = action.results.get("Stdout", action.results.get("Stderr", None))
    domain_name = "canonical.com"
    credentials = (
        result.split("credentials: ")[1].strip().split(":")
    )  # This outputs a list containing username and password.
    client = Client(
        f"http://{mailman_unit.public_address}:8001/3.1", credentials[0], credentials[1]
    )

    # Create a domain and list the domains to check that the new one is there.
    domain = client.create_domain(domain_name)
    assert domain_name in [domain.mail_host for domain in client.domains]
