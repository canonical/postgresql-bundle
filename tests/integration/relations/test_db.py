#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
import logging

from pytest_operator.plugin import OpsTest

from constants import PG

from ..helpers.helpers import (
    deploy_and_relate_application_with_pgbouncer,
    deploy_postgres_bundle,
    get_backend_relation,
    get_backend_user_pass,
)
from ..helpers.postgresql_helpers import check_databases_creation

logger = logging.getLogger(__name__)

WEEBL = "weebl"
APPLICATION_UNITS = 1


async def test_mailman3_core_db(ops_test: OpsTest) -> None:
    """Deploy Mailman3 Core to test the 'db' relation."""
    await deploy_postgres_bundle(ops_test)
    backend_relation = get_backend_relation(ops_test)

    async with ops_test.fast_forward():
        await ops_test.model.wait_for_idle(apps=[PG], status="active", timeout=1000)

        # Deploy and test the deployment of Mailman3 Core.
        await deploy_and_relate_application_with_pgbouncer(
            ops_test,
            WEEBL,
            WEEBL,
            series="jammy",
            force=True,
        )

    pgb_user, pgb_pass = await get_backend_user_pass(ops_test, backend_relation)
    await check_databases_creation(ops_test, ["bugs_database"], pgb_user, pgb_pass)
