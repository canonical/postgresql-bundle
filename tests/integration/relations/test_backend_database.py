# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
import logging

from pytest_operator.plugin import OpsTest
from tenacity import RetryError, Retrying, stop_after_delay, wait_fixed

from constants import BACKEND_RELATION_NAME, PG, PGB

from ..helpers.helpers import (
    CLIENT_APP_NAME,
    FIRST_DATABASE_RELATION_NAME,
    deploy_postgres_bundle,
    get_app_relation_databag,
    get_backend_relation,
    get_backend_user_pass,
    get_cfg,
    wait_for_relation_removed_between,
)
from ..helpers.postgresql_helpers import check_database_users_existence

logger = logging.getLogger(__name__)


async def test_relate_pgbouncer_to_postgres(ops_test: OpsTest, application_charm):
    """Test that the pgbouncer and postgres charms can relate to one another."""
    # Build, deploy, and relate charms.
    await deploy_postgres_bundle(ops_test)
    async with ops_test.fast_forward():
        await ops_test.model.deploy(application_charm, application_name=CLIENT_APP_NAME)
        # Relate the charms and wait for them exchanging some connection data.
        await ops_test.model.add_relation(f"{CLIENT_APP_NAME}:{FIRST_DATABASE_RELATION_NAME}", PGB)
        # Pgbouncer enters a blocked status without a postgres backend database relation
        await ops_test.model.wait_for_idle(apps=[PGB], status="active", timeout=600)
    relation = get_backend_relation(ops_test)

    cfg = await get_cfg(ops_test, f"{PGB}/0")
    logger.info(cfg.render())
    pgb_user, pgb_password = await get_backend_user_pass(ops_test, relation)
    assert pgb_user in cfg["pgbouncer"]["admin_users"]
    assert cfg["pgbouncer"]["auth_query"]

    await check_database_users_existence(ops_test, [pgb_user], [], pgb_user, pgb_password)

    # Remove relation but keep pg application because we're going to need it for future tests.
    await ops_test.model.applications[PG].remove_relation(
        f"{PGB}:{BACKEND_RELATION_NAME}", f"{PG}:database"
    )
    pgb_unit = ops_test.model.applications[PGB].units[0]
    logger.info(await get_app_relation_databag(ops_test, pgb_unit.name, relation.id))
    wait_for_relation_removed_between(ops_test, PG, PGB)

    async with ops_test.fast_forward():
        await asyncio.gather(
            ops_test.model.wait_for_idle(apps=[PGB], status="blocked", timeout=1000),
            ops_test.model.wait_for_idle(apps=[PG], status="active", timeout=1000),
        )

        # Wait for pgbouncer charm to update its config files.
        try:
            for attempt in Retrying(stop=stop_after_delay(3 * 60), wait=wait_fixed(3)):
                with attempt:
                    cfg = await get_cfg(ops_test, f"{PGB}/0")
                    if (
                        pgb_user not in cfg["pgbouncer"]["admin_users"]
                        and "auth_query" not in cfg["pgbouncer"].keys()
                    ):
                        break
        except RetryError:
            assert False, "pgbouncer config files failed to update in 3 minutes"

    cfg = await get_cfg(ops_test, f"{PGB}/0")
    logger.info(cfg.render())
