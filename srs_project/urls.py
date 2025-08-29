from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from flashcards import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    path('', views.home, name='home'),
    path('card/create/', views.card_create, name='card_create'),
    path('collections/', views.collections, name='collections'),
    path('collections/create/', views.create_collection, name='create_collection'),
    path('game_select_category/', views.game_select_category, name='game_select_category'),
    path('game/<str:category>/', views.game, name='game'),
    path('game/end/<str:session_id>/', views.end_game, name='end_game'),  # Изменено на str
    path('stats/', views.stats, name='stats'),
    path('dictionary/', views.dictionary, name='dictionary'),
    path('dictionary/search/', views.dictionary_search, name='dictionary_search'),
]