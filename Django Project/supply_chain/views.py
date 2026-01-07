from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg, Min, Max
from django.urls import reverse_lazy
from django.utils import timezone
from django.http import JsonResponse, HttpResponseForbidden
from datetime import timedelta
import csv
from django.http import HttpResponse

from .models import (
    User, Project, Package, Bid, ContractorTeam, TeamMember, 
    ActivityLog, Report
)
from .forms import (
    ContractorRegistrationForm, ContractorProfileForm, ProjectForm,
    PackageForm, BidForm, BidReviewForm, ContractorTeamForm, TeamMemberForm,
    ReportForm, ProjectFilterForm
)
from .reports.utils import (
    collect_progress_data, collect_financial_data, 
    collect_quality_data, collect_completion_data,
    generate_pdf_report
)


# Mixins
class ContractorRequiredMixin(UserPassesTestMixin):
    """Mixin to restrict views to contractors only"""
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'contractor'
    
    def handle_no_permission(self):
        messages.error(self.request, "You must be a contractor to access this page.")
        return redirect('home')


class CouncilRequiredMixin(UserPassesTestMixin):
    """Mixin to restrict views to council users only"""
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'council'
    
    def handle_no_permission(self):
        messages.error(self.request, "You must be a council to access this page.")
        return redirect('home')


class OwnerOrCouncilMixin(UserPassesTestMixin):
    """Mixin to restrict to project owner or superuser"""
    def test_func(self):
        obj = self.get_object()
        return obj.council == self.request.user or self.request.user.is_superuser


# Authentication Views
class ContractorLoginView(LoginView):
    """Login view for contractors"""
    template_name = 'auth/login.html'
    redirect_authenticated_user = True
    
    def get_success_url(self):
        # Log activity
        ActivityLog.objects.create(
            user=self.request.user,
            action='login',
            ip_address=self.get_client_ip(self.request),
            user_agent=self.request.META.get('HTTP_USER_AGENT', '')
        )
        return reverse_lazy('contractor_dashboard') if self.request.user.user_type == 'contractor' else reverse_lazy('council_dashboard')
    
    @staticmethod
    def get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        return x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')


class ContractorLogoutView(LoginRequiredMixin, LogoutView):
    """Logout view"""
    next_page = 'home'
    http_method_names = ['get', 'post', 'options']
    
    def get(self, request, *args, **kwargs):
        # Log activity before logout
        ActivityLog.objects.create(
            user=request.user,
            action='logout'
        )
        # Redirect to home without showing logout template
        from django.contrib.auth import logout
        logout(request)
        return redirect(self.next_page)
    
    def post(self, request, *args, **kwargs):
        # Log activity before logout
        ActivityLog.objects.create(
            user=request.user,
            action='logout'
        )
        # Redirect to home without showing logout template
        from django.contrib.auth import logout
        logout(request)
        return redirect(self.next_page)


class ContractorRegistrationView(CreateView):
    """View for contractor registration"""
    form_class = ContractorRegistrationForm
    template_name = 'auth/register.html'
    success_url = reverse_lazy('login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Contractor Registration'
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Registration successful! Please log in.")
        return response


# Home and Dashboard Views
def home_view(request):
    """Home page view"""
    context = {
        'total_projects': Project.objects.filter(status='published').count(),
        'total_councils': User.objects.filter(user_type='council').count(),
        'total_contractors': User.objects.filter(user_type='contractor').count(),
        'total_bids': Bid.objects.filter(status='submitted').count(),
    }
    return render(request, 'home.html', context)


class ContractorDashboardView(ContractorRequiredMixin, View):
    """Contractor dashboard view"""
    template_name = 'dashboard/contractor_dashboard.html'
    
    def get(self, request):
        user = request.user
        
        # Get statistics
        total_bids = Bid.objects.filter(contractor=user).count()
        active_bids = Bid.objects.filter(
            contractor=user,
            status__in=['draft', 'submitted', 'under_review']
        ).count()
        awarded_bids = Bid.objects.filter(
            contractor=user,
            status='accepted'
        ).count()
        
        success_rate = 0
        if total_bids > 0:
            success_rate = round((awarded_bids / total_bids) * 100, 2)
        
        # Get recent bids
        recent_bids = Bid.objects.filter(contractor=user).order_by('-submitted_at')[:2]
        
        # Get available projects
        available_projects = Project.objects.filter(
            status='published'
        ).annotate(
            open_packages=Count('packages', filter=Q(packages__status='open'))
        ).filter(open_packages__gt=0)[:5]
        
        # Get awarded projects (packages where this contractor's bid was accepted)
        awarded_packages = Package.objects.filter(
            awarded_bid__contractor=user
        ).exclude(
            status='open'
        ).order_by('-created_at')[:10]
        
        context = {
            'stats': {
                'total_bids': total_bids,
                'active_bids': active_bids,
                'awarded_bids': awarded_bids,
                'success_rate': success_rate,
            },
            'recent_bids': recent_bids,
            'available_projects': available_projects,
            'awarded_packages': awarded_packages,
            'active_bids_count': active_bids,
        }
        
        return render(request, self.template_name, context)


class CouncilDashboardView(CouncilRequiredMixin, View):
    """Council dashboard view"""
    template_name = 'dashboard/council_dashboard.html'
    
    def get(self, request):
        user = request.user
        
        # Get statistics
        total_projects = Project.objects.filter(council=user).count()
        published_projects = Project.objects.filter(council=user, status='published').count()
        active_projects = Project.objects.filter(council=user, status='in_progress').count()
        total_packages = Package.objects.filter(project__council=user).count()
        open_packages = Package.objects.filter(project__council=user, status='open').count()
        total_bids = Bid.objects.filter(package__project__council=user).count()
        pending_bids_count = Bid.objects.filter(
            package__project__council=user,
            status__in=['submitted', 'under_review']
        ).count()
        accepted_bids = Bid.objects.filter(
            package__project__council=user,
            status='accepted'
        ).count()
        
        # Get recent projects
        recent_projects = Project.objects.filter(council=user).order_by('-created_at')[:2]
        
        # Get recent bids (all recent bids, not just pending)
        recent_bids = Bid.objects.filter(
            package__project__council=user
        ).order_by('-submitted_at')[:2]
        
        context = {
            'stats': {
                'total_projects': total_projects,
                'published_projects': published_projects,
                'active_projects': active_projects,
                'total_packages': total_packages,
                'open_packages': open_packages,
                'total_bids': total_bids,
                'pending_bids': pending_bids_count,
                'accepted_bids': accepted_bids,
            },
            'recent_projects': recent_projects,
            'recent_bids': recent_bids,
            'pending_bids_count': pending_bids_count,
        }
        
        return render(request, self.template_name, context)


# Project Views
class ProjectListView(ListView):
    """List all projects"""
    model = Project
    template_name = 'projects/project_list.html'
    context_object_name = 'projects'
    paginate_by = 12
    
    def get_queryset(self):
        user = self.request.user
        
        # Council sees their own projects
        if user.is_authenticated and user.user_type == 'council':
            queryset = Project.objects.filter(council=user)
        else:
            # Others see published projects
            queryset = Project.objects.filter(status='published')
        
        # Search filter
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(location__icontains=search)
            )
        
        # Status filter
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Sort
        sort = self.request.GET.get('sort_by', '-created_at')
        queryset = queryset.order_by(sort)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        queryset = self.get_queryset()
        context['total_projects'] = queryset.count()
        context['published_count'] = queryset.filter(status='published').count()
        context['in_progress_count'] = queryset.filter(status='in_progress').count()
        context['completed_count'] = queryset.filter(status='completed').count()
        
        return context


class ProjectDetailView(DetailView):
    """View project details"""
    model = Project
    template_name = 'projects/project_detail.html'
    context_object_name = 'project'
    pk_url_kwarg = 'pk'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['packages'] = self.object.packages.all()
        return context


class ProjectCreateView(CouncilRequiredMixin, CreateView):
    """Create a new project"""
    model = Project
    form_class = ProjectForm
    template_name = 'projects/project_create_form.html'
    success_url = reverse_lazy('project_list')
    
    def form_valid(self, form):
        form.instance.council = self.request.user
        messages.success(self.request, "Project created successfully!")
        
        # Log activity
        ActivityLog.objects.create(
            user=self.request.user,
            action='project_created',
            details=f"Created project: {form.instance.title}"
        )
        
        return super().form_valid(form)


class ProjectUpdateView(OwnerOrCouncilMixin, UpdateView):
    """Update a project"""
    model = Project
    form_class = ProjectForm
    template_name = 'projects/project_edit_form.html'
    success_url = reverse_lazy('project_list')
    
    def form_valid(self, form):
        messages.success(self.request, "Project updated successfully!")
        
        # Log activity
        ActivityLog.objects.create(
            user=self.request.user,
            action='project_updated',
            details=f"Updated project: {form.instance.title}"
        )
        
        return super().form_valid(form)


class ProjectDeleteView(OwnerOrCouncilMixin, DeleteView):
    """Delete a project"""
    model = Project
    template_name = 'packages/package_confirm_delete.html'
    success_url = reverse_lazy('project_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Project deleted successfully!")
        return super().delete(request, *args, **kwargs)


class PackageOwnerOrCouncilMixin(UserPassesTestMixin):
    """Mixin to restrict to package owner (council) or superuser"""
    def test_func(self):
        package = self.get_object()
        return package.project.council == self.request.user or self.request.user.is_superuser


class BidOwnerMixin(UserPassesTestMixin):
    """Mixin to restrict to bid owner or superuser"""
    def test_func(self):
        bid = self.get_object()
        return bid.contractor == self.request.user or self.request.user.is_superuser


class PackageUpdateView(PackageOwnerOrCouncilMixin, UpdateView):
    """Update a package"""
    model = Package
    form_class = PackageForm
    template_name = 'packages/package_form.html'

    def get_success_url(self):
        return reverse_lazy('project_detail', kwargs={'pk': self.object.project.id})

    def form_valid(self, form):
        messages.success(self.request, "Package updated successfully!")
        return super().form_valid(form)


class PackageDeleteView(PackageOwnerOrCouncilMixin, DeleteView):
    """Delete a package"""
    model = Package
    template_name = 'packages/package_confirm_delete.html'
    
    def get_success_url(self):
        return reverse_lazy('project_detail', kwargs={'pk': self.object.project.id})

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Package deleted successfully!")
        return super().delete(request, *args, **kwargs)


# Package Views
class PackageDetailView(DetailView):
    """View package details"""
    model = Package
    template_name = 'projects/package_detail.html'
    context_object_name = 'package'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['bids'] = self.object.bids.all()
        context['user_bid'] = self.object.bids.filter(
            contractor=self.request.user
        ).first() if self.request.user.is_authenticated else None
        return context


class PackageCreateView(CouncilRequiredMixin, CreateView):
    """Create a new package"""
    model = Package
    form_class = PackageForm
    template_name = 'projects/package_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Don't pass instance for create
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project_id = self.kwargs.get('project_id')
        context['project'] = get_object_or_404(Project, id=project_id, council=self.request.user)
        return context
    
    def form_valid(self, form):
        project_id = self.kwargs.get('project_id')
        project = get_object_or_404(Project, id=project_id, council=self.request.user)
        form.instance.project = project
        
        messages.success(self.request, "Package created successfully!")
        
        ActivityLog.objects.create(
            user=self.request.user,
            action='package_created',
            details=f"Created package: {form.instance.title}"
        )
        
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('project_detail', kwargs={'pk': self.object.project.id})


class AvailableProjectsView(ContractorRequiredMixin, ListView):
    """View available projects for bidding"""
    model = Project
    template_name = 'projects/available_projects.html'
    context_object_name = 'projects'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Project.objects.filter(status='published')
        
        # Location filter
        location = self.request.GET.get('location')
        if location:
            queryset = queryset.filter(location=location)
        
        # Package type filter
        package_type = self.request.GET.get('package_type')
        if package_type:
            queryset = queryset.filter(packages__package_type=package_type)
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search)
            )
        
        # Budget range
        min_budget = self.request.GET.get('min_budget')
        max_budget = self.request.GET.get('max_budget')
        
        if min_budget:
            queryset = queryset.filter(packages__estimated_cost__gte=min_budget)
        if max_budget:
            queryset = queryset.filter(packages__estimated_cost__lte=max_budget)
        
        # Sort
        sort = self.request.GET.get('sort', '-created_at')
        queryset = queryset.order_by(sort).distinct()
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get distinct locations
        context['locations'] = Project.objects.filter(
            status='published'
        ).values_list('location', flat=True).distinct()
        
        # Count statistics
        queryset = self.get_queryset()
        context['total_projects'] = queryset.count()
        context['open_packages_count'] = Package.objects.filter(
            project__status='published',
            status='open'
        ).count()
        
        # Count packages with deadline soon (within 7 days)
        context['deadline_soon_count'] = Package.objects.filter(
            project__status='published',
            status='open',
            deadline__lte=timezone.now() + timedelta(days=7),
            deadline__gte=timezone.now()
        ).count()
        
        context['selected_location'] = self.request.GET.get('location', '')
        context['selected_package_type'] = self.request.GET.get('package_type', '')
        context['selected_sort'] = self.request.GET.get('sort', '-created_at')
        context['search_query'] = self.request.GET.get('search', '')
        context['min_budget'] = self.request.GET.get('min_budget', '')
        context['max_budget'] = self.request.GET.get('max_budget', '')
        
        return context


# Bid Views
class BidCreateView(ContractorRequiredMixin, CreateView):
    """Submit a bid for a package"""
    model = Bid
    form_class = BidForm
    template_name = 'bids/bid_submit.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        return kwargs
    
    def form_valid(self, form):
        package_id = self.kwargs.get('package_id')
        package = get_object_or_404(Package, id=package_id)
        
        # Check if contractor already bid on this package
        existing_bid = Bid.objects.filter(
            package=package,
            contractor=self.request.user
        ).first()
        
        if existing_bid:
            messages.error(self.request, "You have already bid on this package.")
            return redirect('package_detail', pk=package_id)
        
        form.instance.package = package
        form.instance.contractor = self.request.user
        form.instance.status = 'submitted'
        form.instance.submitted_at = timezone.now()
        
        messages.success(self.request, "Bid submitted successfully!")
        
        ActivityLog.objects.create(
            user=self.request.user,
            action='bid_submitted',
            details=f"Submitted bid on package: {package.title}"
        )
        
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        package_id = self.kwargs.get('package_id')
        context['package'] = get_object_or_404(Package, id=package_id)
        return context
    
    def get_success_url(self):
        return reverse_lazy('package_detail', kwargs={'pk': self.object.package.id})


class BidDetailView(ContractorRequiredMixin, DetailView):
    """View bid details"""
    model = Bid
    template_name = 'bids/bid_detail.html'
    context_object_name = 'bid'
    
    def get_object(self):
        bid = super().get_object()
        # Check if user is the contractor who submitted this bid
        if bid.contractor != self.request.user:
            raise HttpResponseForbidden()
        return bid


class BidUpdateView(ContractorRequiredMixin, UpdateView):
    """Edit a submitted bid"""
    model = Bid
    form_class = BidForm
    template_name = 'bids/bid_edit.html'
    
    def get_object(self):
        bid = super().get_object()
        # Check if user is the contractor who submitted this bid
        if bid.contractor != self.request.user:
            raise HttpResponseForbidden()
        return bid
    
    def form_valid(self, form):
        messages.success(self.request, "Bid updated successfully!")
        
        ActivityLog.objects.create(
            user=self.request.user,
            action='bid_updated',
            details=f"Updated bid on package: {form.instance.package.title}"
        )
        
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['bid'] = self.get_object()
        return context
    
    def get_success_url(self):
        return reverse_lazy('my_bids')


class BidWithdrawView(BidOwnerMixin, DetailView):
    """Withdraw a bid"""
    model = Bid
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        bid = self.get_object()

        # Check if the bid can be withdrawn
        if bid.status not in ['draft', 'submitted', 'under_review']:
            messages.error(request, f"This bid cannot be withdrawn as it is already {bid.get_status_display()}.")
            return redirect('my_bids')

        bid.withdraw()
        ActivityLog.objects.create(
            user=request.user,
            action='bid_withdrawn',
            details=f"Withdrew bid on package: {bid.package.title}"
        )
        messages.success(request, "Your bid has been successfully withdrawn.")
        return redirect('my_bids')


class BidDeleteView(BidOwnerMixin, DeleteView):
    """Delete a bid"""
    model = Bid
    success_url = reverse_lazy('my_bids')

    def get_object(self, queryset=None):
        """Only allow deletion if bid is withdrawn"""
        obj = super().get_object()
        if obj.status != 'withdrawn':
            messages.error(self.request, "Only withdrawn bids can be deleted.")
            return None
        return obj

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object is None:
            return redirect('my_bids')
        
        messages.success(request, "Bid deleted successfully.")
        return super().delete(request, *args, **kwargs)


class MyBidsView(ContractorRequiredMixin, ListView):
    """View contractor's bids"""
    model = Bid
    template_name = 'bids/my_bids.html'
    context_object_name = 'bids'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Bid.objects.filter(contractor=self.request.user).order_by('-submitted_at')
        
        # Status filter
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_bids_count'] = Bid.objects.filter(
            contractor=self.request.user,
            status__in=['draft', 'submitted', 'under_review']
        ).count()
        return context


class BidReviewListView(CouncilRequiredMixin, ListView):
    """View bids for review (Council only)"""
    model = Bid
    template_name = 'bids/bid_review_list.html'
    context_object_name = 'bids'
    paginate_by = 20
    
    def get_queryset(self):
        # Get bids for packages owned by this council
        queryset = Bid.objects.filter(
            package__project__council=self.request.user
        ).order_by('-submitted_at')
        
        # Status filter
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset


class BidReviewDetailView(CouncilRequiredMixin, DetailView):
    """Review a specific bid (Council only)"""
    model = Bid
    template_name = 'bids/bid_review_detail.html'
    context_object_name = 'bid'
    
    def get_object(self):
        bid = super().get_object()
        # Check if user is authorized to review this bid
        if bid.package.project.council != self.request.user:
            raise HttpResponseForbidden()
        return bid
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        bid = self.get_object()
        
        # Get other bids for comparison
        other_bids = Bid.objects.filter(package=bid.package).exclude(id=bid.id)
        context['other_bids'] = other_bids
        
        # Calculate bid statistics
        all_bids = Bid.objects.filter(package=bid.package)
        if all_bids.exists():
            context['lowest_bid'] = all_bids.aggregate(min=Min('bid_amount'))['min']
            context['highest_bid'] = all_bids.aggregate(max=Max('bid_amount'))['max']
            context['average_bid'] = all_bids.aggregate(avg=Avg('bid_amount'))['avg']
        
        # Get contractor statistics
        contractor_bids = Bid.objects.filter(contractor=bid.contractor)
        context['contractor_stats'] = {
            'total_bids': contractor_bids.count(),
            'accepted_bids': contractor_bids.filter(status='accepted').count(),
            'pending_bids': contractor_bids.filter(status__in=['pending', 'under_review']).count(),
        }
        
        return context
    
    def post(self, request, *args, **kwargs):
        bid = self.get_object()
        action = request.POST.get('action')
        review_notes = request.POST.get('review_notes', '')
        
        if action == 'accept':
            bid.status = 'accepted'
            bid.reviewed_by = request.user
            bid.reviewed_at = timezone.now()
            bid.review_notes = review_notes
            bid.save()
            
            # Award the package to this contractor
            bid.package.status = 'awarded'
            bid.package.awarded_bid = bid
            bid.package.save()
            
            messages.success(request, "Bid accepted and package awarded!")
            
            ActivityLog.objects.create(
                user=request.user,
                action='bid_accepted',
                details=f"Accepted bid from {bid.contractor.get_display_name()} for {bid.package.title}"
            )
            
        elif action == 'reject':
            bid.status = 'rejected'
            bid.reviewed_by = request.user
            bid.reviewed_at = timezone.now()
            bid.review_notes = review_notes
            bid.save()
            
            messages.success(request, "Bid rejected!")
            
            ActivityLog.objects.create(
                user=request.user,
                action='bid_rejected',
                details=f"Rejected bid from {bid.contractor.get_display_name()} for {bid.package.title}"
            )
        
        elif action == 'save':
            bid.review_notes = review_notes
            bid.status = request.POST.get('status', bid.status)
            bid.reviewed_by = request.user
            bid.reviewed_at = timezone.now()
            bid.save()
            
            messages.success(request, "Bid evaluation saved!")
            
            ActivityLog.objects.create(
                user=request.user,
                action='bid_evaluated',
                details=f"Evaluated bid from {bid.contractor.get_display_name()}"
            )
        
        return redirect('bid_review_detail', pk=bid.id)


class BidAcceptView(CouncilRequiredMixin, View):
    """Accept a bid (Council only)"""
    
    def get(self, request, pk):
        bid = get_object_or_404(Bid, id=pk)
        
        # Check authorization
        if bid.package.project.council != request.user:
            raise HttpResponseForbidden()
        
        # Accept the bid
        bid.status = 'accepted'
        bid.reviewed_by = request.user
        bid.reviewed_at = timezone.now()
        bid.save()
        
        # Award the package
        bid.package.status = 'awarded'
        bid.package.awarded_bid = bid
        bid.package.save()
        
        messages.success(request, f"Bid from {bid.contractor.get_display_name()} accepted and package awarded!")
        
        ActivityLog.objects.create(
            user=request.user,
            action='bid_accepted',
            details=f"Accepted bid from {bid.contractor.get_display_name()} for {bid.package.title}"
        )
        
        return redirect('bid_review_detail', pk=bid.id)


class BidRejectView(CouncilRequiredMixin, View):
    """Reject a bid (Council only)"""
    
    def get(self, request, pk):
        bid = get_object_or_404(Bid, id=pk)
        
        # Check authorization
        if bid.package.project.council != request.user:
            raise HttpResponseForbidden()
        
        # Reject the bid
        bid.status = 'rejected'
        bid.reviewed_by = request.user
        bid.reviewed_at = timezone.now()
        bid.save()
        
        messages.success(request, f"Bid from {bid.contractor.get_display_name()} rejected!")
        
        ActivityLog.objects.create(
            user=request.user,
            action='bid_rejected',
            details=f"Rejected bid from {bid.contractor.get_display_name()} for {bid.package.title}"
        )
        
        return redirect('bid_review_detail', pk=bid.id)


# Team Views
class TeamListView(CouncilRequiredMixin, ListView):
    """List all teams across projects (Council only)"""
    model = ContractorTeam
    template_name = 'teams/team_list.html'
    context_object_name = 'teams'
    paginate_by = 12
    
    def get_queryset(self):
        # Show only teams from this council's projects
        queryset = ContractorTeam.objects.filter(
            project__council=self.request.user
        )
        
        # Status filter
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(project__title__icontains=search)
            )
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Council's teams stats
        council_teams = ContractorTeam.objects.filter(project__council=self.request.user)
        
        context['total_teams'] = council_teams.count()
        context['active_teams'] = council_teams.filter(status='active').count()
        context['forming_teams'] = council_teams.filter(status='forming').count()
        context['completed_teams'] = council_teams.filter(status='completed').count()
        
        # Statistics
        context['total_members'] = sum(
            team.members.count() for team in council_teams
        )
        
        context['selected_status'] = self.request.GET.get('status', '')
        context['search_query'] = self.request.GET.get('search', '')
        
        return context


class TeamDetailView(LoginRequiredMixin, DetailView):
    """View team details"""
    model = ContractorTeam
    template_name = 'teams/team_detail.html'
    context_object_name = 'team'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        team = self.object
        
        # Get team members with roles
        context['members'] = team.members.all()
        context['member_count'] = team.members.count()
        
        # Get all awarded contractors in the project
        context['awarded_contractors'] = team.awarded_contractors
        
        # Get all awarded packages in the project
        awarded_packages = Package.objects.filter(
            project=team.project,
            awarded_bid__isnull=False
        ).select_related('awarded_bid__contractor')
        context['awarded_packages'] = awarded_packages
        
        # Check if user is lead or member
        context['is_lead'] = team.lead_contractor == self.request.user
        context['is_member'] = team.members.filter(contractor=self.request.user).exists()
        
        # Project details
        context['project'] = team.project
        
        return context


class TeamCreateView(CouncilRequiredMixin, CreateView):
    """Create a new team (Council only) - auto-populated with awarded contractors"""
    model = ContractorTeam
    form_class = ContractorTeamForm
    template_name = 'teams/team_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['council'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        project = form.cleaned_data.get('project')
        
        # Auto-generate team name if not provided
        if not form.instance.name or form.instance.name.startswith(project.title):
            form.instance.name = f"{project.title} Team"
        
        form.instance.assigned_by = self.request.user
        
        messages.success(self.request, "Team created successfully!")
        ActivityLog.objects.create(
            user=self.request.user,
            action='team_created',
            details=f"Created team: {form.instance.name}"
        )
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('team_detail', kwargs={'pk': self.object.pk})


class TeamUpdateView(CouncilRequiredMixin, UpdateView):
    """Update team details (Council only)"""
    model = ContractorTeam
    form_class = ContractorTeamForm
    template_name = 'teams/team_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['council'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_update'] = True
        return context
    
    def form_valid(self, form):
        messages.success(self.request, "Team updated successfully!")
        ActivityLog.objects.create(
            user=self.request.user,
            action='team_updated',
            details=f"Updated team: {form.instance.name}"
        )
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('team_detail', kwargs={'pk': self.object.pk})


class TeamMemberAddView(CouncilRequiredMixin, CreateView):
    """Add a member to a team (Council only)"""
    model = TeamMember
    form_class = TeamMemberForm
    template_name = 'teams/add_team_member.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        team_id = self.kwargs.get('team_id')
        context['team'] = ContractorTeam.objects.get(id=team_id)
        return context
    
    def form_valid(self, form):
        team_id = self.kwargs.get('team_id')
        form.instance.team_id = team_id
        messages.success(self.request, "Team member added successfully!")
        ActivityLog.objects.create(
            user=self.request.user,
            action='team_member_added',
            details=f"Added {form.instance.contractor.get_display_name()} to team"
        )
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('team_detail', kwargs={'pk': self.kwargs.get('team_id')})


class TeamMemberRemoveView(CouncilRequiredMixin, DeleteView):
    """Remove a member from a team (Council only)"""
    model = TeamMember
    
    def delete(self, request, *args, **kwargs):
        member = self.get_object()
        team_id = member.team.id
        messages.success(request, f"Removed {member.contractor.get_display_name()} from team")
        ActivityLog.objects.create(
            user=request.user,
            action='team_member_removed',
            details=f"Removed {member.contractor.get_display_name()} from team"
        )
        return super().delete(request, *args, **kwargs)
    
    def get_success_url(self):
        return reverse_lazy('team_detail', kwargs={'pk': self.object.team.id})


# Profile Views
class ProfileView(LoginRequiredMixin, DetailView):
    """View and edit user profile"""
    model = User
    template_name = 'profiles/profile.html'
    context_object_name = 'profile'
    
    def get_object(self):
        return self.request.user
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.user.user_type == 'contractor':
            context['total_bids'] = Bid.objects.filter(contractor=self.request.user).count()
            context['awarded_bids'] = Bid.objects.filter(
                contractor=self.request.user,
                status='accepted'
            ).count()
            context['teams'] = ContractorTeam.objects.filter(lead_contractor=self.request.user)
        
        return context


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Update user profile"""
    model = User
    form_class = ContractorProfileForm
    template_name = 'profiles/profile_edit.html'
    success_url = reverse_lazy('profile')
    
    def get_object(self):
        return self.request.user
    
    def form_valid(self, form):
        messages.success(self.request, "Profile updated successfully!")
        ActivityLog.objects.create(
            user=self.request.user,
            action='profile_updated',
            details="Updated profile information"
        )
        return super().form_valid(form)


# Analytics and Reporting Views
class BidAnalyticsView(CouncilRequiredMixin, View):
    """View bid analytics"""
    template_name = 'analytics/bid_analytics.html'
    
    def get(self, request):
        user = request.user
        
        # Get bids for this council's projects
        bids = Bid.objects.filter(package__project__council=user)
        
        context = {
            'total_bids': bids.count(),
            'pending_bids': bids.filter(status__in=['draft', 'submitted']).count(),
            'under_review_bids': bids.filter(status='under_review').count(),
            'accepted_bids': bids.filter(status='accepted').count(),
            'rejected_bids': bids.filter(status='rejected').count(),
            'average_bid_amount': bids.aggregate(avg=Avg('bid_amount'))['avg'] or 0,
            'total_bid_value': bids.aggregate(total=Sum('bid_amount'))['total'] or 0,
        }
        
        return render(request, self.template_name, context)


class ReportListView(CouncilRequiredMixin, ListView):
    """List reports"""
    model = Report
    template_name = 'reports/report_list.html'
    context_object_name = 'reports'
    paginate_by = 20
    
    def get_queryset(self):
        # Only show reports created by this council user or for their projects
        return Report.objects.filter(
            Q(created_by=self.request.user) |
            Q(project__council=self.request.user)
        ).order_by('-created_at')


class ReportCreateView(CouncilRequiredMixin, CreateView):
    """Create a new report"""
    model = Report
    form_class = ReportForm
    template_name = 'reports/report_form.html'
    success_url = reverse_lazy('report_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Report created successfully!")
        return super().form_valid(form)





class ReportUpdateView(CouncilRequiredMixin, UpdateView):
    """Update a report"""
    model = Report
    form_class = ReportForm
    template_name = 'reports/report_form.html'
    success_url = reverse_lazy('report_list')

    def form_valid(self, form):
        messages.success(self.request, "Report updated successfully!")
        return super().form_valid(form)


class ReportDeleteView(CouncilRequiredMixin, DeleteView):
    """Delete a report"""
    model = Report
    template_name = 'reports/report_confirm_delete.html'
    success_url = reverse_lazy('report_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Report deleted successfully.")
        return super().delete(request, *args, **kwargs)


class AutoGenerateReportView(CouncilRequiredMixin, View):
    """Auto-generate comprehensive reports"""
    template_name = 'reports/auto_generate.html'
    
    def get(self, request):
        """Display the auto-generate report form"""
        projects = Project.objects.filter(council=request.user)
        report_types = [
            ('progress', 'Progress Report'),
            ('financial', 'Financial Report'),
            ('quality', 'Quality & Safety Report'),
            ('completion', 'Completion Report')
        ]
        
        context = {
            'projects': projects,
            'report_types': report_types
        }
        
        return render(request, self.template_name, context)
    
    def post(self, request):
        """Process the auto-generate report form"""
        project_id = request.POST.get('project')
        report_type = request.POST.get('report_type')
        
        if not project_id or not report_type:
            messages.error(request, "Please select both a project and report type.")
            return redirect('auto_generate_report')
        
        try:
            project = get_object_or_404(Project, id=project_id, council=request.user)
        except:
            messages.error(request, "Invalid project selected.")
            return redirect('auto_generate_report')
        
        # Collect data based on report type
        if report_type == 'progress':
            report_data = collect_progress_data(project)
            content_template = 'progress_report.html'
        elif report_type == 'financial':
            report_data = collect_financial_data(project)
            content_template = 'financial_report.html'
        elif report_type == 'quality':
            report_data = collect_quality_data(project)
            content_template = 'quality_report.html'
        elif report_type == 'completion':
            report_data = collect_completion_data(project)
            content_template = 'completion_report.html'
        else:
            messages.error(request, "Invalid report type selected.")
            return redirect('auto_generate_report')
        
        # Generate report title
        report_titles = {
            'progress': f'Progress Report - {project.title}',
            'financial': f'Financial Analysis - {project.title}',
            'quality': f'Quality & Safety Report - {project.title}',
            'completion': f'Completion Report - {project.title}'
        }
        
        # Create report record
        report = Report.objects.create(
            title=report_titles[report_type],
            report_type=report_type,
            project=project,
            created_by=request.user,
            content=f"Auto-generated {report_type} report for {project.title}"
        )
        
        messages.success(request, f"{report_titles[report_type]} generated successfully!")
        
        # Log activity
        ActivityLog.objects.create(
            user=request.user,
            action='report_auto_generated',
            details=f"Auto-generated {report_type} report for project: {project.title}"
        )
        
        return redirect('report_list')


class ReportPDFDownloadView(CouncilRequiredMixin, View):
    """Download report as PDF"""
    
    def get(self, request, pk):
        """Download report as PDF"""
        try:
            # Allow council users to download reports they created or reports for their projects
            report = get_object_or_404(
                Report, 
                id=pk
            )
            
            # Check if council user has access to this report
            if (report.created_by != request.user and 
                (not report.project or report.project.council != request.user)):
                messages.error(request, "Report not found or access denied.")
                return redirect('report_list')
                
        except:
            messages.error(request, "Report not found or access denied.")
            return redirect('report_list')
        
        # Generate PDF
        try:
            pdf_response = generate_pdf_report(report)
            
            # Log activity
            ActivityLog.objects.create(
                user=request.user,
                action='report_downloaded',
                details=f"Downloaded PDF report: {report.title}"
            )
            
            return pdf_response
            
        except Exception as e:
            messages.error(request, f"Error generating PDF: {str(e)}")
            return redirect('report_list')



       

class AwardedProjectsView(ContractorRequiredMixin, ListView):
    """View awarded projects"""
    model = Package
    template_name = 'bids/awarded_projects.html'
    context_object_name = 'packages'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Package.objects.filter(
            awarded_bid__contractor=self.request.user,
            status__in=['awarded', 'in_progress', 'completed']
        )
        
        # Filter by status if provided
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by search query if provided
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(project__title__icontains=search)
            )
        
        # Sort by requested field
        sort = self.request.GET.get('sort', '-awarded_bid__reviewed_at')
        if sort in ['deadline', '-deadline', 'estimated_cost', '-estimated_cost', '-awarded_bid__reviewed_at']:
            queryset = queryset.order_by(sort)
        else:
            queryset = queryset.order_by('-created_at')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all awarded packages for stats
        all_packages = Package.objects.filter(
            awarded_bid__contractor=self.request.user,
            status__in=['awarded', 'in_progress', 'completed']
        )
        
        # Calculate stats
        context['total_awards'] = all_packages.count()
        context['in_progress_awards'] = all_packages.filter(status='in_progress').count()
        context['completed_awards'] = all_packages.filter(status='completed').count()
        context['upcoming_awards'] = all_packages.filter(status='awarded').count()
        
        # Filter params for template
        context['selected_status'] = self.request.GET.get('status', '')
        context['selected_sort'] = self.request.GET.get('sort', '-awarded_bid__reviewed_at')
        context['search_query'] = self.request.GET.get('search', '')
        
        # Performance metrics
        context['total_contract_value'] = sum(
            pkg.awarded_bid.bid_amount for pkg in all_packages if pkg.awarded_bid
        )
        context['average_project_duration'] = (
            all_packages.aggregate(avg=Avg('awarded_bid__duration_days'))['avg'] or 0
        )
        
        # Completion rate
        completed = all_packages.filter(status='completed').count()
        total = all_packages.count()
        context['completion_rate'] = (completed / total * 100) if total > 0 else 0
        
        # Active projects
        context['active_projects'] = all_packages.filter(status='in_progress').count()
        
        # Upcoming packages with days remaining
        upcoming = all_packages.filter(status='in_progress').order_by('deadline')
        for pkg in upcoming:
            pkg.days_remaining = (pkg.deadline - timezone.now().date()).days if pkg.deadline else 0
        context['upcoming_packages'] = upcoming
        
        return context


class MyTeamsView(ContractorRequiredMixin, ListView):
    """View contractor's teams"""
    model = ContractorTeam
    template_name = 'teams/my_teams.html'
    context_object_name = 'teams'
    paginate_by = 12
    
    def get_queryset(self):
        # Get all teams where contractor is a member
        queryset = ContractorTeam.objects.filter(
            members__contractor=self.request.user
        ).distinct()
        
        # Status filter
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(project__title__icontains=search)
            )
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get contractor's team memberships
        all_teams = ContractorTeam.objects.filter(
            members__contractor=self.request.user
        ).distinct()
        
        context['total_teams'] = all_teams.count()
        context['active_teams'] = all_teams.filter(status='active').count()
        context['forming_teams'] = all_teams.filter(status='forming').count()
        context['completed_teams'] = all_teams.filter(status='completed').count()
        
        # Count teams as lead
        context['led_teams_count'] = all_teams.filter(lead_contractor=self.request.user).count()
        context['member_teams_count'] = all_teams.exclude(lead_contractor=self.request.user).count()
        
        # Get my awarded packages
        context['my_awarded_packages'] = Package.objects.filter(
            awarded_bid__contractor=self.request.user,
            awarded_bid__status='accepted'
        )
        
        context['selected_status'] = self.request.GET.get('status', '')
        context['search_query'] = self.request.GET.get('search', '')
        
        return context


# Password change view
class PasswordChangeView(LoginRequiredMixin, View):
    """Handle password changes"""
    template_name = 'auth/password_change.html'
    
    def get(self, request):
        return render(request, self.template_name)
    
    def post(self, request):
        old_password = request.POST.get('old_password')
        new_password1 = request.POST.get('new_password1')
        new_password2 = request.POST.get('new_password2')
        
        user = request.user
        
        if not user.check_password(old_password):
            messages.error(request, "Old password is incorrect.")
            return redirect('password_change')
        
        if new_password1 != new_password2:
            messages.error(request, "New passwords do not match.")
            return redirect('password_change')
        
        user.set_password(new_password1)
        user.save()
        
        messages.success(request, "Password changed successfully!")
        return redirect('profile')


# Export CSV views
class ExportBidsCSVView(CouncilRequiredMixin, View):
    """Export bids to CSV"""
    
    def get(self, request):
        # Get bids for this council's projects
        bids = Bid.objects.filter(package__project__council=request.user)
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="bids.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Package', 'Contractor', 'Amount', 'Duration (Days)', 'Status', 'Submitted At'])
        
        for bid in bids:
            writer.writerow([
                bid.package.title,
                bid.contractor.get_display_name(),
                bid.bid_amount,
                bid.duration_days,
                bid.get_status_display(),
                bid.submitted_at
            ])
        
        return response


class ExportProjectsCSVView(CouncilRequiredMixin, View):
    """Export projects to CSV"""
    
    def get(self, request):
        projects = Project.objects.filter(council=request.user)
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="projects.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Title', 'Location', 'Status', 'Packages', 'Start Date', 'End Date'])
        
        for project in projects:
            writer.writerow([
                project.title,
                project.location,
                project.get_status_display(),
                project.packages.count(),
                project.start_date,
                project.end_date
            ])
        
        return response
