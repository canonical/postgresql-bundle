# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
import logging

import pytest
from pytest_operator.plugin import OpsTest

from constants import PG, PGB

from ..helpers.helpers import (
    CLIENT_APP_NAME,
    deploy_postgres_bundle,
    get_app_relation_databag,
    get_backend_relation,
    get_backend_user_pass,
    get_cfg,
    scale_application,
)
from ..helpers.postgresql_helpers import check_databases_creation

logger = logging.getLogger(__name__)
FIRST_DATABASE_RELATION_NAME = "first-database"
TEST_DBNAME = "postgresql_test_app_first_database"


@pytest.mark.abort_on_fail
async def test_setup(ops_test: OpsTest):
    """Deploy bundle and set up mailman for testing.

    We're adding an application to ensure that related applications stay online during service
    interruptions.
    """
    async with ops_test.fast_forward():
        await asyncio.gather(
            ops_test.model.deploy(
                CLIENT_APP_NAME,
                application_name=CLIENT_APP_NAME,
                num_units=2,
                series="jammy",
                channel="edge",
            ),
            deploy_postgres_bundle(ops_test, scale_postgres=3, timeout=1500),
        )
        await ops_test.model.wait_for_idle(apps=[CLIENT_APP_NAME, PG], timeout=1500)
        await ops_test.model.add_relation(f"{CLIENT_APP_NAME}:{FIRST_DATABASE_RELATION_NAME}", PGB)

        await ops_test.model.wait_for_idle(status="active")

    pgb_user, pgb_pass = await get_backend_user_pass(ops_test, get_backend_relation(ops_test))
    await check_databases_creation(ops_test, [TEST_DBNAME], pgb_user, pgb_pass)


async def test_kill_pg_primary(ops_test: OpsTest):
    """Kill primary, check that all proxy instances switched traffic for a new primary."""
    # Get postgres primary through action
    unit_name = ops_test.model.applications[PG].units[0].name
    action = await ops_test.model.units.get(unit_name).run_action("get-primary")
    action = await action.wait()
    primary = action.results["primary"]

    # Get primary connection string from each pgbouncer unit and assert they're pointing to the
    # correct PG primary
    old_primary_ip = ops_test.model.units.get(primary).public_address
    for unit in ops_test.model.applications[PGB].units:
        unit_cfg = await get_cfg(ops_test, unit.name)
        assert unit_cfg["databases"][TEST_DBNAME]["host"] == old_primary_ip

    await ops_test.model.destroy_units(primary)
    await ops_test.model.wait_for_idle(
        apps=[PG, PGB, CLIENT_APP_NAME], status="active", timeout=600
    )

    # Assert pgbouncer config points to the new correct primary
    unit_name = ops_test.model.applications[PG].units[0].name
    action = await ops_test.model.units.get(unit_name).run_action("get-primary")
    action = await action.wait()
    new_primary = action.results["primary"]
    new_primary_ip = ops_test.model.units.get(new_primary).public_address
    assert new_primary_ip != old_primary_ip
    for unit in ops_test.model.applications[PGB].units:
        unit_cfg = await get_cfg(ops_test, unit.name)
        assert unit_cfg["databases"][TEST_DBNAME]["host"] == new_primary_ip


async def test_discover_dbs(ops_test: OpsTest):
    """Check that proxy discovers new members when scaling up postgres charm."""
    await scale_application(ops_test, PG, 3)
    # Get postgres primary through action
    unit_name = ops_test.model.applications[PG].units[0].name
    action = await ops_test.model.units.get(unit_name).run_action("get-primary")
    action = await action.wait()
    primary = action.results["primary"]

    pgb_unit = ops_test.model.applications[PGB].units[0].name
    # Check existing relation data
    initial_relation = get_backend_relation(ops_test)
    backend_databag = await get_app_relation_databag(ops_test, pgb_unit, initial_relation.id)
    logging.info(backend_databag)
    read_only_endpoints = backend_databag["read-only-endpoints"].split(",")
    assert len(read_only_endpoints) == 2
    existing_endpoints = [
        f"{unit.public_address}:5432" if unit.name != primary else None
        for unit in ops_test.model.applications[PG].units
    ]
    existing_endpoints.remove(None)
    assert set(read_only_endpoints) == set(existing_endpoints)

    # Add a new unit
    await scale_application(ops_test, PG, 4)

    # check relation databag updates after adding a new unit
    updated_relation = get_backend_relation(ops_test)
    updated_backend_databag = await get_app_relation_databag(
        ops_test, pgb_unit, updated_relation.id
    )
    logging.info(updated_backend_databag)
    read_only_endpoints = updated_backend_databag["read-only-endpoints"].split(",")
    assert len(read_only_endpoints) == 3
    existing_endpoints = [
        f"{unit.public_address}:5432" if unit.name != primary else None
        for unit in ops_test.model.applications[PG].units
    ]
    existing_endpoints.remove(None)
    assert set(read_only_endpoints) == set(existing_endpoints)
