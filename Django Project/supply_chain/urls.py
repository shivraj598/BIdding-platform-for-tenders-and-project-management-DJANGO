from django.urls import path
from django.contrib.auth.views import LogoutView, PasswordChangeView, PasswordChangeDoneView
from . import views

urlpatterns = [
    # Home
    path('', views.home_view, name='home'),
    
    # Authentication
    path('login/', views.ContractorLoginView.as_view(), name='login'),
    path('logout/', views.ContractorLogoutView.as_view(), name='logout'),
    path('register/', views.ContractorRegistrationView.as_view(), name='contractor_register'),
    
    # Password Management
    path('password-change/', views.PasswordChangeView.as_view(), name='password_change'),
    
    # Dashboards
    path('contractor/dashboard/', views.ContractorDashboardView.as_view(), name='contractor_dashboard'),
    path('council/dashboard/', views.CouncilDashboardView.as_view(), name='council_dashboard'),
    
    # Projects - List and Detail
    path('projects/', views.ProjectListView.as_view(), name='project_list'),
    path('projects/<uuid:pk>/', views.ProjectDetailView.as_view(), name='project_detail'),
    path('projects/create/', views.ProjectCreateView.as_view(), name='project_create'),
    path('projects/<uuid:pk>/update/', views.ProjectUpdateView.as_view(), name='project_update'),
    path('projects/<uuid:pk>/delete/', views.ProjectDeleteView.as_view(), name='project_delete'),
    
    # Projects - Available (for contractors)
    path('available-projects/', views.AvailableProjectsView.as_view(), name='available_projects'),
    
    # Packages
    path('packages/<uuid:pk>/', views.PackageDetailView.as_view(), name='package_detail'),
    path('projects/<uuid:project_id>/packages/create/', views.PackageCreateView.as_view(), name='package_create'),
    path('packages/<uuid:pk>/update/', views.PackageUpdateView.as_view(), name='package_update'),
    path('packages/<uuid:pk>/delete/', views.PackageDeleteView.as_view(), name='package_delete'),
    
    # Bids
    path('bids/', views.MyBidsView.as_view(), name='my_bids'),
    path('packages/<uuid:package_id>/bid/', views.BidCreateView.as_view(), name='bid_create'),
    path('bids/<uuid:pk>/', views.BidDetailView.as_view(), name='bid_detail'),
    path('bids/<uuid:pk>/edit/', views.BidUpdateView.as_view(), name='bid_update'),
    path('bids/<uuid:pk>/withdraw/', views.BidWithdrawView.as_view(), name='bid_withdraw'),
    path('bids/<uuid:pk>/delete/', views.BidDeleteView.as_view(), name='bid_delete'),
    path('awarded-projects/', views.AwardedProjectsView.as_view(), name='awarded_projects'),
    
    # Bid Review (Council)
    path('bids/review/', views.BidReviewListView.as_view(), name='bid_review_list'),
    path('bids/<uuid:pk>/review/', views.BidReviewDetailView.as_view(), name='bid_review_detail'),
    path('bids/<uuid:pk>/accept/', views.BidAcceptView.as_view(), name='bid_accept'),
    path('bids/<uuid:pk>/reject/', views.BidRejectView.as_view(), name='bid_reject'),
    
    # Teams
    path('teams/', views.TeamListView.as_view(), name='team_list'),
    path('teams/create/', views.TeamCreateView.as_view(), name='team_create'),
    path('teams/<uuid:pk>/', views.TeamDetailView.as_view(), name='team_detail'),
    path('teams/<uuid:pk>/edit/', views.TeamUpdateView.as_view(), name='team_update'),
    path('teams/<uuid:team_id>/add-member/', views.TeamMemberAddView.as_view(), name='team_add_member'),
    path('team-members/<int:pk>/remove/', views.TeamMemberRemoveView.as_view(), name='team_remove_member'),
    path('my-teams/', views.MyTeamsView.as_view(), name='my_teams'),
    
    # Profile
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/update/', views.ProfileUpdateView.as_view(), name='profile_update'),
    
    # Analytics and Reports
    path('analytics/bids/', views.BidAnalyticsView.as_view(), name='bid_analytics'),
    path('reports/', views.ReportListView.as_view(), name='report_list'),
    path('reports/create/', views.ReportCreateView.as_view(), name='report_create'),
    path('reports/auto-generate/', views.AutoGenerateReportView.as_view(), name='auto_generate_report'),

    path('reports/<uuid:pk>/pdf/', views.ReportPDFDownloadView.as_view(), name='report_pdf'),
    path('reports/<uuid:pk>/update/', views.ReportUpdateView.as_view(), name='report_update'),
    path('reports/<uuid:pk>/delete/', views.ReportDeleteView.as_view(), name='report_delete'),
    
    # Export
    path('export/bids/csv/', views.ExportBidsCSVView.as_view(), name='export_bids_csv'),
    path('export/projects/csv/', views.ExportProjectsCSVView.as_view(), name='export_projects_csv'),
]
