# PostgreSQL Bundle

A juju bundle for deploying PostgreSQL and PGBouncer VM charms, with TLS.

Included charms:
- [postgresql-operator](https://github.com/canonical/postgresql-operator)
  - 2 replica units
  - related to pgbouncer-operator for connection pooling
  - related to tls-certificates-operator for TLS.
- [pgbouncer-operator](https://github.com/canonical/pgbouncer-operator)
  - Note: TLS not implemented in this proxy yet
- [tls-certificates-operator](https://github.com/canonical/tls-certificates-operator)
  - The TLS implementation is self-signed - if other certificates are required, please follow the [TLS Certificate Operator Documentation](https://charmhub.io/tls-certificates-operator) to upload your own.

## License

The Charmed PostgreSQL Bundle is free software, distributed under the Apache Software License, version 2.0. See [LICENSE](https://github.com/canonical/pgbouncer-operator/blob/main/LICENSE) for more information.

## Security

Security issues in this bundle can be reported through [LaunchPad](https://wiki.ubuntu.com/DebuggingSecurity#How%20to%20File). Please do not file GitHub issues about security issues.

## Contributing

Please see the [Juju SDK docs](https://juju.is/docs/sdk) for guidelines on enhancements to this charm following best practice guidelines, and [CONTRIBUTING.md](https://github.com/canonical/postgresql-bundle/CONTRIBUTING.md) for developer guidance. For more information, get in touch on the [Charmhub Mattermost server](https://chat.charmhub.io).
