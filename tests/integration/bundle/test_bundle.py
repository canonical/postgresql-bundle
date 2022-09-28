# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
import logging

import pytest
from pytest_operator.plugin import OpsTest
from tenacity import RetryError, Retrying, stop_after_delay, wait_fixed

from constants import BACKEND_RELATION_NAME, PG, PGB
from tests.integration.helpers.helpers import (
    deploy_postgres_bundle,
    get_app_relation_databag,
    get_backend_relation,
    get_backend_user_pass,
    get_cfg,
    wait_for_relation_removed_between,
)
from tests.integration.helpers.postgresql_helpers import check_database_users_existence

logger = logging.getLogger(__name__)


@pytest.mark.bundle
async def test_relate_pgbouncer_to_postgres(ops_test: OpsTest):
    """Test that the pgbouncer and postgres charms can relate to one another."""
    # Build, deploy, and relate charms.
    await deploy_postgres_bundle(ops_test)
    relation = get_backend_relation(ops_test)