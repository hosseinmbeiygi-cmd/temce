from __future__ import annotations

import argparse
import asyncio
import json

from apps.cli.commands import register_commands
from apps.cli.formatters import format_json, format_table
from core.logging import setup_logging


async def run_job(job_name: str, params: str = "{}") -> None:
    from jobs.job_dispatcher import job_dispatcher

    kwargs = json.loads(params)
    result = await job_dispatcher.dispatch(job_name, **kwargs)
    print(format_json(result))


def list_resource(resource: str) -> None:
    if resource == "jobs":
        from jobs.job_dispatcher import job_dispatcher

        jobs = job_dispatcher.list_jobs()
        print(format_table(["Job Name"], [[j] for j in jobs]))
    else:
        print(f"Listing {resource} - not implemented")


def serve(port: int) -> None:
    from main import main as serve_main

    serve_main()


def seed(data_type: str) -> None:
    from scripts.seed_reference_data import seed_all

    seed_all()
    print(f"Seeded {data_type} data")


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description="Iran Market Platform CLI")
    sub = parser.add_subparsers(dest="command", help="Available commands")
    register_commands(sub)

    args = parser.parse_args()
    if args.command == "run":
        asyncio.run(run_job(args.job_name, args.params))
    elif args.command == "list":
        list_resource(args.resource)
    elif args.command == "serve":
        serve(args.port)
    elif args.command == "seed":
        seed(args.type)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
