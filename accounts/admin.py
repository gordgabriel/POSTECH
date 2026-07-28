from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import UserModel


@admin.register(UserModel)
class UserModelAdmin(UserAdmin):
    list_display = ['username', 'email', 'type', 'phone_number', 'is_staff', 'is_active']
    list_filter = UserAdmin.list_filter + ('type',)
    search_fields = ['username', 'email']
    fieldsets = UserAdmin.fieldsets + (
        ('Informações adicionais', {
            'fields': (
                'uuid',
                'name',
                'type',
                'phone_number',
            ),
        }),
    )
    readonly_fields = ['uuid', 'created_at', 'updated_at']
