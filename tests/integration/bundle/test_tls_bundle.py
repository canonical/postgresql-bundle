# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

from pytest_operator.plugin import OpsTest

from constants import PG, PGB

from ..helpers.helpers import (
    deploy_postgres_bundle,
    get_backend_relation,
    get_backend_user_pass,
    wait_for_relation_joined_between,
)
from ..helpers.postgresql_helpers import (
    enable_connections_logging,
    get_postgres_primary,
    run_command_on_unit,
)

logger = logging.getLogger(__name__)


MAILMAN3 = "mailman3-core"


async def test_tls(ops_test: OpsTest):
    await deploy_postgres_bundle(ops_test)

    async with ops_test.fast_forward():
        await ops_test.model.applications[PGB].set_config({"listen_port": "5432"})
        await ops_test.model.wait_for_idle(apps=[PGB], status="active", timeout=600)
        relation = get_backend_relation(ops_test)
        pgb_user, _ = await get_backend_user_pass(ops_test, relation)

        # Enable additional logs on the PostgreSQL instance to check TLS
        # being used in a later step.
        enable_connections_logging(ops_test, f"{PG}/0")

        # Deploy an app and relate it to PgBouncer to open a connection
        # between PgBouncer and PostgreSQL.
        async with ops_test.fast_forward():
            await ops_test.model.deploy(MAILMAN3)
            await ops_test.model.add_relation(f"{PGB}:db", f"{MAILMAN3}:db")
            wait_for_relation_joined_between(ops_test, PGB, MAILMAN3)
            await ops_test.model.wait_for_idle(
                apps=[PG, PGB, MAILMAN3], status="active", timeout=1000
            )

        # Check the logs to ensure TLS is being used by PgBouncer.
        postgresql_primary_unit = await get_postgres_primary(ops_test)
        logs = await run_command_on_unit(
            ops_test, postgresql_primary_unit, "journalctl -u patroni.service"
        )
        assert (
            f"connection authorized: user={pgb_user} database=mailman3 SSL enabled"
            " (protocol=TLSv1.3, cipher=TLS_AES_256_GCM_SHA384, bits=256, compression=off)" in logs
        ), f"TLS is not being used on connections to PostgreSQL for user {pgb_user}"
