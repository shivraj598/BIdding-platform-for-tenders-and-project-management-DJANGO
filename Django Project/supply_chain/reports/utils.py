"""
Report data collection utilities for Django Supply Chain Management System.

This module contains functions to collect and organize data for different types of reports.
"""

from django.utils import timezone
from django.db.models import Count, Sum, Avg, Min, Max, Q
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO
from ..models import Bid, Package, ContractorTeam


def collect_progress_data(project):
    """
    Collect all data needed for progress reports.
    
    Args:
        project: Project instance
        
    Returns:
        dict: Dictionary containing all progress report data
    """
    if not project:
        return {
            'project': None,
            'generated_date': timezone.now(),
            'error': 'No project provided',
            'total_packages': 0,
            'completed_packages': 0,
            'in_progress_packages': 0,
            'awarded_packages': 0,
            'open_packages': 0,
            'progress_percentage': 0,
            'total_bids': 0,
            'accepted_bids': 0,
            'bid_acceptance_rate': 0,
            'team_status': 'No project',
            'team_name': None,
            'team_members_count': 0,
            'lead_contractor': None,
            'packages': [],
            'recommendations': ['No project data available'],
            'total_bid_value': 0,
        }
    
    packages = project.packages.all()
    total_packages = packages.count()
    completed_packages = packages.filter(status='completed').count()
    in_progress_packages = packages.filter(status='in_progress').count()
    awarded_packages = packages.filter(status='awarded').count()

    # Calculate progress percentage
    progress_percentage = (completed_packages / total_packages * 100) if total_packages > 0 else 0

    # Bid statistics
    total_bids = Bid.objects.filter(package__project=project).count()
    accepted_bids = Bid.objects.filter(package__project=project, status='accepted').count()

    # Team information
    team = getattr(project, 'team', None)
    team_status = team.status if team else 'Not formed'

    # Package-wise data
    package_data = []
    for package in packages:
        bid_count = package.bids.count()
        accepted_bid = package.awarded_bid
        package_data.append({
            'title': package.title,
            'package_type': package.get_package_type_display(),
            'status': package.get_status_display(),
            'bid_count': bid_count,
            'awarded_amount': accepted_bid.bid_amount if accepted_bid else None,
            'contractor': accepted_bid.contractor.get_display_name() if accepted_bid else None,
            'is_completed': package.status == 'completed',
            'is_in_progress': package.status == 'in_progress',
            'is_awarded': package.status == 'awarded',
            'is_open': package.status == 'open',
        })

    # Open packages
    open_packages = packages.filter(status='open').count()

    # Generate recommendations based on progress
    recommendations = []
    if progress_percentage < 25:
        recommendations.append("Project is in early stages. Focus on completing initial planning and mobilization.")
    elif progress_percentage < 50:
        recommendations.append("Project is progressing steadily. Ensure quality control measures are in place.")
    elif progress_percentage < 75:
        recommendations.append("Project is in execution phase. Monitor timelines and resource allocation.")
    else:
        recommendations.append("Project is nearing completion. Prepare for handover and final inspections.")

    if open_packages > 0:
        recommendations.append("Complete bidding process for remaining packages to avoid delays.")

    return {
        'project': project,
        'generated_date': timezone.now(),
        'total_packages': total_packages,
        'completed_packages': completed_packages,
        'in_progress_packages': in_progress_packages,
        'awarded_packages': awarded_packages,
        'open_packages': open_packages,
        'progress_percentage': progress_percentage,
        'total_bids': total_bids,
        'accepted_bids': accepted_bids,
        'bid_acceptance_rate': (accepted_bids/total_bids*100) if total_bids > 0 else 0,
        'team_status': team_status,
        'team_name': team.name if team else None,
        'team_members_count': team.members.count() if team else 0,
        'lead_contractor': team.lead_contractor.get_display_name() if team and team.lead_contractor else None,
        'packages': package_data,
        'recommendations': recommendations,
        'total_bid_value': project.total_bid_value,
    }


def collect_financial_data(project):
    """
    Collect all data needed for financial reports.
    
    Args:
        project: Project instance
        
    Returns:
        dict: Dictionary containing all financial report data
    """
    if not project:
        return {
            'project': None,
            'generated_date': timezone.now(),
            'error': 'No project provided',
            'total_budget': 0,
            'total_spent': 0,
            'remaining_budget': 0,
            'budget_utilization_percentage': 0,
            'packages': [],
            'financial_summary': {
                'total_packages': 0,
                'awarded_packages': 0,
                'total_contract_value': 0,
                'total_paid': 0,
                'remaining_balance': 0,
                'over_budget_packages': 0,
                'under_budget_packages': 0,
            }
        }
    
    packages = project.packages.all()
    awarded_packages = packages.filter(status__in=['awarded', 'in_progress', 'completed'])

    # Calculate financial totals
    total_budget = sum(pkg.awarded_bid.bid_amount for pkg in awarded_packages if pkg.awarded_bid)
    total_estimated = sum(pkg.estimated_cost for pkg in packages if pkg.estimated_cost)

    # Calculate variances
    budget_variance = total_budget - total_estimated if total_estimated else 0
    variance_percentage = (budget_variance / total_estimated * 100) if total_estimated else 0

    # Package-wise financial data
    package_financials = []
    for package in awarded_packages:
        if package.awarded_bid:
            estimated = package.estimated_cost or 0
            awarded = package.awarded_bid.bid_amount
            variance = awarded - estimated
            var_pct = (variance / estimated * 100) if estimated else 0
            
            package_financials.append({
                'title': package.title,
                'package_type': package.get_package_type_display(),
                'status': package.get_status_display(),
                'estimated_cost': estimated,
                'awarded_amount': awarded,
                'variance': variance,
                'variance_percentage': var_pct,
                'contractor': package.awarded_bid.contractor.get_display_name(),
            })

    # Financial metrics
    budget_utilization = (total_budget/total_estimated*100) if total_estimated else 0
    avg_package_value = total_budget/awarded_packages.count() if awarded_packages.exists() else 0
    largest_contract = max((pkg.awarded_bid.bid_amount for pkg in awarded_packages if pkg.awarded_bid), default=0)
    smallest_contract = min((pkg.awarded_bid.bid_amount for pkg in awarded_packages if pkg.awarded_bid), default=0)

    # Contractor payment analysis
    contractor_totals = {}
    for package in awarded_packages:
        if package.awarded_bid:
            contractor = package.awarded_bid.contractor.get_display_name()
            amount = package.awarded_bid.bid_amount
            contractor_totals[contractor] = contractor_totals.get(contractor, 0) + float(amount)

    # Sort contractors by total amount
    contractor_analysis = []
    for contractor, total in sorted(contractor_totals.items(), key=lambda x: x[1], reverse=True):
        percentage = (total / float(total_budget) * 100) if total_budget else 0
        contractor_analysis.append({
            'name': contractor,
            'total_amount': total,
            'percentage': percentage,
        })

    # Financial recommendations
    financial_recommendations = []
    if variance_percentage > 10:
        financial_recommendations.append("Budget exceeds estimates significantly. Review scope and requirements.")
    elif variance_percentage < -10:
        financial_recommendations.append("Project is under budget. Consider scope enhancements or quality improvements.")
    else:
        financial_recommendations.append("Budget is well-managed within acceptable variance ranges.")

    financial_recommendations.extend([
        "Monitor ongoing package costs to ensure continued budget compliance.",
        "Maintain detailed cost tracking for accurate financial reporting."
    ])

    return {
        'project': project,
        'generated_date': timezone.now(),
        'total_budget': total_budget,
        'total_estimated': total_estimated,
        'budget_variance': budget_variance,
        'variance_percentage': variance_percentage,
        'budget_utilization': budget_utilization,
        'avg_package_value': avg_package_value,
        'largest_contract': largest_contract,
        'smallest_contract': smallest_contract,
        'packages': package_financials,
        'contractor_analysis': contractor_analysis,
        'recommendations': financial_recommendations,
    }


def collect_quality_data(project):
    """
    Collect all data needed for quality & safety reports.
    
    Args:
        project: Project instance
        
    Returns:
        dict: Dictionary containing all quality report data
    """
    if not project:
        return {
            'project': None,
            'generated_date': timezone.now(),
            'error': 'No project provided',
            'quality_summary': {
                'total_packages': 0,
                'quality_checks_completed': 0,
                'safety_incidents': 0,
                'defects_reported': 0,
                'passed_packages': 0,
                'failed_packages': 0,
                'compliance_rate': 0,
                'average_quality_score': 0,
            },
            'packages': [],
            'recommendations': ['No project data available']
        }
    
    packages = project.packages.all()
    completed_packages = packages.filter(status='completed')
    active_packages = packages.filter(status__in=['awarded', 'in_progress'])

    # Package status data
    package_quality_data = []
    for package in packages:
        package_quality_data.append({
            'title': package.title,
            'status': package.get_status_display(),
            'package_type': package.get_package_type_display(),
            'contractor': package.awarded_bid.contractor.get_display_name() if package.awarded_bid else None,
            'is_completed': package.status == 'completed',
            'is_in_progress': package.status == 'in_progress',
            'status_icon': '✅' if package.status == 'completed' else '🔄' if package.status == 'in_progress' else '⏳',
        })

    # Contractor performance analysis
    contractors = {}
    for package in packages.filter(awarded_bid__isnull=False):
        contractor = package.awarded_bid.contractor
        name = contractor.get_display_name()
        if name not in contractors:
            contractors[name] = {
                'packages': 0,
                'completed': 0,
                'experience': contractor.experience_years
            }
        contractors[name]['packages'] += 1
        if package.status == 'completed':
            contractors[name]['completed'] += 1

    # Contractor analysis with performance metrics
    contractor_performance = []
    for name, data in contractors.items():
        completion_rate = (data['completed'] / data['packages'] * 100) if data['packages'] > 0 else 0
        contractor_performance.append({
            'name': name,
            'packages_assigned': data['packages'],
            'packages_completed': data['completed'],
            'completion_rate': completion_rate,
            'experience_years': data['experience'],
        })

    # Risk assessment
    risks = []
    if packages.filter(status='open').exists():
        risks.append("Delayed bidding process may impact project timeline")

    if not contractors:
        risks.append("No contractors assigned - project initiation at risk")
    elif len(contractors) < packages.filter(awarded_bid__isnull=False).count():
        risks.append("Some packages remain unassigned")

    low_experience = [name for name, data in contractors.items() if data['experience'] < 3]
    if low_experience:
        risks.append(f"Contractors with limited experience: {', '.join(low_experience)}")

    if not risks:
        risks.append("No significant risks identified at this time.")

    # Safety and compliance metrics
    avg_contractor_experience = (
        sum(c['experience'] for c in contractors.values()) / len(contractors) 
        if contractors else 0
    )

    # Quality recommendations
    quality_recommendations = [
        "Implement regular quality inspections for all active work packages",
        "Ensure all contractors have appropriate safety certifications",
        "Maintain detailed quality control documentation",
        "Conduct final quality audits before project completion",
        "Address identified risk factors promptly"
    ]

    # Next steps
    next_steps = [
        "Schedule quality control inspections for active packages",
        "Review contractor safety records and certifications",
        "Update risk register with current project status",
        "Prepare quality assurance checklist for remaining work"
    ]

    return {
        'project': project,
        'generated_date': timezone.now(),
        'project_status': project.get_status_display(),
        'active_packages_count': active_packages.count(),
        'completed_packages_count': completed_packages.count(),
        'packages': package_quality_data,
        'contractors': contractor_performance,
        'contractors_count': len(contractors),
        'active_work_sites': active_packages.count(),
        'avg_contractor_experience': avg_contractor_experience,
        'risks': risks,
        'recommendations': quality_recommendations,
        'next_steps': next_steps,
    }


def collect_completion_data(project):
    """
    Collect all data needed for completion reports.
    
    Args:
        project: Project instance
        
    Returns:
        dict: Dictionary containing all completion report data
    """
    if not project:
        return {
            'project': None,
            'generated_date': timezone.now(),
            'error': 'No project provided',
            'completion_percentage': 0,
            'project_duration': 0,
            'final_status': 'No project',
            'packages': [],
            'completion_summary': {
                'completed': 0,
                'in_progress': 0,
                'awarded': 0,
                'open': 0,
            },
            'total_project_value': 0,
            'contractor_summary': [],
            'team_data': {
                'name': None,
                'status': 'No project',
                'members_count': 0,
                'members': []
            },
            'achievements': ['No project data available'],
            'lessons_learned': {
                'success_factors': [],
                'areas_for_improvement': []
            },
            'future_recommendations': [],
            'final_status': {
                'project_status': 'NO PROJECT',
                'completion_date': 'N/A',
                'prepared_by': 'Automated System'
            }
        }
    
    packages = project.packages.all()
    completed_packages = packages.filter(status='completed')
    completion_percentage = (completed_packages.count() / packages.count() * 100) if packages.exists() else 0

    # Package completion status
    package_completion_data = []
    for package in packages:
        status_icon = "✅" if package.status == 'completed' else "🔄" if package.status == 'in_progress' else "⏳"
        awarded_info = {}
        if package.awarded_bid:
            awarded_info = {
                'awarded_to': package.awarded_bid.contractor.get_display_name(),
                'contract_value': package.awarded_bid.bid_amount,
                'duration': package.awarded_bid.duration_days
            }
        
        package_completion_data.append({
            'title': package.title,
            'type': package.get_package_type_display(),
            'status': package.get_status_display(),
            'status_icon': status_icon,
            'awarded_info': awarded_info,
            'is_completed': package.status == 'completed',
            'is_in_progress': package.status == 'in_progress',
            'is_awarded': package.status == 'awarded',
            'is_open': package.status == 'open',
        })

    # Completion summary
    completion_summary = {
        'completed': completed_packages.count(),
        'in_progress': packages.filter(status='in_progress').count(),
        'awarded': packages.filter(status='awarded').count(),
        'open': packages.filter(status='open').count(),
    }

    # Financial summary
    contractor_payments = {}
    for package in packages.filter(awarded_bid__isnull=False):
        contractor = package.awarded_bid.contractor.get_display_name()
        amount = package.awarded_bid.bid_amount
        contractor_payments[contractor] = contractor_payments.get(contractor, 0) + float(amount)

    contractor_summary = []
    for contractor, amount in sorted(contractor_payments.items(), key=lambda x: x[1], reverse=True):
        contractor_summary.append({
            'name': contractor,
            'amount': amount,
        })

    # Team performance
    team = getattr(project, 'team', None)
    team_data = None
    if team:
        team_data = {
            'name': team.name,
            'status': team.get_status_display(),
            'members_count': team.members.count(),
            'members': [
                {
                    'name': member.contractor.get_display_name(),
                    'role': member.get_role_display()
                }
                for member in team.members.all()
            ]
        }
    else:
        team_data = {
            'name': None,
            'status': 'No formal team structure was established for this project.',
            'members_count': 0,
            'members': []
        }

    # Project outcomes
    achievements = []
    if completion_percentage == 100:
        achievements.append("✅ Project completed on time and within scope")
    elif completion_percentage >= 80:
        achievements.append("✅ Project substantially completed")
    else:
        achievements.append("⚠️ Project completion in progress")

    if project.total_bid_value > 0:
        achievements.append(f"✅ Total contract value of ${project.total_bid_value:,.2f} secured")

    if team and team.members.exists():
        achievements.append(f"✅ Team of {team.members.count()} members successfully coordinated")

    if not achievements:
        achievements.append("Project milestones being tracked and monitored")

    # Lessons learned
    lessons_learned = {
        'success_factors': [
            f"{'Effective project planning contributed to successful execution' if completion_percentage > 80 else 'Additional planning may be beneficial for future projects'}",
            f"{len(contractor_payments)} qualified contractors engaged",
            f"{'Well-coordinated team effort' if team else 'Individual contractor management approach'}"
        ],
        'areas_for_improvement': [
            f"{'Project completed within planned timeline' if project.status == 'completed' else 'Timeline monitoring and adjustment may be needed'}",
            "Regular quality inspections maintained throughout project",
            "Stakeholder communication protocols established"
        ]
    }

    # Recommendations for future projects
    future_recommendations = [
        {
            'phase': 'Planning Phase',
            'items': [
                'Conduct thorough feasibility studies',
                'Develop detailed project schedules',
                'Establish clear quality standards'
            ]
        },
        {
            'phase': 'Execution Phase',
            'items': [
                'Implement regular progress monitoring',
                'Maintain open communication channels',
                'Ensure adequate resource allocation'
            ]
        },
        {
            'phase': 'Closure Phase',
            'items': [
                'Conduct comprehensive final inspections',
                'Document lessons learned',
                'Prepare handover documentation'
            ]
        }
    ]

    # Final status
    final_status = {
        'project_status': 'COMPLETED' if completion_percentage == 100 else 'IN PROGRESS',
        'completion_date': timezone.now().strftime('%B %d, %Y') if completion_percentage == 100 else 'Ongoing',
        'prepared_by': 'Automated System'
    }

    return {
        'project': project,
        'generated_date': timezone.now(),
        'completion_percentage': completion_percentage,
        'project_duration': (project.end_date - project.start_date).days,
        'final_status': project.get_status_display(),
        'packages': package_completion_data,
        'completion_summary': completion_summary,
        'total_project_value': project.total_bid_value,
        'contractor_summary': contractor_summary,
        'team_data': team_data,
        'achievements': achievements,
        'lessons_learned': lessons_learned,
        'future_recommendations': future_recommendations,
        'final_status': final_status,
    }


def generate_pdf_report(report):
    """
    Generate PDF report using reportlab with detailed data.

    Args:
        report: Report instance

    Returns:
        HttpResponse: PDF response
    """
    # Handle case where report.project might be None
    project_title = report.project.title if report.project else "No Project"
    project_name = report.project if report.project else None
    
    # Collect detailed data based on report type
    if report.report_type == 'progress':
        data = collect_progress_data(project_name)
    elif report.report_type == 'financial':
        data = collect_financial_data(project_name)
    elif report.report_type == 'quality':
        data = collect_quality_data(project_name)
    elif report.report_type == 'completion':
        data = collect_completion_data(project_name)
    else:
        # Fallback for custom reports
        data = {
            'project': project_name,
            'generated_date': timezone.now(),
        }

    # Create a BytesIO buffer to receive PDF data
    buffer = BytesIO()

    # Create PDF document
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()

    # Create custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        spaceBefore=20,
        textColor=colors.darkblue
    )

    subheading_style = ParagraphStyle(
        'CustomSubheading',
        parent=styles['Heading3'],
        fontSize=12,
        spaceAfter=8,
        spaceBefore=15,
        textColor=colors.darkgreen
    )

    # Build PDF content
    story = []

    # Title
    story.append(Paragraph(report.title, title_style))
    story.append(Spacer(1, 12))

    # Report metadata
    metadata_data = [
        ['Report Type:', report.get_report_type_display()],
        ['Created Date:', report.created_at.strftime('%B %d, %Y')],
        ['Author:', report.created_by.username],
        ['Project:', project_title],
        ['Generated On:', timezone.now().strftime('%B %d, %Y at %I:%M %p')],
    ]

    metadata_table = Table(metadata_data, colWidths=[2*inch, 4*inch])
    metadata_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (0, 0), (0, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    story.append(metadata_table)
    story.append(Spacer(1, 20))

    # Generate detailed content based on report type
    if report.report_type == 'progress':
        story.extend(_generate_progress_pdf_content(data, styles, subheading_style))
    elif report.report_type == 'financial':
        story.extend(_generate_financial_pdf_content(data, styles, subheading_style))
    elif report.report_type == 'quality':
        story.extend(_generate_quality_pdf_content(data, styles, subheading_style))
    elif report.report_type == 'completion':
        story.extend(_generate_completion_pdf_content(data, styles, subheading_style))
    else:
        # For custom reports, use the stored content
        story.append(Paragraph("Report Content", heading_style))
        story.append(Spacer(1, 12))
        content_lines = report.content.split('\n')
        for line in content_lines:
            if line.strip():
                story.append(Paragraph(line.strip(), styles['Normal']))
                story.append(Spacer(1, 6))

    # Add footer
    story.append(Spacer(1, 30))
    footer_text = "Generated by BidFlow Supply Chain Management System"
    story.append(Paragraph(footer_text, styles['Normal']))

    # Build PDF
    doc.build(story)

    # Get the PDF value from the buffer
    pdf = buffer.getvalue()
    buffer.close()

    # Create HTTP response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{report.title.replace(" ", "_")}.pdf"'
    response.write(pdf)

    return response


def _generate_progress_pdf_content(data, styles, subheading_style):
    """Generate PDF content for progress reports"""
    story = []

    story.append(Paragraph("Project Overview", subheading_style))
    overview_data = [
        ['Total Packages:', str(data.get('total_packages', 0))],
        ['Completed Packages:', str(data.get('completed_packages', 0))],
        ['In Progress Packages:', str(data.get('in_progress_packages', 0))],
        ['Progress Percentage:', f"{data.get('progress_percentage', 0):.1f}%"],
        ['Total Bids:', str(data.get('total_bids', 0))],
        ['Accepted Bids:', str(data.get('accepted_bids', 0))],
    ]

    overview_table = Table(overview_data, colWidths=[2.5*inch, 2.5*inch])
    overview_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(overview_table)
    story.append(Spacer(1, 15))

    # Package details
    if data.get('packages'):
        story.append(Paragraph("Package Details", subheading_style))
        package_headers = ['Package', 'Status', 'Bids', 'Contractor']
        package_data = [package_headers]

        for pkg in data['packages'][:10]:  # Limit to first 10 packages
            package_data.append([
                pkg['title'][:30] + '...' if len(pkg['title']) > 30 else pkg['title'],
                pkg['status'],
                str(pkg['bid_count']),
                pkg['contractor'][:25] + '...' if pkg.get('contractor') and len(pkg['contractor']) > 25 else (pkg.get('contractor') or 'N/A')
            ])

        if len(package_data) > 1:
            package_table = Table(package_data, colWidths=[2*inch, 1.5*inch, 1*inch, 2.5*inch])
            package_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ]))
            story.append(package_table)
            story.append(Spacer(1, 15))

    # Recommendations
    if data.get('recommendations'):
        story.append(Paragraph("Recommendations", subheading_style))
        for rec in data['recommendations']:
            story.append(Paragraph(f"• {rec}", styles['Normal']))
            story.append(Spacer(1, 4))

    return story


def _generate_financial_pdf_content(data, styles, subheading_style):
    """Generate PDF content for financial reports"""
    story = []

    story.append(Paragraph("Financial Summary", subheading_style))
    financial_data = [
        ['Total Budget:', f"${data.get('total_budget', 0):,.2f}"],
        ['Total Estimated:', f"${data.get('total_estimated', 0):,.2f}"],
        ['Budget Variance:', f"${data.get('budget_variance', 0):,.2f}"],
        ['Variance Percentage:', f"{data.get('variance_percentage', 0):.1f}%"],
        ['Budget Utilization:', f"{data.get('budget_utilization', 0):.1f}%"],
    ]

    financial_table = Table(financial_data, colWidths=[2.5*inch, 2.5*inch])
    financial_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgreen),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(financial_table)
    story.append(Spacer(1, 15))

    # Package financials
    if data.get('packages'):
        story.append(Paragraph("Package Financial Details", subheading_style))
        package_headers = ['Package', 'Estimated', 'Awarded', 'Variance']
        package_data = [package_headers]

        for pkg in data['packages'][:8]:  # Limit to first 8 packages
            package_data.append([
                pkg['title'][:25] + '...' if len(pkg['title']) > 25 else pkg['title'],
                f"${pkg['estimated_cost']:,.0f}" if pkg['estimated_cost'] else 'N/A',
                f"${pkg['awarded_amount']:,.0f}",
                f"${pkg['variance']:,.0f}"
            ])

        if len(package_data) > 1:
            package_table = Table(package_data, colWidths=[2*inch, 1.5*inch, 1.5*inch, 1.5*inch])
            package_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ]))
            story.append(package_table)
            story.append(Spacer(1, 15))

    # Contractor analysis
    if data.get('contractor_analysis'):
        story.append(Paragraph("Contractor Analysis", subheading_style))
        contractor_headers = ['Contractor', 'Total Amount', 'Percentage']
        contractor_data = [contractor_headers]

        for contractor in data['contractor_analysis'][:6]:  # Limit to first 6
            contractor_data.append([
                contractor['name'][:25] + '...' if len(contractor['name']) > 25 else contractor['name'],
                f"${contractor['total_amount']:,.0f}",
                f"{contractor['percentage']:.1f}%"
            ])

        if len(contractor_data) > 1:
            contractor_table = Table(contractor_data, colWidths=[2.5*inch, 1.5*inch, 1*inch])
            contractor_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ]))
            story.append(contractor_table)
            story.append(Spacer(1, 15))

    return story


def _generate_quality_pdf_content(data, styles, subheading_style):
    """Generate PDF content for quality reports"""
    story = []

    story.append(Paragraph("Project Status Overview", subheading_style))
    status_data = [
        ['Active Packages:', str(data.get('active_packages_count', 0))],
        ['Completed Packages:', str(data.get('completed_packages_count', 0))],
        ['Total Contractors:', str(data.get('contractors_count', 0))],
        ['Active Work Sites:', str(data.get('active_work_sites', 0))],
        ['Avg Contractor Experience:', f"{data.get('avg_contractor_experience', 0):.1f} years"],
    ]

    status_table = Table(status_data, colWidths=[2.5*inch, 2.5*inch])
    status_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightyellow),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(status_table)
    story.append(Spacer(1, 15))

    # Contractor performance
    if data.get('contractors'):
        story.append(Paragraph("Contractor Performance", subheading_style))
        contractor_headers = ['Contractor', 'Packages', 'Completed', 'Success Rate']
        contractor_data = [contractor_headers]

        for contractor in data['contractors'][:6]:  # Limit to first 6
            contractor_data.append([
                contractor['name'][:25] + '...' if len(contractor['name']) > 25 else contractor['name'],
                str(contractor['packages_assigned']),
                str(contractor['packages_completed']),
                f"{contractor['completion_rate']:.1f}%"
            ])

        if len(contractor_data) > 1:
            contractor_table = Table(contractor_data, colWidths=[2*inch, 1*inch, 1*inch, 1.5*inch])
            contractor_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkred),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ]))
            story.append(contractor_table)
            story.append(Spacer(1, 15))

    # Risks and Recommendations
    if data.get('risks'):
        story.append(Paragraph("Identified Risks", subheading_style))
        for risk in data['risks']:
            story.append(Paragraph(f"• {risk}", styles['Normal']))
            story.append(Spacer(1, 4))
        story.append(Spacer(1, 10))

    if data.get('recommendations'):
        story.append(Paragraph("Quality Recommendations", subheading_style))
        for rec in data['recommendations']:
            story.append(Paragraph(f"• {rec}", styles['Normal']))
            story.append(Spacer(1, 4))

    return story


def _generate_completion_pdf_content(data, styles, subheading_style):
    """Generate PDF content for completion reports"""
    story = []

    story.append(Paragraph("Completion Summary", subheading_style))
    completion_data = [
        ['Completion Percentage:', f"{data.get('completion_percentage', 0):.1f}%"],
        ['Project Duration:', f"{data.get('project_duration', 0)} days"],
        ['Total Project Value:', f"${data.get('total_project_value', 0):,.2f}"],
        ['Final Status:', data.get('final_status', 'Unknown')],
    ]

    completion_table = Table(completion_data, colWidths=[2.5*inch, 2.5*inch])
    completion_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightcyan),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(completion_table)
    story.append(Spacer(1, 15))

    # Package completion status
    if data.get('packages'):
        story.append(Paragraph("Package Completion Status", subheading_style))
        package_headers = ['Package', 'Type', 'Status', 'Contractor']
        package_data = [package_headers]

        for pkg in data['packages'][:8]:  # Limit to first 8 packages
            package_data.append([
                pkg['title'][:25] + '...' if len(pkg['title']) > 25 else pkg['title'],
                pkg['type'][:15] + '...' if len(pkg['type']) > 15 else pkg['type'],
                pkg['status'],
                pkg.get('awarded_info', {}).get('awarded_to', 'N/A')[:20] + '...' if pkg.get('awarded_info', {}).get('awarded_to') and len(pkg['awarded_info']['awarded_to']) > 20 else pkg.get('awarded_info', {}).get('awarded_to', 'N/A')
            ])

        if len(package_data) > 1:
            package_table = Table(package_data, colWidths=[2*inch, 1.2*inch, 1.2*inch, 2.1*inch])
            package_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkcyan),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ]))
            story.append(package_table)
            story.append(Spacer(1, 15))

    # Achievements
    if data.get('achievements'):
        story.append(Paragraph("Project Achievements", subheading_style))
        for achievement in data['achievements']:
            story.append(Paragraph(f"• {achievement}", styles['Normal']))
            story.append(Spacer(1, 4))
        story.append(Spacer(1, 10))

    # Lessons Learned
    if data.get('lessons_learned'):
        story.append(Paragraph("Lessons Learned", subheading_style))
        if data['lessons_learned'].get('success_factors'):
            story.append(Paragraph("Success Factors:", styles['Italic']))
            for factor in data['lessons_learned']['success_factors']:
                story.append(Paragraph(f"• {factor}", styles['Normal']))
                story.append(Spacer(1, 2))
            story.append(Spacer(1, 8))

        if data['lessons_learned'].get('areas_for_improvement'):
            story.append(Paragraph("Areas for Improvement:", styles['Italic']))
            for area in data['lessons_learned']['areas_for_improvement']:
                story.append(Paragraph(f"• {area}", styles['Normal']))
                story.append(Spacer(1, 2))

    return story
