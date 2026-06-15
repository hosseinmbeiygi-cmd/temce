from __future__ import annotations


def register_commands(subparsers) -> None:
    run_parser = subparsers.add_parser("run", help="Run a job")
    run_parser.add_argument("job_name", type=str, help="Job name")
    run_parser.add_argument("--params", type=str, default="{}", help="JSON params")

    list_parser = subparsers.add_parser("list", help="List resources")
    list_parser.add_argument("resource", type=str, choices=["jobs", "models", "providers"], help="Resource type")

    serve_parser = subparsers.add_parser("serve", help="Start API server")
    serve_parser.add_argument("--port", type=int, default=8000, help="Server port")

    seed_parser = subparsers.add_parser("seed", help="Seed reference data")
    seed_parser.add_argument("--type", type=str, default="all", help="Data type to seed")
