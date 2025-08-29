from django import forms
from .models import Card
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .hsk_data import HSK1_CHARACTERS
from .hsk2_data import HSK2_CHARACTERS

class CardForm(forms.ModelForm):
    CATEGORY_CHOICES = [
        ('HSK1', 'HSK 1'),
        ('HSK2', 'HSK 2'),
        ('HSK3', 'HSK 3'),
    ]
    
    category = forms.ChoiceField(
        choices=CATEGORY_CHOICES,
        widget=forms.Select(attrs={'id': 'category-select'})
    )
    
    # Инициализация пустого списка для иероглифов (будет заполняться в JavaScript)
    character = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={'id': 'character-select'})
    )
    
    meaning = forms.CharField(
        widget=forms.TextInput(attrs={'id': 'meaning-field', 'readonly': 'readonly'})
    )
    pinyin = forms.CharField(
        widget=forms.TextInput(attrs={'id': 'pinyin-field', 'readonly': 'readonly'})
    )

    class Meta:
        model = Card
        fields = ['category', 'character', 'pinyin', 'meaning']
        widgets = {
            'pinyin': forms.TextInput(attrs={'id': 'pinyin-field'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Инициализация choices для character динамически в JavaScript, поэтому оставляем пустым
        self.fields['character'].choices = []

class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'password1', 'password2']