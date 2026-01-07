from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, FileExtensionValidator
from django.utils import timezone
from model_utils import FieldTracker
import uuid


# Council Model
class Council(models.Model):
    name = models.CharField(max_length=100)
    contact = models.CharField(max_length=100)
    contact_email = models.EmailField()
    slug = models.SlugField(max_length=100, unique=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Councils'
    
    def __str__(self):
        return f'{self.name} Council'


# Custom User Model
class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('council', 'Council'),
        ('contractor', 'Contractor'),
    )
    
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='contractor')
    
    # Company Information
    company_name = models.CharField(max_length=255, blank=True)
    address = models.TextField(blank=True)
    business_license = models.FileField(upload_to='business_licenses/', null=True, blank=True)
    experience_years = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    # Profile
    phone = models.CharField(max_length=20, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    
    # Verification
    is_verified = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Track field changes
    tracker = FieldTracker()
    
    class Meta:
        ordering = ['-date_joined']
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"
    
    def get_display_name(self):
        """Return display name - company name for contractors, full name for councils"""
        if self.user_type == 'contractor':
            return self.company_name or self.get_full_name() or self.username
        return self.get_full_name() or self.username


# Project Model
class Project(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    council = models.ForeignKey(User, on_delete=models.CASCADE, related_name='projects', limit_choices_to={'user_type': 'council'})
    
    # Basic Information
    title = models.CharField(max_length=255)
    description = models.TextField()
    location = models.CharField(max_length=255)
    budget_range = models.CharField(max_length=100, blank=True, help_text="e.g., $50,000 - $100,000")
    
    # Timeline
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    is_public = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Track field changes
    tracker = FieldTracker()
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Projects'
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['council', 'status']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
    
    @property
    def total_bid_value(self):
        """Calculate total bid amount if all packages are awarded"""
        bids = self.packages.filter(status='awarded').values_list('awarded_bid__bid_amount', flat=True)
        return sum(bids) if bids else 0


# Package Model (Work Package)
class Package(models.Model):
    PACKAGE_TYPE_CHOICES = (
        ('wiring', 'Electrical Wiring'),
        ('plumbing', 'Plumbing'),
        ('traffic', 'Traffic Management'),
        ('water', 'Water Works'),
        ('road', 'Road Construction'),
        ('sanitation', 'Sanitation'),
        ('landscaping', 'Landscaping'),
        ('structural', 'Structural Works'),
        ('other', 'Other'),
    )
    
    STATUS_CHOICES = (
        ('open', 'Open for Bidding'),
        ('in_progress', 'In Progress'),
        ('awarded', 'Awarded'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='packages')
    
    # Basic Information
    title = models.CharField(max_length=255)
    description = models.TextField()
    package_type = models.CharField(max_length=20, choices=PACKAGE_TYPE_CHOICES)
    
    # Financial
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Timeline
    deadline = models.DateTimeField()
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    
    # Awarded Information
    awarded_bid = models.OneToOneField('Bid', on_delete=models.SET_NULL, null=True, blank=True, related_name='awarded_package')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Track field changes
    tracker = FieldTracker()
    
    class Meta:
        ordering = ['deadline']
        verbose_name_plural = 'Packages'
        indexes = [
            models.Index(fields=['status', 'deadline']),
            models.Index(fields=['project', 'status']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_package_type_display()})"
    
    @property
    def is_deadline_passed(self):
        """Check if bidding deadline has passed"""
        return timezone.now() > self.deadline
    
    @property
    def bids_count(self):
        """Get count of bids for this package"""
        return self.bids.count()
    
    @property
    def active_bids_count(self):
        """Get count of active (not rejected) bids"""
        return self.bids.exclude(status='rejected').count()
    
    @property
    def duration_days(self):
        """Get duration in days from awarded bid"""
        if self.awarded_bid:
            return self.awarded_bid.duration_days
        return 0
    
    @property
    def team(self):
        """Get the team assigned to this package"""
        return self.teams.filter(status__in=['forming', 'active']).first()


# Bid Model
class Bid(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name='bids')
    contractor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bids', limit_choices_to={'user_type': 'contractor'})
    
    # Bid Details
    bid_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    duration_days = models.IntegerField(validators=[MinValueValidator(1)], help_text="Estimated completion time in days")
    
    # Proposal
    proposal_text = models.TextField()
    proposal_document = models.FileField(upload_to='bid_proposals/', null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Review Information
    review_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_bids')
    
    # Timestamps
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Track field changes
    tracker = FieldTracker()
    
    class Meta:
        ordering = ['-submitted_at']
        verbose_name_plural = 'Bids'
        unique_together = ('package', 'contractor')  # One bid per contractor per package
        indexes = [
            models.Index(fields=['status', '-submitted_at']),
            models.Index(fields=['contractor', 'status']),
            models.Index(fields=['package', 'status']),
        ]
    
    def __str__(self):
        return f"Bid by {self.contractor.get_display_name()} on {self.package.title}"
    
    def submit(self):
        """Submit a bid"""
        if self.status == 'draft':
            self.status = 'submitted'
            self.submitted_at = timezone.now()
            self.save()
    
    def withdraw(self):
        """Withdraw a submitted bid"""
        if self.status in ['draft', 'submitted', 'under_review']:
            self.status = 'withdrawn'
            self.save()
    
    def accept(self, reviewer):
        """Accept a bid and award the package"""
        self.status = 'accepted'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save()
        
        # Award the package to this bid
        self.package.awarded_bid = self
        self.package.status = 'awarded'
        self.package.save()
    
    def reject(self, reviewer, notes=''):
        """Reject a bid"""
        self.status = 'rejected'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        self.save()


# Contractor Team Model
class ContractorTeam(models.Model):
    STATUS_CHOICES = (
        ('forming', 'Forming'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('disbanded', 'Disbanded'),
    )
    
    ROLE_CHOICES = (
        ('lead', 'Lead Contractor'),
        ('member', 'Team Member'),
        ('specialist', 'Specialist'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Team Information
    name = models.CharField(max_length=255)
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='team')
    package = models.ForeignKey(Package, on_delete=models.SET_NULL, null=True, blank=True, related_name='teams')
    
    # Team Lead (Optional - auto-assigned from first awarded bid)
    lead_contractor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='led_teams')
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='forming')
    
    # Additional Information
    notes = models.TextField(blank=True)
    
    # Assignment Information
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_teams')
    assigned_date = models.DateTimeField(auto_now_add=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Track field changes
    tracker = FieldTracker()
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Contractor Teams'
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['project', 'status']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['project'], name='one_team_per_project'),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.project.title}"
    
    @property
    def awarded_contractors(self):
        """Get all contractors with awarded bids in this project"""
        from django.db.models import Q
        return User.objects.filter(
            bids__package__project=self.project,
            bids__status='accepted'
        ).distinct()


# Team Member Model (Through model for many-to-many relationship)
class TeamMember(models.Model):
    ROLE_CHOICES = (
        ('lead', 'Lead Contractor'),
        ('member', 'Team Member'),
        ('specialist', 'Specialist'),
    )
    
    team = models.ForeignKey(ContractorTeam, on_delete=models.CASCADE, related_name='members')
    contractor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='team_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    
    # Assignment Date
    assigned_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('team', 'contractor')
        verbose_name_plural = 'Team Members'
    
    def __str__(self):
        return f"{self.contractor.get_display_name()} - {self.get_role_display()}"


# Activity Log Model
class ActivityLog(models.Model):
    ACTION_CHOICES = (
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('project_created', 'Project Created'),
        ('project_updated', 'Project Updated'),
        ('project_published', 'Project Published'),
        ('package_created', 'Package Created'),
        ('bid_submitted', 'Bid Submitted'),
        ('bid_reviewed', 'Bid Reviewed'),
        ('bid_awarded', 'Bid Awarded'),
        ('bid_withdrawn', 'Bid Withdrawn'),
        ('team_created', 'Team Created'),
        ('profile_updated', 'Profile Updated'),
        ('document_uploaded', 'Document Uploaded'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_logs')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = 'Activity Logs'
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.get_action_display()}"


# Report Model (for analytics)
class Report(models.Model):
    REPORT_TYPE_CHOICES = (
        ('progress', 'Progress Report'),
        ('financial', 'Financial Report'),
        ('quality', 'Quality & Safety Report'),
        ('completion', 'Completion Report'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Report Details
    title = models.CharField(max_length=255)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    
    # Content
    content = models.TextField()
    
    # Associated Objects
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports')
    package = models.ForeignKey(Package, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports')
    bid = models.ForeignKey(Bid, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports')
    
    # Author
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_reports')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} ({self.get_report_type_display()})"

    def get_report_type_color(self):
        """Get color class for report type"""
        color_map = {
            'progress': 'emerald',
            'financial': 'blue',
            'quality': 'amber',
            'safety': 'red',
            'performance': 'purple',
        }
        return color_map.get(self.report_type, 'gray')

    def get_report_type_icon(self):
        """Get icon name for report type"""
        icon_map = {
            'progress': 'trending-up',
            'financial': 'dollar-sign',
            'quality': 'clipboard-check',
            'safety': 'shield',
            'performance': 'bar-chart-3',
        }
        return icon_map.get(self.report_type, 'file-text')
