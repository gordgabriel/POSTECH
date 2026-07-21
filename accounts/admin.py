from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import UserModel, VehiclesModel


@admin.register(UserModel)
class UserModelAdmin(UserAdmin):
    list_display = ['username', 'email', 'phone_number', 'is_staff', 'is_active']
    search_fields = ['username', 'email']
    fieldsets = UserAdmin.fieldsets + (
        ('Informações adicionais', {
            'fields': (
                'uuid',
                'phone_number',
                'birth_date',
                'gender',
                'address',
            ),
        }),
    )
    readonly_fields = ['uuid', 'created_at', 'updated_at']


@admin.register(VehiclesModel)
class VehiclesModelAdmin(admin.ModelAdmin):
    list_display = ['plate', 'brand', 'model', 'year', 'user']
    search_fields = ['plate', 'brand', 'model', 'user__username']
    readonly_fields = ['uuid', 'created_at', 'updated_at']
