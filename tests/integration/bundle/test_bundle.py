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
    get_app_relation_databag,
    get_backend_relation,
    scale_application,
    deploy_and_relate_application_with_pgbouncer,
    get_backend_relation,
    get_backend_user_pass,
    get_legacy_relation_username
)

from tests.integration.helpers.postgresql_helpers import check_databases_creation, check_database_users_existence

logger = logging.getLogger(__name__)

MAILMAN3_CORE_APP_NAME = "mailman3-core"

@pytest.mark.bundle
@pytest.mark.abort_on_fail
async def test_setup(ops_test: OpsTest):
    """Deploy bundle and set up mailman for testing.

    We're adding an application to ensure that related applications stay online during service
    interruptions.
    """
    await deploy_postgres_bundle(ops_test)
    await asyncio.gather(
        scale_application(ops_test, PG, 3),
        scale_application(ops_test, PGB, 3),
    )

    async with ops_test.fast_forward():
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

    pgb_user, pgb_pass = await get_backend_user_pass(ops_test, get_backend_relation(ops_test))
    await check_databases_creation(ops_test, ["mailman3"], pgb_user, pgb_pass)

    mailman3_core_users = get_legacy_relation_username(ops_test, db_relation.id)
    await check_database_users_existence(
        ops_test, [mailman3_core_users], [], pgb_user, pgb_pass
    )

    # Assert Mailman3 Core is configured to use PostgreSQL instead of SQLite.
    mailman_unit = ops_test.model.applications[MAILMAN3_CORE_APP_NAME].units[0]
    action = await mailman_unit.run("mailman info")
    result = action.results.get("Stdout", action.results.get("Stderr", None))
    assert "db url: postgres://" in result, f"no postgres db url, Stderr: {result}"


@pytest.mark.bundle
async def test_kill_pg_primary(ops_test: OpsTest):
    """Kill primary, check that all proxy instances switched traffic for a new primary.

    TODO mailman doesn't connect to all proxy instances. Spool through proxy instances and verify
    (using their databags) that all proxy instances have switched to a new primary.
    """
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
    client.create_domain(domain_name)
    assert domain_name in [domain.mail_host for domain in client.domains]


@pytest.mark.bundle
async def test_discover_dbs(ops_test: OpsTest):
    """Check that proxy discovers new members when scaling up postgres charm."""
    # Check existing relation data
    initial_relation = get_backend_relation(ops_test)
    # Get postgres primary through action
    unit_name = ops_test.model.applications[PG].units[0].name
    action = await ops_test.model.units.get(unit_name).run_action("get-primary")
    action = await action.wait()
    primary = action.results["primary"]

    pgb_unit = ops_test.model.applications[PGB].units[0].name
    backend_databag = get_app_relation_databag(ops_test, pgb_unit, initial_relation.id)
    read_only_endpoints = backend_databag["read-only-endpoints"].split(",")
    assert len(read_only_endpoints) == 2
    for unit in ops_test.model.applications[PG].units:
        if unit.name == primary:
            continue
        unit_addr = f"{unit.public_address}:5432"
        if unit_addr in read_only_endpoints:
            read_only_endpoints.remove(unit_addr)
        else:
            assert False, f"unit addr: {unit_addr} not in read_only_endpoints {read_only_endpoints}"

    assert read_only_endpoints == []

    # Add a new unit
    scale_application(ops_test, PG, 4)

    # check relation databag updates after adding a new unit
    updated_relation = get_backend_relation(ops_test)
    updated_backend_databag = get_app_relation_databag(ops_test, pgb_unit, updated_relation.id)
    read_only_endpoints = updated_backend_databag["read-only-endpoints"].split(",")
    assert len(read_only_endpoints) == 3
    for unit in ops_test.model.applications[PG].units:
        if unit.name == primary:
            continue
        unit_addr = f"{unit.public_address}:5432"
        if unit_addr in read_only_endpoints:
            read_only_endpoints.remove(unit_addr)
        else:
            assert False, f"unit addr: {unit_addr} not in read_only_endpoints {read_only_endpoints}"

    assert read_only_endpoints == []
