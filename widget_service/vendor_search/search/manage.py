"""CLI for Search database initialization, card import, and signature rebuild."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .cards_import import import_cards
from .repository import SQLiteDescriptionDAO, SQLiteTemplateDAO


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the Search template database")
    parser.add_argument("--db", default="search/data/templates.sqlite3")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init")
    import_parser = subparsers.add_parser("import-cards")
    import_parser.add_argument("--cards", default="cards")
    import_parser.add_argument("--description-db", required=True)
    import_parser.add_argument("--replace", action="store_true")
    subparsers.add_parser("rebuild-signatures")
    subparsers.add_parser("count")
    return parser


def main() -> None:
    args = _parser().parse_args()
    template_dao = SQLiteTemplateDAO(Path(args.db))
    template_dao.initialize()
    if args.command == "init":
        result: object = {"initialized": args.db}
    elif args.command == "import-cards":
        report = import_cards(
            args.cards,
            template_dao,
            SQLiteDescriptionDAO(args.description_db),
            replace=bool(args.replace),
        )
        result = {
            "imported": list(report.imported_template_ids),
            "rejected": [
                {
                    "template_id": item.template_id,
                    "reason": item.reason,
                    "pointer": item.pointer,
                }
                for item in report.rejected
            ],
        }
    elif args.command == "rebuild-signatures":
        rebuild = template_dao.rebuild_signatures()
        result = {
            "updated": list(rebuild.updated_template_ids),
            "rejected": [
                {"template_id": item[0], "reason": item[1], "pointer": item[2]}
                for item in rebuild.rejected
            ],
        }
    else:
        result = {"count": template_dao.count()}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
