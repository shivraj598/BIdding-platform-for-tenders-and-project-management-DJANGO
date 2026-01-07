from datetime import timezone
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Project, Package, Bid, ContractorTeam, ActivityLog
from django.utils.html import format_html

# Custom User Admin
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'company_name', 'user_type', 'is_verified', 'is_staff', 'is_active')
    list_filter = ('user_type', 'is_verified', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'company_name', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email', 'phone', 'profile_picture')}),
        ('Company Info', {'fields': ('company_name', 'address', 'business_license', 'experience_years')}),
        ('Permissions', {'fields': ('user_type', 'is_verified', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined', 'created_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'user_type', 'is_staff', 'is_active'),
        }),
    )
    
    readonly_fields = ('date_joined', 'last_login', 'created_at')
    
    def get_queryset(self, request):
        # Show all users to superusers, limited view for others
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(is_superuser=False)

# Project Admin
class PackageInline(admin.TabularInline):
    model = Package
    extra = 1
    readonly_fields = ('created_at', 'updated_at')
    fields = ('title', 'package_type', 'estimated_cost', 'deadline', 'status', 'created_at')
    show_change_link = True

class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'council', 'location', 'budget_range', 'status', 'is_public', 'start_date', 'created_at')
    list_filter = ('status', 'is_public', 'start_date', 'council')
    search_fields = ('title', 'description', 'location', 'council__username', 'council__company_name')
    readonly_fields = ('created_at', 'updated_at', 'id')
    date_hierarchy = 'start_date'
    inlines = [PackageInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'location', 'council')
        }),
        ('Financial & Dates', {
            'fields': ('budget_range', 'start_date', 'end_date')
        }),
        ('Status', {
            'fields': ('status', 'is_public')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new project
            if not obj.council_id:
                obj.council = request.user
        super().save_model(request, obj, form, change)

# Package Admin
class BidInline(admin.TabularInline):
    model = Bid
    extra = 0
    readonly_fields = ('submitted_at', 'status')
    fields = ('contractor', 'amount', 'duration_days', 'status', 'submitted_at')
    show_change_link = True

class PackageAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'package_type', 'estimated_cost', 'deadline', 'status', 'created_at')
    list_filter = ('package_type', 'status', 'deadline', 'project__council')
    search_fields = ('title', 'description', 'project__title')
    readonly_fields = ('created_at', 'updated_at', 'id')
    inlines = [BidInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('project', 'title', 'description', 'package_type')
        }),
        ('Financial & Deadline', {
            'fields': ('estimated_cost', 'deadline')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.user_type == 'council' and not request.user.is_superuser:
            return qs.filter(project__council=request.user)
        return qs

# Bid Admin
class BidAdmin(admin.ModelAdmin):
    list_display = ('package', 'contractor', 'bid_amount', 'status', 'submitted_at', 'reviewed_at')
    list_filter = ('status', 'submitted_at', 'package__project__council')
    search_fields = ('proposal_text', 'contractor__username', 'contractor__company_name', 'package__title')
    readonly_fields = ('submitted_at', 'reviewed_at', 'id')
    
    fieldsets = (
        ('Bid Information', {
            'fields': ('package', 'contractor', 'bid_amount', 'duration_days', 'proposal_text', 'proposal_document')
        }),
        ('Review Information', {
            'fields': ('status', 'review_notes', 'reviewed_by')
        }),
        ('Metadata', {
            'fields': ('id', 'submitted_at', 'reviewed_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_under_review', 'mark_as_accepted', 'mark_as_rejected']
    
    def mark_as_under_review(self, request, queryset):
        queryset.update(status='under_review', reviewed_by=request.user)
        self.message_user(request, f"{queryset.count()} bids marked as under review.")
    mark_as_under_review.short_description = "Mark selected bids as Under Review"
    
    def mark_as_accepted(self, request, queryset):
        queryset.update(status='accepted', reviewed_by=request.user)
        self.message_user(request, f"{queryset.count()} bids accepted.")
    mark_as_accepted.short_description = "Accept selected bids"
    
    def mark_as_rejected(self, request, queryset):
        queryset.update(status='rejected', reviewed_by=request.user)
        self.message_user(request, f"{queryset.count()} bids rejected.")
    mark_as_rejected.short_description = "Reject selected bids"
    
    def save_model(self, request, obj, form, change):
        if 'status' in form.changed_data:
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)

# Contractor Team Admin
class ContractorTeamAdmin(admin.ModelAdmin):
    list_display = ('package', 'lead_contractor', 'assigned_by', 'assigned_date')
    list_filter = ('assigned_date', 'project__council')
    search_fields = ('package__title', 'lead_contractor__company_name', 'notes')
    
    fieldsets = (
        ('Team Assignment', {
            'fields': ('project', 'package', 'lead_contractor', 'assigned_by')
        }),
        ('Additional Information', {
            'fields': ('notes',)
        }),
        ('Metadata', {
            'fields': ('id', 'assigned_date'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new team
            obj.assigned_by = request.user
        super().save_model(request, obj, form, change)

# Activity Log Admin
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'timestamp', 'ip_address')
    list_filter = ('action', 'timestamp', 'user__user_type')
    search_fields = ('user__username', 'details', 'ip_address')
    readonly_fields = ('user', 'action', 'details', 'ip_address', 'user_agent', 'timestamp')
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

# Register all models
admin.site.register(User, CustomUserAdmin)
admin.site.register(Project, ProjectAdmin)
admin.site.register(Package, PackageAdmin)
admin.site.register(Bid, BidAdmin)
admin.site.register(ContractorTeam, ContractorTeamAdmin)
admin.site.register(ActivityLog, ActivityLogAdmin)

# Customize admin site
admin.site.site_header = "BidFlow Administration"
admin.site.site_title = "BidFlow Admin Portal"
admin.site.index_title = "Welcome to BidFlow Administration"