from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.paths import root_path
from apps.core.safe_write import atomic_write
from apps.core.services import pipeline_summary, run_node_script
from apps.core.states import canonicalize_status


def parse_orphan(stderr: str) -> str | None:
    import re

    match = re.search(r"orphaned[:—-]+\s*(.+?)\s*$", stderr, re.IGNORECASE | re.MULTILINE)
    if not match:
        return None
    value = match.group(1).strip()
    while value.endswith(")") and value.count(")") > value.count("("):
        value = value[:-1].rstrip()
    return value


class PipelineView(APIView):
    def get(self, request):
        return Response(pipeline_summary())


class StatusView(APIView):
    def post(self, request):
        row_num = str(request.data.get("n") or "").strip()
        raw_status = str(request.data.get("status") or "").strip()
        if not row_num or not raw_status:
            return Response({"error": "n and status required"}, status=400)
        if any(c in raw_status for c in "|\r\n*"):
            return Response({"error": "invalid status (table-breaking characters)"}, status=400)
        canon = canonicalize_status(raw_status)
        if not canon:
            return Response({"error": f"not a canonical status: {raw_status}"}, status=400)
        tracker = root_path("data", "applications.md")
        try:
            lines = tracker.read_text(encoding="utf-8").split("\n")
        except FileNotFoundError:
            return Response({"error": "tracker not found"}, status=404)

        status_idx = 6
        for line in lines:
            if not line.strip().startswith("|"):
                continue
            cells = [c.strip().lower() for c in line.split("|")]
            if "status" in cells:
                status_idx = cells.index("status")
                break

        changed = False
        for i, line in enumerate(lines):
            if not line.strip().startswith("|"):
                continue
            parts = line.split("|")
            if len(parts) <= status_idx + 1 or parts[1].strip() != row_num:
                continue
            parts[status_idx] = f" {canon} "
            lines[i] = "|".join(parts)
            changed = True
            break
        if not changed:
            return Response({"error": "row not found"}, status=404)
        atomic_write(tracker, "\n".join(lines))
        return Response({"ok": True, "status": canon})


class TrackerDeleteView(APIView):
    def post(self, request):
        row_num = str(request.data.get("n") or request.data.get("num") or "").strip()
        if not row_num.isdigit():
            return Response({"error": "a numeric application number is required"}, status=400)
        dry_run = bool(request.data.get("dryRun"))
        args = ["delete", "--num", row_num]
        if dry_run:
            args.append("--dry-run")
        result = run_node_script("tracker", *args)
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "delete failed").strip().split("\n")[0]
            status_code = status.HTTP_404_NOT_FOUND if "No application numbered" in message else status.HTTP_400_BAD_REQUEST
            return Response({"error": message}, status=status_code)
        return Response({"ok": True, "dryRun": dry_run, "orphanReport": parse_orphan(result.stderr)})
