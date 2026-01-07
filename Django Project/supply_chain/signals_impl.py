from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import Bid, Package, User, Project, ActivityLog, ContractorTeam, TeamMember
from model_utils import FieldTracker


@receiver(post_save, sender=Bid)
def track_bid_changes(sender, instance, created, **kwargs):
    """Track changes to bid records and auto-create teams"""
    if created:
        ActivityLog.objects.create(
            user=instance.contractor,
            action='bid_submitted',
            details=f"Submitted bid on {instance.package.title}: ${instance.bid_amount}"
        )
    else:
        # Check if status changed to accepted
        if instance.tracker.has_changed('status') and instance.status == 'accepted':
            ActivityLog.objects.create(
                user=instance.package.project.council,
                action='bid_awarded',
                details=f"Awarded package {instance.package.title} to {instance.contractor.get_display_name()}"
            )
            
            # Auto-create project team if it doesn't exist
            project = instance.package.project
            team, created = ContractorTeam.objects.get_or_create(
                project=project,
                defaults={
                    'name': f"{project.title} Team",
                    'assigned_by': project.council,
                    'status': 'forming'
                }
            )
            
            # Auto-add contractor to team if not already a member
            if not team.members.filter(contractor=instance.contractor).exists():
                TeamMember.objects.create(
                    team=team,
                    contractor=instance.contractor,
                    role='member'
                )
                ActivityLog.objects.create(
                    user=project.council,
                    action='team_member_added',
                    details=f"Added {instance.contractor.get_display_name()} to {project.title} team"
                )
            
            # Set lead contractor if this is the first awarded bid
            if not team.lead_contractor:
                team.lead_contractor = instance.contractor
                team.save()
                
        elif instance.tracker.has_changed('status') and instance.status == 'rejected':
            ActivityLog.objects.create(
                user=instance.package.project.council,
                action='bid_reviewed',
                details=f"Rejected bid from {instance.contractor.get_display_name()} on {instance.package.title}"
            )


@receiver(post_save, sender=Project)
def track_project_changes(sender, instance, created, **kwargs):
    """Track changes to project records"""
    if created:
        ActivityLog.objects.create(
            user=instance.council,
            action='project_created',
            details=f"Created project: {instance.title}"
        )
    else:
        # Check if project was published
        if instance.tracker.has_changed('status') and instance.status == 'published':
            ActivityLog.objects.create(
                user=instance.council,
                action='project_published',
                details=f"Published project: {instance.title}"
            )


@receiver(post_save, sender=Package)
def track_package_changes(sender, instance, created, **kwargs):
    """Track package creation"""
    if created:
        ActivityLog.objects.create(
            user=instance.project.council,
            action='project_updated',
            details=f"Created work package: {instance.title} in {instance.project.title}"
        )


@receiver(post_save, sender=User)
def track_user_creation(sender, instance, created, **kwargs):
    """Track new user registrations"""
    if created and instance.user_type == 'contractor':
        ActivityLog.objects.create(
            user=instance,
            action='profile_updated',
            details=f"New contractor registration: {instance.company_name or instance.username}"
        )
