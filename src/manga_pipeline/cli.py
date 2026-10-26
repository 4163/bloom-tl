"""Small CLI. Commands describe separate agent and human checkpoints."""
import argparse
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from .files import PROJECTS, project
from . import native, output, workflow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Copy originals from an ordered manifest.")
    init.add_argument("project"); init.add_argument("--manifest", required=True); init.add_argument("--pages", required=True); init.add_argument("--archive")
    commands.add_parser("status")
    serve = commands.add_parser("serve"); serve.add_argument("--port", type=int, default=8765)
    extract = commands.add_parser("extract-transcript"); extract.add_argument("project"); extract.add_argument("--native-json", required=True)
    audit = commands.add_parser("audit-transcript"); audit.add_argument("project"); audit.add_argument("--note", required=True)
    for verb in ("handoff", "accept-translation"):
        command = commands.add_parser(verb); command.add_argument("project"); command.add_argument("revision")
    for verb in ("output", "finalize"):
        command = commands.add_parser(verb); command.add_argument("project")
        if verb == "finalize":
            command.add_argument("--format", choices=["full", "zip"], default="full", dest="package")
    finished = commands.add_parser("confirm-finished"); finished.add_argument("project"); finished.add_argument("--note", required=True)
    choice = commands.add_parser("select-output"); choice.add_argument("project"); choice.add_argument("page")
    mode = choice.add_mutually_exclusive_group(required=True)
    mode.add_argument("--revision"); mode.add_argument("--latest", action="store_true")
    issue = commands.add_parser("issue"); issue.add_argument("project")
    issue.add_argument("--stage", choices=["transcript", "translation", "visual"], required=True)
    issue.add_argument("--record", required=True); issue.add_argument("--question", required=True)
    resolve = commands.add_parser("resolve"); resolve.add_argument("project"); resolve.add_argument("issue")
    resolve.add_argument("--decision", required=True)
    resolve.add_argument("--by", choices=["user", "agent"], default="user")
    resolve.add_argument("--revision", help="Completed revision containing the agent's page fix.")
    pages = commands.add_parser("import-pages"); pages.add_argument("project"); pages.add_argument("revision"); pages.add_argument("--from", dest="source", required=True)
    fork = commands.add_parser("fork"); fork.add_argument("project"); fork.add_argument("revision"); fork.add_argument("--from", dest="base", required=True)
    engine = commands.add_parser("engine"); engine.add_argument("stage", choices=["extract", "clean", "render"]); engine.add_argument("project")
    engine.add_argument("--python", required=True); engine.add_argument("--run", required=True); engine.add_argument("--revision"); engine.add_argument("--execute", action="store_true")
    engine.add_argument("--pages", nargs="+", help="Only these pages for cleanup or rendering.")
    editable = commands.add_parser("export-editable"); editable.add_argument("project"); editable.add_argument("revision"); editable.add_argument("page"); editable.add_argument("--layers", required=True)
    imported = commands.add_parser("import-edit"); imported.add_argument("project"); imported.add_argument("revision"); imported.add_argument("page"); imported.add_argument("--from", dest="source", required=True)
    discard = commands.add_parser("discard-revision"); discard.add_argument("project"); discard.add_argument("revision", nargs="?")
    args = parser.parse_args()
    try:
        result = dispatch(args)
        if result is not None:
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    except (ValueError, OSError, KeyError, IndexError, json.JSONDecodeError) as error:
        parser.exit(1, f"{error}\n")


def dispatch(args):
    name = getattr(args, "project", None)
    if args.command == "init":
        return workflow.initialize(name, args.manifest, args.pages, args.archive)
    if args.command == "serve":
        from .server import serve
        return serve(args.port)
    if args.command == "status":
        result = []
        for file in sorted(PROJECTS.glob("*/project.json")):
            folder, data = project(file.parent.name)
            result.append({"project": data["id"], "revision": data.get("current_revision"),
                           "pages": len(data["pages"]), "open_questions": len([item for item in workflow.issues(folder) if item["status"] == "open"])})
        return result
    if args.command == "extract-transcript":
        return native.extract_transcript(name, args.native_json)
    if args.command == "audit-transcript":
        return workflow.audit_transcript(name, args.note)
    if args.command == "handoff":
        return workflow.handoff(name, args.revision)
    if args.command == "accept-translation":
        return workflow.accept_translation(name, args.revision)
    if args.command == "output":
        return output.describe(name)
    if args.command == "select-output":
        return output.choose(name, args.page, args.revision)
    if args.command == "confirm-finished":
        return output.confirm_finished(name, args.note)
    if args.command == "finalize":
        return output.finalize(name, args.package)
    if args.command == "issue":
        return workflow.add_issue(name, args.stage, args.record, args.question)
    if args.command == "resolve":
        return workflow.resolve_issue(name, args.issue, args.decision, args.by, args.revision)
    if args.command == "import-pages":
        return workflow.import_pages(name, args.revision, args.source)
    if args.command == "engine":
        return native.run_engine(name, args.stage, args.python, args.run, args.revision, args.execute, args.pages)
    if args.command in {"export-editable", "import-edit"}:
        from .editing import export_editable, import_edit
        return export_editable(name, args.revision, args.page, args.layers) if args.command == "export-editable" else import_edit(name, args.revision, args.page, args.source)
    if args.command == "discard-revision":
        from .editing import discard_revision
        return discard_revision(name, args.revision)
    if args.command == "fork":
        return workflow.fork_revision(name, args.revision, args.base)
