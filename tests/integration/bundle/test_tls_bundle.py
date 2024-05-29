# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

import pytest
from pytest_operator.plugin import OpsTest

from constants import PG, PGB

from ..helpers.helpers import (
    deploy_and_relate_application_with_pgbouncer,
    deploy_postgres_bundle,
    get_backend_relation,
    get_backend_user_pass,
)
from ..helpers.postgresql_helpers import (
    enable_connections_logging,
    get_postgres_primary,
    run_command_on_unit,
)

logger = logging.getLogger(__name__)

MAILMAN3_CORE_APP_NAME = "mailman3-core"


@pytest.mark.group(1)
async def test_none():
    pass


@pytest.mark.unstable
@pytest.mark.group(1)
async def test_tls(ops_test: OpsTest):
    await deploy_postgres_bundle(ops_test, focal=True)

    async with ops_test.fast_forward():
        # Enable additional logs on the PostgreSQL instance to check TLS
        # being used in a later step.
        enable_connections_logging(ops_test, f"{PG}/0")

        # Deploy an app and relate it to PgBouncer to open a connection
        # between PgBouncer and PostgreSQL.
        async with ops_test.fast_forward():
            await deploy_and_relate_application_with_pgbouncer(
                ops_test,
                MAILMAN3_CORE_APP_NAME,
                MAILMAN3_CORE_APP_NAME,
                series="focal",
            )
            await ops_test.model.wait_for_idle(
                apps=[PG, PGB, MAILMAN3_CORE_APP_NAME], status="active", timeout=1000
            )
        relation = get_backend_relation(ops_test)
        pgb_user, _ = await get_backend_user_pass(ops_test, relation)

        # Check the logs to ensure TLS is being used by PgBouncer.
        postgresql_primary_unit = await get_postgres_primary(ops_test)
        mailman_ssl_log = f"connection authorized: user={pgb_user} database=mailman3 SSL enabled"
        postgresql_logs = "/var/snap/charmed-postgresql/common/var/log/postgresql/postgresql-*.log"
        await run_command_on_unit(
            ops_test,
            postgresql_primary_unit,
            f"grep '{mailman_ssl_log}' {postgresql_logs}",
        )
