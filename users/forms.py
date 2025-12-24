from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import CustomUser, District, Position

# Миксин для Tailwind-классов (без изменений — он хороший)
class TailwindInputMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.base_input_class = (
            'w-full bg-gray-100 border border-gray-200 rounded-xl px-4 py-3 '
            'outline-none focus:ring-2 focus:ring-blue-500 transition-all '
            'placeholder-gray-500 text-lg'
        )

        self.password_input_class = self.base_input_class.replace('px-4', 'pl-4 pr-12')

        for field_name, field in self.fields.items():
            if field_name in ('password1', 'password2'):
                if not isinstance(field.widget, forms.PasswordInput):
                    field.widget = forms.PasswordInput()
                field.widget.attrs.update({
                    'class': self.password_input_class,
                    'autocomplete': 'new-password',
                })
                if field_name == 'password1':
                    field.widget.attrs['id'] = 'id_password1'
                    field.widget.attrs['placeholder'] = 'Придумайте пароль'
                else:
                    field.widget.attrs['id'] = 'id_password2'
                    field.widget.attrs['placeholder'] = 'Повторите пароль'

            elif isinstance(field, (forms.ChoiceField, forms.ModelChoiceField)):
                field.widget.attrs.update({
                    'class': (
                        'w-full bg-gray-100 border border-gray-200 rounded-xl px-4 py-3 '
                        'outline-none focus:ring-2 focus:ring-blue-500 transition-all '
                        'appearance-none text-gray-700 text-lg'
                    )
                })

            else:
                if 'class' not in field.widget.attrs:
                    field.widget.attrs['class'] = self.base_input_class

            if field_name == 'username':
                field.widget.attrs['placeholder'] = 'Логин (обязательно)'


# Форма входа (без изменений)
class UserLoginForm(TailwindInputMixin, AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'Логин'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Пароль'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = ''
        self.fields['password'].label = ''


# Форма регистрации (без изменений)
class UserRegistrationForm(TailwindInputMixin, UserCreationForm):
    department_type = forms.ChoiceField(
        label="Тип регистрации",
        choices=[
            ('', 'Выберите тип'),
            ('apparat', 'Аппарат'),
            ('district', 'Районное отделение'),
        ],
        required=True,
    )

    last_name = forms.CharField(label="Фамилия", max_length=150, widget=forms.TextInput(attrs={'placeholder': 'Фамилия'}))
    first_name = forms.CharField(label="Имя", max_length=150, widget=forms.TextInput(attrs={'placeholder': 'Имя'}))
    middle_name = forms.CharField(label="Отчество", max_length=150, required=False, widget=forms.TextInput(attrs={'placeholder': 'Отчество (при наличии)'}))
    email = forms.EmailField(label="Email", required=True, widget=forms.EmailInput(attrs={'placeholder': 'your@email.com'}))

    district = forms.ModelChoiceField(
        label="Район",
        queryset=District.objects.all(),
        required=False,
        empty_label="Выберите район",
    )
    position = forms.ModelChoiceField(
        label="Должность",
        queryset=Position.objects.all(),
        required=False,
        empty_label="Выберите должность",
    )

    class Meta:
        model = CustomUser
        fields = (
            'last_name', 'first_name', 'middle_name', 'email',
            'department_type', 'district', 'position',
            'username', 'password1', 'password2',
        )

    BAD_WORDS = [
        'huylan', 'pidor', 'pidoras', 'gandon', 'chmo', 'suka', 'blyat', 'blyad',
        'idiot', 'fuck', 'fack', 'sosat', 'ebat', 'huy', 'hui', 'pizda', 'mudak',
        'dolboeb', 'pedik', 'shlyuha', 'blya', 'nahui', 'zaebal', 'zaebis',
    ]

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            username_lower = username.lower()
            for word in self.BAD_WORDS:
                if word in username_lower:
                    raise forms.ValidationError("Логин содержит недопустимые слова.")
        return username

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].label = 'Пароль'
        self.fields['password2'].label = 'Подтверждение пароля'

        fields_to_hide_label = ['last_name', 'first_name', 'middle_name', 'username', 'department_type']
        for field_name in fields_to_hide_label:
            if field_name in self.fields:
                self.fields[field_name].label = ''

        # Динамическая фильтрация должностей
        selected_district_id = None
        if self.data and 'district' in self.data:
            try:
                selected_district_id = int(self.data.get('district'))
            except (ValueError, TypeError):
                pass

        if selected_district_id:
            try:
                selected_district = District.objects.get(id=selected_district_id)
                head_position = Position.objects.filter(title__iexact="руководитель районного отделения").first()
                if head_position:
                    if CustomUser.objects.filter(district=selected_district, position=head_position).exists():
                        self.fields['position'].queryset = Position.objects.exclude(id=head_position.id)
                    else:
                        self.fields['position'].queryset = Position.objects.all()
                else:
                    self.fields['position'].queryset = Position.objects.all()
            except District.DoesNotExist:
                self.fields['position'].queryset = Position.objects.all()
        else:
            self.fields['position'].queryset = Position.objects.all()

    def clean(self):
        cleaned_data = super().clean()
        department_type = cleaned_data.get('department_type')

        if department_type == 'apparat':
            raise forms.ValidationError("Регистрация для Аппарата временно недоступна.")
        elif department_type == 'district':
            if not cleaned_data.get('district'):
                self.add_error('district', 'Выберите район.')
            if not cleaned_data.get('position'):
                self.add_error('position', 'Выберите должность.')

            position = cleaned_data.get('position')
            district = cleaned_data.get('district')
            if position and district:
                if position.title.lower() == "руководитель районного отделения":
                    if CustomUser.objects.filter(district=district, position=position).exists():
                        self.add_error('position', 'В этом районе уже есть Руководитель.')

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.last_name = self.cleaned_data['last_name']
        user.first_name = self.cleaned_data['first_name']
        user.middle_name = self.cleaned_data.get('middle_name', '')
        user.email = self.cleaned_data['email']
        user.department_type = self.cleaned_data['department_type']

        if self.cleaned_data['department_type'] == 'district':
            user.district = self.cleaned_data['district']
            user.position = self.cleaned_data['position']

        if commit:
            user.save()

        return user


# === ФОРМА РЕДАКТИРОВАНИЯ ПРОФИЛЯ ===
class UserUpdateForm(TailwindInputMixin, forms.ModelForm):
    class Meta:
        model = CustomUser
        # Указываем ВСЕ поля, которые нужны, кроме аватара
        fields = [
            'username',
            'last_name',
            'first_name',
            'middle_name',
            'email',
            'district',
            'position',
            'department_type',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if 'avatar' in self.fields:
            del self.fields['avatar']
