from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.services import run_node_script

from .models import RunLog


SCRIPT_BY_KIND = {
    "scan": "scan",
    "scan-full": "scan-ats-full",
    "pipeline": "openrouter-runner",
    "pdf": "generate-pdf",
    "doctor": "doctor",
    "merge": "merge-tracker",
    "verify": "verify-pipeline",
}


class RunView(APIView):
    def post(self, request):
        kind = str(request.data.get("kind") or "doctor")
        args = request.data.get("args") or []
        if not isinstance(args, list):
            return Response({"error": "args must be a list"}, status=400)
        script = SCRIPT_BY_KIND.get(kind)
        if not script:
            return Response({"error": f"unsupported run kind: {kind}"}, status=400)
        run = RunLog.objects.create(kind=kind, status="running", input_text=str(request.data), cli_id=str(request.data.get("cli") or "node"))
        result = run_node_script(script, *[str(a) for a in args], timeout=600)
        run.status = "completed" if result.returncode == 0 else "failed"
        run.stdout = result.stdout
        run.stderr = result.stderr
        run.error_message = "" if result.returncode == 0 else (result.stderr or result.stdout)
        run.finished_at = timezone.now()
        run.save()
        return Response({"ok": result.returncode == 0, "runId": run.id, "stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode})


class AssistantView(APIView):
    def post(self, request):
        return Response({"error": "assistant orchestration is not implemented in Django yet; use the existing Next.js route for now."}, status=501)


class RunsSaveView(APIView):
    def post(self, request):
        run = RunLog.objects.create(
            kind=str(request.data.get("kind") or "manual"),
            status=str(request.data.get("status") or "completed"),
            input_text=str(request.data.get("input") or ""),
            cli_id=str(request.data.get("cli") or ""),
            stdout=str(request.data.get("stdout") or ""),
            stderr=str(request.data.get("stderr") or ""),
            finished_at=timezone.now(),
        )
        return Response({"ok": True, "runId": run.id})
