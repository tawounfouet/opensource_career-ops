from django.db import models


class CvDocument(models.Model):
    path = models.CharField(max_length=500, default="cv.md")
    title = models.CharField(max_length=200, default="CV")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.title


class CvVersion(models.Model):
    document = models.ForeignKey(CvDocument, on_delete=models.CASCADE, related_name="versions")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
