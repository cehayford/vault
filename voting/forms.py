import re
from django import forms
from django.forms import ModelForm
from django.utils.text import slugify
from .models import Election, Ballot, Candidate, Organisation
import datetime


INPUT_CLASS = 'w-full px-4 py-2.5 text-sm rounded-lg border border-border bg-secondary text-foreground placeholder-muted focus:border-accent focus:outline-none transition-colors duration-fast'


class ElectionForm(ModelForm):
    # Accept datetime-local browser value (YYYY-MM-DDTHH:MM) and common manual formats
    DATETIME_INPUT_FORMATS = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']

    class Meta:
        model = Election
        fields = ['title', 'description', 'start_date', 'end_date', 'voting_type', 'status', 'brand_name', 'primary_color']
        labels = {
            'brand_name': 'Brand name',
            'primary_color': 'Primary color',
        }
        help_texts = {
            'brand_name': 'Display name for this election; defaults to title if blank.',
            'primary_color': 'Hex color e.g. #B45309 for accents on election pages. Optional.',
        }
        widgets = {
            'title': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Election title', 'required': True}),
            'description': forms.Textarea(attrs={'class': INPUT_CLASS, 'placeholder': 'Describe the election purpose and scope', 'rows': 4, 'required': True}),
            'start_date': forms.DateTimeInput(attrs={'class': INPUT_CLASS, 'type': 'datetime-local', 'required': True}, format='%Y-%m-%dT%H:%M'),
            'end_date': forms.DateTimeInput(attrs={'class': INPUT_CLASS, 'type': 'datetime-local', 'required': True}, format='%Y-%m-%dT%H:%M'),
            'voting_type': forms.Select(attrs={'class': INPUT_CLASS, 'required': True}),
            'status': forms.Select(attrs={'class': INPUT_CLASS, 'required': True}),
            'brand_name': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'Leave blank to use election title',
                'maxlength': 120,
            }),
            'primary_color': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': '#B45309',
                'maxlength': 7,
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['start_date'].input_formats = self.DATETIME_INPUT_FORMATS
        self.fields['end_date'].input_formats = self.DATETIME_INPUT_FORMATS

    def clean_start_date(self):
        start_date = self.cleaned_data.get('start_date')
        end_date = self.cleaned_data.get('end_date')
        if start_date and end_date and start_date >= end_date:
            raise forms.ValidationError('End date must be after start date.')
        return start_date

    def clean_brand_name(self):
        value = self.cleaned_data.get('brand_name')
        if value is not None:
            value = value.strip() or None
        return value

    def clean_primary_color(self):
        value = (self.cleaned_data.get('primary_color') or '').strip()
        if not value:
            return None
        value = value.lower()
        if not value.startswith('#'):
            value = '#' + value
        if not re.match(r'^#[0-9a-f]{6}$', value):
            if re.match(r'^#[0-9a-f]{3}$', value):
                value = '#' + value[1] * 2 + value[2] * 2 + value[3] * 2
            else:
                raise forms.ValidationError('Enter a valid hex color (e.g. #B45309 or #f00).')
        return value


class BallotForm(ModelForm):
    class Meta:
        model = Ballot
        fields = ['title', 'description', 'max_selections', 'seats']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 focus:outline-none focus:ring-0 transition-all duration-200 bg-white border-4 border-amber-900 font-mono text-sm md:text-base uppercase tracking-wide focus:bg-amber-900 focus:text-white focus:placeholder-amber-200 placeholder-amber-900',
                'placeholder': 'Ballot Title',
                'required': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 focus:outline-none focus:ring-0 transition-all duration-200 bg-white border-4 border-amber-900 font-mono text-sm md:text-base uppercase tracking-wide focus:bg-amber-900 focus:text-white focus:placeholder-amber-200 placeholder-amber-900',
                'placeholder': 'Describe this ballot and voting options',
                'rows': 4,
                'required': True
            }),
            'max_selections': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 focus:outline-none focus:ring-0 transition-all duration-200 bg-white border-4 border-amber-900 font-mono text-sm md:text-base uppercase tracking-wide focus:bg-amber-900 focus:text-white focus:placeholder-amber-200 placeholder-amber-900',
                'placeholder': 'Maximum selections allowed (for multiple choice)',
                'required': False,
                'min': 1
            }),
            'seats': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 focus:outline-none focus:ring-0 transition-all duration-200 bg-white border-4 border-amber-900 font-mono text-sm md:text-base uppercase tracking-wide focus:bg-amber-900 focus:text-white focus:placeholder-amber-200 placeholder-amber-900',
                'placeholder': 'Seats to allocate (for Proportional Representation; default 1)',
                'required': False,
                'min': 1
            }),
        }
    
    def clean_max_selections(self):
        max_selections = self.cleaned_data.get('max_selections')
        voting_type = self.cleaned_data.get('voting_type')
        if voting_type == 'single_choice' and max_selections and max_selections > 1:
            raise forms.ValidationError('Single choice voting allows only 1 selection.')
        return max_selections


class OrganisationForm(ModelForm):
    class Meta:
        model = Organisation
        fields = ['name', 'description', 'logo', 'website']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 bg-white border-4 border-amber-900 font-mono text-sm uppercase tracking-wide focus:bg-amber-900 focus:text-white focus:outline-none',
                'placeholder': 'Organisation Name',
                'required': True,
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 bg-white border-4 border-amber-900 font-mono text-sm uppercase tracking-wide focus:bg-amber-900 focus:text-white focus:outline-none',
                'placeholder': 'Describe your organisation',
                'rows': 4,
            }),
            'website': forms.URLInput(attrs={
                'class': 'w-full px-4 py-3 bg-white border-4 border-amber-900 font-mono text-sm uppercase tracking-wide focus:bg-amber-900 focus:text-white focus:outline-none',
                'placeholder': 'https://your-organisation.com',
            }),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.slug:
            instance.slug = slugify(instance.name)
            from voting.models import Organisation as OrgModel
            base_slug = instance.slug
            counter = 1
            while OrgModel.objects.filter(slug=instance.slug).exists():
                instance.slug = f'{base_slug}-{counter}'
                counter += 1
        if commit:
            instance.save()
        return instance


class CandidateForm(ModelForm):
    class Meta:
        model = Candidate
        fields = ['name', 'description', 'party', 'photo', 'ballot']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 focus:outline-none focus:ring-0 transition-all duration-200 bg-white border-4 border-amber-900 font-mono text-sm md:text-base uppercase tracking-wide focus:bg-amber-900 focus:text-white focus:placeholder-amber-200 placeholder-amber-900',
                'placeholder': 'Candidate Name',
                'required': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 focus:outline-none focus:ring-0 transition-all duration-200 bg-white border-4 border-amber-900 font-mono text-sm md:text-base uppercase tracking-wide focus:bg-amber-900 focus:text-white focus:placeholder-amber-200 placeholder-amber-900',
                'placeholder': 'Candidate description or platform',
                'rows': 4,
                'required': False
            }),
            'party': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 focus:outline-none focus:ring-0 transition-all duration-200 bg-white border-4 border-amber-900 font-mono text-sm md:text-base uppercase tracking-wide focus:bg-amber-900 focus:text-white focus:placeholder-amber-200 placeholder-amber-900',
                'placeholder': 'Party or affiliation',
                'required': False
            }),
            'ballot': forms.Select(attrs={
                'class': 'w-full px-4 py-3 focus:outline-none focus:ring-0 transition-all duration-200 bg-white border-4 border-amber-900 font-mono text-sm md:text-base uppercase tracking-wide focus:bg-amber-900 focus:text-white focus:placeholder-amber-200 placeholder-amber-900',
                'required': True
            }),
            'photo': forms.FileInput(attrs={
                'class': 'w-full px-4 py-3 focus:outline-none focus:ring-0 transition-all duration-200 bg-white border-4 border-amber-900 font-mono text-sm md:text-base uppercase tracking-wide focus:bg-amber-900 focus:text-white focus:placeholder-amber-200 placeholder-amber-900',
                'accept': 'image/*',
                'required': False
            }),
        }
    
    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo:
            if photo.size > 5 * 1024 * 1024:
                raise forms.ValidationError('Photo size must be less than 5MB.')
            allowed_types = ['image/jpeg', 'image/png', 'image/gif']
            if photo.content_type not in allowed_types:
                raise forms.ValidationError('Only JPEG, PNG, and GIF images are allowed.')
        return photo


class VoteForm(forms.Form):
    def __init__(self, voting_type='single_choice', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.voting_type = voting_type
        if voting_type == 'single_choice':
            self.fields['candidate'] = forms.ChoiceField(
                label='Select Your Choice',
                choices=[],
                widget=forms.RadioSelect,
                required=True
            )
        elif voting_type == 'multiple_choice':
            self.fields['candidates'] = forms.MultipleChoiceField(
                label='Select Your Choices',
                choices=[],
                widget=forms.CheckboxSelectMultiple,
                required=True
            )
        elif voting_type == 'ranked_choice':
            self.fields['ranked_choices'] = forms.MultipleChoiceField(
                label='Rank Your Choices',
                choices=[],
                widget=forms.CheckboxSelectMultiple,
                required=True
            )
        elif voting_type == 'yes_no':
            self.fields['vote'] = forms.ChoiceField(
                label='Your Vote',
                choices=[('yes', 'Yes'), ('no', 'No')],
                widget=forms.RadioSelect,
                required=True
            )
    
    def set_candidates(self, candidates):
        """Set candidate choices for voting forms"""
        if self.voting_type in ['single_choice', 'multiple_choice']:
            self.fields['candidate'].choices = [(str(c.pk), c.name) for c in candidates]
            if self.voting_type == 'multiple_choice':
                self.fields['candidates'].choices = [(str(c.pk), c.name) for c in candidates]
        elif self.voting_type == 'ranked_choice':
            self.fields['ranked_choices'].choices = [(str(c.pk), c.name) for c in candidates]


class ElectionFilterForm(forms.Form):
    status = forms.ChoiceField(
        label='Status',
        choices=[
            ('', 'All Elections'),
            ('draft', 'Draft'),
            ('scheduled', 'Scheduled'),
            ('active', 'Active'),
            ('closed', 'Closed'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        required=False
    )
    search = forms.CharField(
        label='Search Elections',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 focus:outline-none focus:ring-0 transition-all duration-200 bg-white border-4 border-amber-900 font-mono text-sm md:text-base uppercase tracking-wide focus:bg-amber-900 focus:text-white focus:placeholder-amber-200 placeholder-amber-900',
            'placeholder': 'Search by title or description...'
        })
    )