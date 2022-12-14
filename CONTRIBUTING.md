# Contributing

## Overview

This documents explains the processes and practices recommended for contributing enhancements to
this bundle.

- Generally, before developing enhancements to this charm, you should consider [opening an issue
  ](https://github.com/canonical/postgresql-bundle/issues) explaining your use case.
- If you would like to chat with us about your use-cases or proposed implementation, you can reach
  us at [Canonical data-platform Mattermost public channel](https://chat.charmhub.io/charmhub/channels/data-platform)
  or [Discourse](https://discourse.charmhub.io/).
- Familiarising yourself with the [Charmed Operator Framework](https://juju.is/docs/sdk) library
  will help you a lot when working on new features or bug fixes.
- All enhancements require at least 2 approving reviews before being merged. Code review typically examines
  - code quality
  - test coverage
  - user experience for Juju administrators this charm.
- Please help us out in ensuring easy to review branches by rebasing your pull request branch onto
  the `main` branch. This also avoids merge commits and creates a linear Git commit history.

## Developing

You can use the environments created by `tox` for development:

```shell
tox --notest -e lint
source .tox/unit/bin/activate
```

### Testing

```shell
tox -e fmt           # update your code according to linting rules
tox -e lint          # code style
tox -e integration   # integration tests
tox                  # runs 'lint' environment
```

For more test options, see tox.ini.

## Canonical Contributor Agreement

Canonical welcomes contributions to the Charmed PGBouncer Operator. Please check out our [contributor agreement](https://ubuntu.com/legal/contributors) if you're interested in contributing to the solution.
