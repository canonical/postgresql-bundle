# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
import logging

import pytest
from pytest_operator.plugin import OpsTest

from constants import PG, PGB
from tests.integration.helpers.helpers import (
    deploy_postgres_bundle,
    get_app_relation_databag,
    run_sql,
    wait_for_relation_joined_between,
)

logger = logging.getLogger(__name__)
PSQL = "psql"


@pytest.mark.dev
@pytest.mark.bundle
@pytest.mark.abort_on_fail
async def test_read_distribution(ops_test: OpsTest):
    """Check that read instance changed during reconnection to proxy.

    Each new read connection should connect to a new readonly node.
    """
    async with ops_test.fast_forward():
        await asyncio.gather(
            await deploy_postgres_bundle(ops_test, scale_postgres=3),
            await ops_test.model.deploy(
                "postgresql-charmers-postgresql-client",
                application_name=PSQL,
            ),
        )

        psql_relation = await ops_test.model.relate(f"{PSQL}:db", f"{PGB}:db-admin")
        wait_for_relation_joined_between(ops_test, PGB, PSQL)
        await ops_test.model.wait_for_idle(
            apps=[PSQL, PG, PGB],
            status="active",
            timeout=600,
        )

    unit_name = f"{PSQL}/0"
    psql_databag = await get_app_relation_databag(ops_test, unit_name, psql_relation.id)
    pgpass = psql_databag.get("password")
    user = psql_databag.get("user")
    host = psql_databag.get("host")
    port = psql_databag.get("port")
    dbname = f"{psql_databag.get('database')}_standby"
    assert None not in [pgpass, user, host, port, dbname], "databag incorrectly populated"

    user_command = "SELECT reset_val FROM pg_settings WHERE name='listen_addresses';"
    # get first IP
    rtn, first_ip, err = await run_sql(
        ops_test, unit_name, user_command, pgpass, user, host, port, dbname
    )
    assert rtn == 0, f"failed to run admin command {user_command}, {err}"

    # get second IP
    rtn, second_ip, err = await run_sql(
        ops_test, unit_name, user_command, pgpass, user, host, port, dbname
    )
    assert rtn == 0, f"failed to run admin command {user_command}, {err}"

    assert first_ip != second_ip
