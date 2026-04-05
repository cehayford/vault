from collections import OrderedDict

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import CustomUser
import re


PHONE_COUNTRY_CODES = [
    ('', '-- Select country code --'),
    ('+213', 'Algeria (+213)'),
    ('+244', 'Angola (+244)'),
    ('+229', 'Benin (+229)'),
    ('+267', 'Botswana (+267)'),
    ('+226', 'Burkina Faso (+226)'),
    ('+257', 'Burundi (+257)'),
    ('+237', 'Cameroon (+237)'),
    ('+238', 'Cape Verde (+238)'),
    ('+236', 'Central African Republic (+236)'),
    ('+235', 'Chad (+235)'),
    ('+269', 'Comoros (+269)'),
    ('+243', 'DR Congo (+243)'),
    ('+242', 'Congo (+242)'),
    ('+253', 'Djibouti (+253)'),
    ('+20', 'Egypt (+20)'),
    ('+240', 'Equatorial Guinea (+240)'),
    ('+291', 'Eritrea (+291)'),
    ('+268', 'Eswatini (+268)'),
    ('+251', 'Ethiopia (+251)'),
    ('+241', 'Gabon (+241)'),
    ('+220', 'Gambia (+220)'),
    ('+233', 'Ghana (+233)'),
    ('+224', 'Guinea (+224)'),
    ('+245', 'Guinea-Bissau (+245)'),
    ('+225', 'Ivory Coast (+225)'),
    ('+254', 'Kenya (+254)'),
    ('+266', 'Lesotho (+266)'),
    ('+231', 'Liberia (+231)'),
    ('+218', 'Libya (+218)'),
    ('+261', 'Madagascar (+261)'),
    ('+265', 'Malawi (+265)'),
    ('+223', 'Mali (+223)'),
    ('+222', 'Mauritania (+222)'),
    ('+230', 'Mauritius (+230)'),
    ('+212', 'Morocco (+212)'),
    ('+258', 'Mozambique (+258)'),
    ('+264', 'Namibia (+264)'),
    ('+227', 'Niger (+227)'),
    ('+234', 'Nigeria (+234)'),
    ('+250', 'Rwanda (+250)'),
    ('+239', 'São Tomé and Príncipe (+239)'),
    ('+221', 'Senegal (+221)'),
    ('+248', 'Seychelles (+248)'),
    ('+232', 'Sierra Leone (+232)'),
    ('+252', 'Somalia (+252)'),
    ('+27', 'South Africa (+27)'),
    ('+211', 'South Sudan (+211)'),
    ('+249', 'Sudan (+249)'),
    ('+255', 'Tanzania (+255)'),
    ('+228', 'Togo (+228)'),
    ('+216', 'Tunisia (+216)'),
    ('+256', 'Uganda (+256)'),
    ('+260', 'Zambia (+260)'),
    ('+263', 'Zimbabwe (+263)'),
    ('+1', 'United States / Canada (+1)'),
    ('+44', 'United Kingdom (+44)'),
    ('+91', 'India (+91)'),
    ('+86', 'China (+86)'),
    ('+81', 'Japan (+81)'),
    ('+49', 'Germany (+49)'),
    ('+33', 'France (+33)'),
    ('+39', 'Italy (+39)'),
    ('+34', 'Spain (+34)'),
    ('+61', 'Australia (+61)'),
    ('+55', 'Brazil (+55)'),
    ('+7', 'Russia / Kazakhstan (+7)'),
    ('+82', 'South Korea (+82)'),
    ('+52', 'Mexico (+52)'),
    ('+32', 'Belgium (+32)'),
    ('+41', 'Switzerland (+41)'),
    ('+43', 'Austria (+43)'),
    ('+46', 'Sweden (+46)'),
    ('+47', 'Norway (+47)'),
    ('+48', 'Poland (+48)'),
    ('+351', 'Portugal (+351)'),
    ('+353', 'Ireland (+353)'),
    ('+358', 'Finland (+358)'),
    ('+31', 'Netherlands (+31)'),
    ('+64', 'New Zealand (+64)'),
    ('+971', 'UAE (+971)'),
    ('+966', 'Saudi Arabia (+966)'),
    ('+972', 'Israel (+972)'),
    ('+90', 'Turkey (+90)'),
    ('+98', 'Iran (+98)'),
    ('+92', 'Pakistan (+92)'),
    ('+880', 'Bangladesh (+880)'),
    ('+62', 'Indonesia (+62)'),
    ('+63', 'Philippines (+63)'),
    ('+65', 'Singapore (+65)'),
    ('+60', 'Malaysia (+60)'),
    ('+66', 'Thailand (+66)'),
    ('+84', 'Vietnam (+84)'),
    ('+852', 'Hong Kong (+852)'),
    ('+886', 'Taiwan (+886)'),
]
PHONE_CODES_PARSING_ORDER = sorted(
    [c for c, _ in PHONE_COUNTRY_CODES if c],
    key=lambda x: -len(x)
)


class CustomUserCreationForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].widget.attrs.update({
            'class': 'w-full px-4 py-2.5 text-sm rounded-md border border-border bg-secondary text-foreground placeholder-muted focus:border-accent focus:outline-none transition-colors duration-fast',
            'placeholder': 'First Name'
        })
        self.fields['last_name'].widget.attrs.update({
            'class': 'w-full px-4 py-2.5 text-sm rounded-md border border-border bg-secondary text-foreground placeholder-muted focus:border-accent focus:outline-none transition-colors duration-fast',
            'placeholder': 'Last Name'
        })     
        self.fields['email'].widget.attrs.update({
            'class': 'w-full px-4 py-2.5 text-sm rounded-md border border-border bg-secondary text-foreground placeholder-muted focus:border-accent focus:outline-none transition-colors duration-fast',
            'placeholder': 'Email Address'
        }) 
        self.fields['password1'].widget.attrs.update({
            'class': 'w-full px-4 py-2.5 text-sm rounded-md border border-border bg-secondary text-foreground placeholder-muted focus:border-accent focus:outline-none transition-colors duration-fast',
            'placeholder': 'Password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'w-full px-4 py-2.5 text-sm rounded-md border border-border bg-secondary text-foreground placeholder-muted focus:border-accent focus:outline-none transition-colors duration-fast',
            'placeholder': 'Confirm Password'
        })
    
    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'email', 'password1', 'password2')
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email
    
    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Passwords do not match.')
        return password2


class LoginForm(AuthenticationForm):
    error_messages = {
        'invalid_login': 'Please enter a correct email address and password.',
        'no_account': 'No account found with this email address. You can sign up instead.',
        'wrong_password': 'Incorrect password. Try again or use "Forgot password?" to reset.',
        'inactive': 'Please verify your email before signing in. Check your inbox/spam, or use "Resend verification code" below.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # AuthenticationForm keeps the identifier key as 'username' even when USERNAME_FIELD='email'
        password_field = self.fields['password']
        for key in ('username', 'email'):
            if key in self.fields:
                del self.fields[key]
                break
        self.fields['email'] = forms.EmailField(
            label='Email address',
            max_length=254,
            widget=forms.EmailInput(attrs={
                'class': 'w-full px-4 py-2.5 text-sm rounded-md border border-border bg-secondary text-foreground placeholder-muted focus:border-accent focus:outline-none transition-colors duration-fast',
                'placeholder': 'Email address',
                'autocomplete': 'email',
            }),
        )
        self.fields['password'] = password_field
        self.fields['password'].widget.attrs.update({
            'class': 'w-full px-4 py-2.5 text-sm rounded-md border border-border bg-secondary text-foreground placeholder-muted focus:border-accent focus:outline-none transition-colors duration-fast',
            'placeholder': 'Password',
            'autocomplete': 'current-password',
        })
        # Ensure order: email then password
        self.fields = OrderedDict([
            ('email', self.fields['email']),
            ('password', self.fields['password']),
        ])

    def clean(self):
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')
        if email is not None and password:
            normalized_email = CustomUser.objects.normalize_email(email.strip())
            self.user_cache = authenticate(
                self.request,
                username=normalized_email,
                password=password,
                backend='userauth.backends.EmailBackend',
            )
            if self.user_cache is None:
                user_exists = CustomUser.objects.filter(email__iexact=normalized_email).exists()
                if user_exists:
                    raise forms.ValidationError(
                        self.error_messages['wrong_password'],
                        code='wrong_password',
                    )
                raise forms.ValidationError(
                    self.error_messages['no_account'],
                    code='no_account',
                )
            if not self.user_cache.is_active:
                raise forms.ValidationError(
                    self.error_messages['inactive'],
                    code='inactive',
                )
        return self.cleaned_data


class UserSignUp(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'password']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 text-sm rounded-md border border-border bg-secondary text-foreground placeholder-muted focus:border-accent focus:outline-none transition-colors duration-fast',
                'placeholder': 'First Name',
                'required': True
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 text-sm rounded-md border border-border bg-secondary text-foreground placeholder-muted focus:border-accent focus:outline-none transition-colors duration-fast',
                'placeholder': 'Last Name',
                'required': True
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-2.5 text-sm rounded-md border border-border bg-secondary text-foreground placeholder-muted focus:border-accent focus:outline-none transition-colors duration-fast',
                'placeholder': 'Email Address',
                'required': True,
                'autocomplete': 'email'
            }),
            'password': forms.PasswordInput(attrs={
                'class': 'w-full px-4 py-2.5 text-sm rounded-md border border-border bg-secondary text-foreground placeholder-muted focus:border-accent focus:outline-none transition-colors duration-fast',
                'placeholder': 'Password',
                'required': True,
                'autocomplete': 'new-password'
            }),
        }
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email
    
    def clean_password(self):
        password = self.cleaned_data.get('password')
        if len(password) < 8:
            raise forms.ValidationError('Password must be at least 8 characters long.')
        if not re.search(r'[A-Z]', password):
            raise forms.ValidationError('Password must contain at least one uppercase letter.')
        if not re.search(r'[a-z]', password):
            raise forms.ValidationError('Password must contain at least one lowercase letter.')
        if not re.search(r'\d', password):
            raise forms.ValidationError('Password must contain at least one digit.')
        return password


class MFADisableForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password'].widget.attrs.update({
            'class': 'w-full px-4 py-2.5 text-sm rounded-md border border-border bg-secondary text-foreground placeholder-muted focus:border-accent focus:outline-none transition-colors duration-fast',
            'placeholder': 'Enter your password to confirm',
            'autocomplete': 'current-password'
        })
    password = forms.CharField(label='Password', widget=forms.PasswordInput, required=True)


class MFAVerifyForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['token'].widget.attrs.update({
            'class': 'w-full px-4 py-3 text-center text-2xl tracking-[0.3em] rounded-md border border-border bg-secondary text-foreground placeholder-muted focus:border-accent focus:outline-none transition-colors duration-fast',
            'placeholder': '000000',
            'maxlength': '6',
            'pattern': '[0-9]{6}',
            'autocomplete': 'one-time-code'
        })
        self.fields['backup_code'].widget.attrs.update({
            'class': 'w-full px-4 py-2.5 text-sm rounded-md border border-border bg-secondary text-foreground placeholder-muted focus:border-accent focus:outline-none transition-colors duration-fast',
            'placeholder': 'Enter backup code',
            'maxlength': '6',
            'pattern': '[0-9]{6}'
        })
    token = forms.CharField(label='Verification Code', max_length=6, required=True)
    backup_code = forms.CharField(label='Backup Code', max_length=6, required=False)


class ContactForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].widget.attrs.update({
            'class': 'w-full px-4 py-2.5 text-sm rounded-md border border-border bg-secondary text-foreground placeholder-muted focus:border-accent focus:outline-none transition-colors duration-fast',
            'placeholder': 'Your Name',
            'required': True
        })        
        self.fields['email'].widget.attrs.update({
            'class': 'w-full px-4 py-2.5 text-sm rounded-md border border-border bg-secondary text-foreground placeholder-muted focus:border-accent focus:outline-none transition-colors duration-fast',
            'placeholder': 'Your Email',
            'required': True,
            'type': 'email'
        })
        self.fields['message'].widget.attrs.update({
            'class': 'w-full px-4 py-2.5 text-sm rounded-md border border-border bg-secondary text-foreground placeholder-muted focus:border-accent focus:outline-none transition-colors duration-fast',
            'placeholder': 'Your Message',
            'required': True,
            'rows': 4
        })
    name = forms.CharField(label='Name', max_length=100, required=True)
    email = forms.EmailField(label='Email', required=True)
    message = forms.CharField(label='Message', widget=forms.Textarea, required=True)


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = [
            'first_name', 'last_name', 'nickname', 'phone_number', 'address',
            'date_of_birth', 'citizenship_country',
        ]
        labels = {
            'citizenship_country': 'Country of citizenship',
        }
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border border-border bg-secondary px-4 py-3 text-sm text-foreground placeholder-muted focus:border-accent focus:outline-none transition-colors duration-fast',
                'placeholder': 'First name',
                'autocomplete': 'given-name',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border border-border bg-secondary px-4 py-3 text-sm text-foreground placeholder-muted focus:border-accent focus:outline-none transition-colors duration-fast',
                'placeholder': 'Last name',
                'autocomplete': 'family-name',
            }),
            'nickname': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border border-border bg-secondary px-4 py-3 text-sm text-foreground placeholder-muted focus:border-accent focus:outline-none transition-colors duration-fast',
                'placeholder': 'Display name',
                'autocomplete': 'nickname',
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border border-border bg-secondary px-4 py-3 text-sm text-foreground placeholder-muted focus:border-accent focus:outline-none transition-colors duration-fast',
                'placeholder': 'Phone number (without country code)',
                'inputmode': 'numeric',
                'autocomplete': 'tel-national',
            }),
            'address': forms.Textarea(attrs={
                'class': 'w-full rounded-lg border border-border bg-secondary px-4 py-3 text-sm text-foreground placeholder-muted focus:border-accent focus:outline-none transition-colors duration-fast resize-y',
                'placeholder': 'Address',
                'rows': 3,
                'autocomplete': 'street-address',
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'w-full rounded-lg border border-border bg-secondary px-4 py-3 text-sm text-foreground focus:border-accent focus:outline-none transition-colors duration-fast',
                'type': 'date',
                'autocomplete': 'bday',
            }),
            'citizenship_country': forms.Select(attrs={
                'class': 'w-full rounded-lg border border-border bg-secondary px-4 py-3 text-sm text-foreground focus:border-accent focus:outline-none transition-colors duration-fast',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Insert country code field before phone_number and set initial from existing number
        self.fields['phone_country_code'] = forms.ChoiceField(
            choices=PHONE_COUNTRY_CODES,
            required=False,
            label='Country code (auto-added to phone number)',
            widget=forms.Select(attrs={
                'class': 'w-full rounded-lg border border-border bg-secondary px-4 py-3 text-sm text-foreground focus:border-accent focus:outline-none transition-colors duration-fast',
            }),
        )
        keys = list(self.fields.keys())
        keys.remove('phone_country_code')
        idx = keys.index('phone_number')
        new_order = keys[:idx] + ['phone_country_code', 'phone_number'] + keys[idx + 1:]
        self.fields = OrderedDict((k, self.fields[k]) for k in new_order)
        if self.instance and getattr(self.instance, 'phone_number', None):
            raw = (self.instance.phone_number or '').strip()
            if raw.startswith('+'):
                for code in PHONE_CODES_PARSING_ORDER:
                    if raw.startswith(code):
                        self.initial['phone_country_code'] = code
                        self.initial['phone_number'] = raw[len(code):].strip()
                        break

    def save(self, commit=True):
        code = (self.cleaned_data.get('phone_country_code') or '').strip()
        number = (self.cleaned_data.get('phone_number') or '').strip().replace(' ', '')
        if number:
            self.instance.phone_number = (code + number) if code else number
        else:
            self.instance.phone_number = ''
        return super().save(commit=commit)

