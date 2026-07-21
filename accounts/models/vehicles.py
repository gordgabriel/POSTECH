from django.db import models
import uuid
from accounts.models.user_model import UserModel

class VehiclesModel(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    brand = models.CharField(max_length=255)
    model = models.CharField(max_length=255)
    year = models.IntegerField()
    plate = models.CharField(max_length=255)
    annotation = models.TextField(null=True, blank=True)
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)