from django.contrib import admin
from .models import CustomUser, Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    """Tenant management — only super_admin (Part 5-TENANT)."""
    list_display = ['name', 'slug', 'is_active', 'plan', 'created_at']
    list_filter = ['is_active', 'plan']
    search_fields = ['name', 'slug', 'billing_email']
    prepopulated_fields = {'slug': ('name',)}

    def has_module_permission(self, request):
        return getattr(request.user, 'role', None) == 'super_admin'

    def has_view_permission(self, request, obj=None):
        return getattr(request.user, 'role', None) == 'super_admin'

    def has_add_permission(self, request):
        return getattr(request.user, 'role', None) == 'super_admin'

    def has_change_permission(self, request, obj=None):
        return getattr(request.user, 'role', None) == 'super_admin'

    def has_delete_permission(self, request, obj=None):
        return getattr(request.user, 'role', None) == 'super_admin'


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ['email', 'first_name', 'last_name', 'role', 'tenant', 'is_verified', 'is_active']
    list_filter = ['role', 'tenant', 'is_verified', 'is_active']
    search_fields = ['email', 'first_name', 'last_name']
    list_select_related = ['tenant']