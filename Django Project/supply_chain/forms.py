from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from .models import User, Project, Package, Bid, ContractorTeam, TeamMember, Report


# User Forms
class ContractorRegistrationForm(UserCreationForm):
    """Form for contractor registration"""
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    phone = forms.CharField(max_length=20, required=True)
    company_name = forms.CharField(max_length=255, required=True)
    license_number = forms.CharField(max_length=255, required=True)
    experience_years = forms.IntegerField(min_value=0, required=True)
    business_license = forms.FileField(required=False)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'phone', 
                  'company_name', 'license_number', 'experience_years', 'business_license')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = 'contractor'
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone = self.cleaned_data['phone']
        user.company_name = self.cleaned_data['company_name']
        user.experience_years = self.cleaned_data['experience_years']
        if self.cleaned_data.get('business_license'):
            user.business_license = self.cleaned_data['business_license']
        if commit:
            user.save()
        return user


class ContractorProfileForm(forms.ModelForm):
    """Form for updating contractor profile"""
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone', 'company_name',
                  'address', 'experience_years', 'profile_picture', 'business_license')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'experience_years': forms.NumberInput(attrs={'class': 'form-control'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
            'business_license': forms.FileInput(attrs={'class': 'form-control'}),
        }


class ProjectForm(forms.ModelForm):
    """Form for creating/editing projects"""
    class Meta:
        model = Project
        fields = ('title', 'description', 'location', 'budget_range', 
                  'start_date', 'end_date', 'status')
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter project title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Describe the project...'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'City, state, or address'
            }),
            'budget_range': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., $50,000 - $100,000'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date >= end_date:
            raise forms.ValidationError("End date must be after start date.")
        
        return cleaned_data


class PackageForm(forms.ModelForm):
    """Form for creating/editing packages"""
    class Meta:
        model = Package
        fields = ('title', 'description', 'package_type', 'estimated_cost', 'deadline', 'status')
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Package title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Describe the work package...'
            }),
            'package_type': forms.Select(attrs={'class': 'form-control'}),
            'estimated_cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'deadline': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        deadline = cleaned_data.get('deadline')
        
        if deadline and deadline <= timezone.now():
            raise forms.ValidationError("Deadline must be in the future.")
        
        return cleaned_data


class BidForm(forms.ModelForm):
    """Form for submitting/editing bids"""
    class Meta:
        model = Bid
        fields = ('bid_amount', 'duration_days', 'proposal_text', 'proposal_document')
        widgets = {
            'bid_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'duration_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '30',
                'min': '1'
            }),
            'proposal_text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 8,
                'placeholder': 'Describe your approach and proposal...'
            }),
            'proposal_document': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        bid_amount = cleaned_data.get('bid_amount')
        
        if bid_amount and bid_amount < 0:
            raise forms.ValidationError("Bid amount cannot be negative.")
        
        return cleaned_data


class BidReviewForm(forms.ModelForm):
    """Form for reviewing bids (Council only)"""
    class Meta:
        model = Bid
        fields = ('status', 'review_notes')
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'review_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Add review notes...'
            }),
        }


class ContractorTeamForm(forms.ModelForm):
    """Form for creating contractor teams"""
    class Meta:
        model = ContractorTeam
        fields = ('name', 'project', 'notes', 'status')
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Team name (auto-filled)'
            }),
            'project': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Additional team notes...'
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        council = kwargs.pop('council', None)
        super().__init__(*args, **kwargs)
        
        # Filter projects to council's projects only
        if council:
            self.fields['project'].queryset = Project.objects.filter(council=council)
        
        self.fields['project'].label = "Select Project"
        self.fields['name'].help_text = "Team name will be auto-generated if left blank"


class TeamMemberForm(forms.ModelForm):
    """Form for adding team members"""
    contractor = forms.ModelChoiceField(
        queryset=User.objects.filter(user_type='contractor'),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = TeamMember
        fields = ('contractor', 'role')
        widgets = {
            'role': forms.Select(attrs={'class': 'form-control'}),
        }


class ReportForm(forms.ModelForm):
    """Form for creating reports"""
    class Meta:
        model = Report
        fields = ('title', 'report_type', 'content')
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Report title'
            }),
            'report_type': forms.Select(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 8,
                'placeholder': 'Report content...'
            }),
        }


# Advanced filter forms
class ProjectFilterForm(forms.Form):
    """Form for filtering projects"""
    search = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Search projects...'
    }))
    status = forms.ChoiceField(required=False, choices=[('', 'All Status')] + list(Project.STATUS_CHOICES),
                               widget=forms.Select(attrs={'class': 'form-control'}))
    location = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Location'
    }))
    sort_by = forms.ChoiceField(required=False, choices=[
        ('-created_at', 'Newest First'),
        ('created_at', 'Oldest First'),
        ('title', 'Title A-Z'),
        ('-title', 'Title Z-A'),
    ], widget=forms.Select(attrs={'class': 'form-control'}))


class PackageFilterForm(forms.Form):
    """Form for filtering packages"""
    search = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Search packages...'
    }))
    package_type = forms.ChoiceField(required=False, choices=[('', 'All Types')] + list(Package.PACKAGE_TYPE_CHOICES),
                                    widget=forms.Select(attrs={'class': 'form-control'}))
    status = forms.ChoiceField(required=False, choices=[('', 'All Status')] + list(Package.STATUS_CHOICES),
                              widget=forms.Select(attrs={'class': 'form-control'}))
    sort_by = forms.ChoiceField(required=False, choices=[
        ('deadline', 'Deadline (Soonest)'),
        ('-deadline', 'Deadline (Latest)'),
        ('estimated_cost', 'Cost (Low to High)'),
        ('-estimated_cost', 'Cost (High to Low)'),
    ], widget=forms.Select(attrs={'class': 'form-control'}))


class BidFilterForm(forms.Form):
    """Form for filtering bids"""
    status = forms.ChoiceField(required=False, choices=[('', 'All Status')] + list(Bid.STATUS_CHOICES),
                              widget=forms.Select(attrs={'class': 'form-control'}))
    sort_by = forms.ChoiceField(required=False, choices=[
        ('-submitted_at', 'Newest First'),
        ('submitted_at', 'Oldest First'),
        ('bid_amount', 'Amount (Low to High)'),
        ('-bid_amount', 'Amount (High to Low)'),
    ], widget=forms.Select(attrs={'class': 'form-control'}))
