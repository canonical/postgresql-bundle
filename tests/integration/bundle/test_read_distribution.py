# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
import logging

import pytest
from pytest_operator.plugin import OpsTest

from tests.integration.helpers.helpers import (
    deploy_postgres_bundle,
)
from tests.integration.helpers.postgresql_helpers import check_database_users_existence

logger = logging.getLogger(__name__)


@pytest.mark.bundle
async def deploy_bundle(ops_test: OpsTest):
    """Deploy bundle."""
    await deploy_postgres_bundle(ops_test)


@pytest.mark.bundle
async def test_read_distribution(ops_test: OpsTest):
    """Read distribution, check that read instance changed during reconnection to proxy."""
