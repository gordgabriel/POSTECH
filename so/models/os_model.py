from django.db import models
import uuid
from accounts.models.user_model import UserModel

status_choices = [
    ('Received', 'Received'),
    ('Diagnosing', 'Diagnosing'),
    ('Waiting for approval', 'Waiting for approval'),
    ('In execution', 'In execution'),
    ('Completed', 'Completed'),
    ('Delivered', 'Delivered'),
    ('Cancelled', 'Cancelled'),
]

class OSModel(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_approved = models.BooleanField(default=False)
    user = models.ForeignKey(UserModel, on_delete=models.CASCADE)
    responsible = models.ForeignKey(UserModel, on_delete=models.CASCADE, related_name='responsible')
    responsible_notes = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=255, choices=status_choices, default='Received')
    
    def __str__(self):
        return self.uuid