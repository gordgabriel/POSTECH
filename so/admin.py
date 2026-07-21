from django.contrib import admin

from so.models import OSModel


@admin.register(OSModel)
class OSModelAdmin(admin.ModelAdmin):
    list_display = ['uuid', 'status', 'user', 'responsible', 'is_approved', 'created_at']
    list_filter = ['status', 'is_active', 'is_approved']
    search_fields = ['uuid', 'user__username', 'responsible__username']
    readonly_fields = ['uuid', 'created_at', 'updated_at']
