"""Explicit offline lab operator. No HTTP, Keycloak admin credential or corporate identity."""
from __future__ import annotations

import argparse
import json
import sys

from app.trusted_identity_registry import OPERATIONS, RegistryError, TrustedIdentityRegistry, load_fixture


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise RegistryError("invalid_arguments")


def main(argv=None):
    try:
        parser = Parser(description="Offline workload-only trusted registry laboratory operator")
        parser.add_argument("operation", choices=("init", "list", *sorted(OPERATIONS)))
        parser.add_argument("--db", required=True, help="Explicit absolute path to a dedicated lab database")
        parser.add_argument("--fixture")
        parser.add_argument("--target", help="Registered principal id or binding id")
        parser.add_argument("--organization")
        parser.add_argument("--permission")
        parser.add_argument("--operator-label", help="Optional unverified lab label, not an authenticated administrator")
        args = parser.parse_args(argv)
        registry = TrustedIdentityRegistry(args.db)
        if args.operation == "init":
            if not args.fixture or any((args.target, args.organization, args.permission)):
                raise RegistryError("invalid_arguments")
            registry.initialize(load_fixture(args.fixture), args.operator_label)
            result = {"initialized": True, "revision": 1, "operator_verified": False}
        elif args.operation == "list":
            if any((args.fixture, args.target, args.organization, args.permission, args.operator_label)):
                raise RegistryError("invalid_arguments")
            result = registry.sanitized()
        else:
            if args.fixture or not args.target:
                raise RegistryError("invalid_arguments")
            result = registry.mutate(args.operation, args.target, args.organization, args.permission, args.operator_label)
        print(json.dumps(result, sort_keys=True))
        return 0
    except RegistryError as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1
    except Exception:
        print('{"error":"registry_operation_failed"}', file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
