#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import asyncio
import json
import logging
import time

import pytest
from juju.errors import JujuAPIError
from pytest_operator.plugin import OpsTest

from ...helpers.helpers import (
    deploy_postgres_bundle,
    get_app_relation_databag,
    get_backend_relation,
    get_backend_user_pass,
    scale_application,
)
from ...helpers.postgresql_helpers import check_database_users_existence
from .helpers import (
    build_connection_string,
    check_new_relation,
    run_sql_on_application_charm,
)

logger = logging.getLogger(__name__)

CLIENT_APP_NAME = "application"
CLIENT_UNIT_NAME = f"{CLIENT_APP_NAME}/0"
TEST_DBNAME = "application_first_database"
ANOTHER_APPLICATION_APP_NAME = "another-application"
PG = "postgresql"
PG_2 = "another-postgresql"
PGB = "pgbouncer"
PGB_2 = "another-pgbouncer"
APP_NAMES = [CLIENT_APP_NAME, PG, PGB]
FIRST_DATABASE_RELATION_NAME = "first-database"
SECOND_DATABASE_RELATION_NAME = "second-database"
MULTIPLE_DATABASE_CLUSTERS_RELATION_NAME = "multiple-database-clusters"


@pytest.mark.abort_on_fail
async def test_database_relation_with_charm_libraries(ops_test: OpsTest, application_charm):
    """Test basic functionality of database relation interface."""
    # Deploy both charms (multiple units for each application to test that later they correctly
    # set data in the relation application databag using only the leader unit).
    async with ops_test.fast_forward():
        await asyncio.gather(
            ops_test.model.deploy(
                application_charm,
                application_name=CLIENT_APP_NAME,
                num_units=2,
            ),
            deploy_postgres_bundle(ops_test, timeout=1500),
        )
        await ops_test.model.wait_for_idle(apps=[CLIENT_APP_NAME, PG], timeout=1500)

    # Relate the charms and wait for them exchanging some connection data.
    global client_relation
    client_relation = await ops_test.model.add_relation(
        f"{CLIENT_APP_NAME}:{FIRST_DATABASE_RELATION_NAME}", PGB
    )
    async with ops_test.fast_forward():
        await ops_test.model.wait_for_idle(status="active")

    # Check we can add data
    await check_new_relation(
        ops_test,
        unit_name=ops_test.model.applications[CLIENT_APP_NAME].units[0].name,
        relation_id=client_relation.id,
        dbname=TEST_DBNAME,
    )


async def test_database_version(ops_test: OpsTest):
    """Check version is accurate."""
    version_query = "SELECT version();"
    run_version_query = await run_sql_on_application_charm(
        ops_test,
        unit_name=CLIENT_UNIT_NAME,
        query=version_query,
        dbname=TEST_DBNAME,
        relation_id=client_relation.id,
    )
    # Get the version of the database and compare with the information that was retrieved directly
    # from the database.
    app_unit = ops_test.model.applications[CLIENT_APP_NAME].units[0]
    databag = await get_app_relation_databag(ops_test, app_unit.name, client_relation.id)
    version = databag.get("version", None)
    assert version, f"Version is not available in databag: {databag}"
    assert version in json.loads(run_version_query["results"])[0][0]


async def test_database_admin_permissions(ops_test: OpsTest):
    """Test admin permissions."""
    create_database_query = "CREATE DATABASE another_database;"
    run_create_database_query = await run_sql_on_application_charm(
        ops_test,
        unit_name=CLIENT_UNIT_NAME,
        query=create_database_query,
        dbname=TEST_DBNAME,
        relation_id=client_relation.id,
    )
    assert "no results to fetch" in json.loads(run_create_database_query["results"])

    create_user_query = "CREATE USER another_user WITH ENCRYPTED PASSWORD 'test-password';"
    run_create_user_query = await run_sql_on_application_charm(
        ops_test,
        unit_name=CLIENT_UNIT_NAME,
        query=create_user_query,
        dbname=TEST_DBNAME,
        relation_id=client_relation.id,
    )
    assert "no results to fetch" in json.loads(run_create_user_query["results"])


async def test_no_read_only_endpoint_in_standalone_cluster(ops_test: OpsTest):
    """Test that there is no read-only endpoint in a standalone cluster."""
    await scale_application(ops_test, CLIENT_APP_NAME, 1)
    await check_new_relation(
        ops_test,
        unit_name=ops_test.model.applications[CLIENT_APP_NAME].units[0].name,
        relation_id=client_relation.id,
        dbname=TEST_DBNAME,
    )

    unit = ops_test.model.applications[CLIENT_APP_NAME].units[0]
    databag = await get_app_relation_databag(ops_test, unit.name, client_relation.id)
    assert not databag.get(
        "read-only-endpoints", None
    ), f"read-only-endpoints in pgb databag: {databag}"


async def test_no_read_only_endpoint_in_scaled_up_cluster(ops_test: OpsTest):
    """Test that there is read-only endpoint in a scaled up cluster."""
    await scale_application(ops_test, CLIENT_APP_NAME, 2)
    await check_new_relation(
        ops_test,
        unit_name=ops_test.model.applications[CLIENT_APP_NAME].units[0].name,
        relation_id=client_relation.id,
        dbname=TEST_DBNAME,
    )

    unit = ops_test.model.applications[CLIENT_APP_NAME].units[0]
    databag = await get_app_relation_databag(ops_test, unit.name, client_relation.id)
    assert not databag.get(
        "read-only-endpoints", None
    ), f"read-only-endpoints in pgb databag: {databag}"


async def test_two_applications_cant_relate_to_the_same_pgb(ops_test: OpsTest, application_charm):
    """Test that two different application connect to the database with different credentials."""
    # Set some variables to use in this test.
    all_app_names = [ANOTHER_APPLICATION_APP_NAME]
    all_app_names.extend(APP_NAMES)

    # Deploy another application.
    await ops_test.model.deploy(
        application_charm,
        application_name=ANOTHER_APPLICATION_APP_NAME,
    )
    await ops_test.model.wait_for_idle(status="active")

    # Try relate the new application with the database.
    try:
        await ops_test.model.add_relation(
            f"{ANOTHER_APPLICATION_APP_NAME}:{FIRST_DATABASE_RELATION_NAME}", PGB
        )
        assert False, "PGB was able to relate to a second application"
    except JujuAPIError:
        pass


async def test_an_application_can_request_multiple_databases(ops_test: OpsTest, application_charm):
    """Test that an application can request additional databases using the same interface.

    This occurs using a new relation per interface (for now).
    """
    # Relate the charms using another relation and wait for them exchanging some connection data.
    await ops_test.model.deploy(
        PGB,
        channel="edge",
        application_name=PGB_2,
        num_units=None,
        config={"listen_port": 7432},
    )
    await asyncio.gather(
        ops_test.model.add_relation(f"{PGB_2}:backend-database", f"{PG}:database"),
        ops_test.model.add_relation(f"{CLIENT_APP_NAME}:{SECOND_DATABASE_RELATION_NAME}", PGB_2),
    )
    async with ops_test.fast_forward():
        await ops_test.model.wait_for_idle(apps=APP_NAMES + [PGB, PGB_2], status="active")

    # Get the connection strings to connect to both databases.
    first_database_connection_string = await build_connection_string(
        ops_test, CLIENT_APP_NAME, FIRST_DATABASE_RELATION_NAME
    )
    second_database_connection_string = await build_connection_string(
        ops_test, CLIENT_APP_NAME, SECOND_DATABASE_RELATION_NAME
    )

    # Assert the two application have different relation (connection) data.
    assert first_database_connection_string != second_database_connection_string


async def test_scaling(ops_test: OpsTest):
    """Check these relations all work when scaling pgbouncer."""
    await scale_application(ops_test, CLIENT_APP_NAME, 1)
    await ops_test.model.wait_for_idle()
    await check_new_relation(
        ops_test,
        unit_name=ops_test.model.applications[CLIENT_APP_NAME].units[0].name,
        relation_id=client_relation.id,
        dbname=TEST_DBNAME,
    )

    await scale_application(ops_test, CLIENT_APP_NAME, 2)
    await ops_test.model.wait_for_idle()
    await check_new_relation(
        ops_test,
        unit_name=ops_test.model.applications[CLIENT_APP_NAME].units[0].name,
        relation_id=client_relation.id,
        dbname=TEST_DBNAME,
    )


@pytest.mark.unstable
async def test_relation_broken(ops_test: OpsTest):
    """Test that the user is removed when the relation is broken."""
    client_unit_name = ops_test.model.applications[CLIENT_APP_NAME].units[0].name
    # Retrieve the relation user.
    databag = await get_app_relation_databag(ops_test, client_unit_name, client_relation.id)
    relation_user = databag.get("username", None)
    logging.info(f"relation user: {relation_user}")
    assert relation_user, f"no relation user in client databag: {databag}"

    backend_rel = get_backend_relation(ops_test)
    pg_user, pg_pass = await get_backend_user_pass(ops_test, backend_rel)

    # Break the relation.
    await ops_test.model.applications[PGB].remove_relation(
        f"{PGB}:database", f"{CLIENT_APP_NAME}:{FIRST_DATABASE_RELATION_NAME}"
    )
    async with ops_test.fast_forward():
        await ops_test.model.wait_for_idle(apps=APP_NAMES, status="active", raise_on_blocked=True)

    time.sleep(10)
    # Check that the relation user was removed from the database.
    await check_database_users_existence(
        ops_test, [], [relation_user], pg_user=pg_user, pg_user_password=pg_pass
    )
