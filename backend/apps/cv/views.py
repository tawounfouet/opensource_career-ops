import re

from django.http import FileResponse, HttpResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.paths import root_path
from apps.core.safe_write import atomic_write_with_backup


MAX_CV_BYTES = 200_000


class CvViewSet(APIView):
    def get(self, request):
        path = root_path("cv.md")
        try:
            return Response({"content": path.read_text(encoding="utf-8"), "exists": True})
        except FileNotFoundError:
            return Response({"content": "", "exists": False})

    def post(self, request):
        content = request.data.get("content")
        if not isinstance(content, str):
            return Response({"error": "content required"}, status=400)
        if len(content.encode("utf-8")) > MAX_CV_BYTES:
            return Response({"error": "CV is too large (over 200KB)"}, status=413)
        bak = atomic_write_with_backup(root_path("cv.md"), content)
        return Response({"ok": True, "backedUp": bool(bak)})


class CvPdfView(APIView):
    def get(self, request):
        company = str(request.query_params.get("company") or "").strip()
        if not company:
            return HttpResponse("company required", status=400, content_type="text/plain")
        slug = "-".join(re.findall(r"[a-z0-9]+", company.lower()))
        if not slug:
            return HttpResponse("company required", status=400, content_type="text/plain")
        output_dir = root_path("output")
        try:
            files = [
                child
                for child in output_dir.iterdir()
                if child.is_file()
                and child.name.lower().endswith(".pdf")
                and re.search(rf"(^|[^a-z0-9]){re.escape(slug)}([^a-z0-9]|$)", child.name.lower())
            ]
        except FileNotFoundError:
            return HttpResponse("no output directory", status=404, content_type="text/plain")
        if not files:
            return HttpResponse("no tailored CV found for this offer", status=404, content_type="text/plain")
        files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        try:
            response = FileResponse(files[0].open("rb"), content_type="application/pdf")
            response["Content-Disposition"] = f'inline; filename="{files[0].name}"'
            response["Cache-Control"] = "no-store"
            return response
        except OSError:
            return HttpResponse("could not read the PDF", status=500, content_type="text/plain")
