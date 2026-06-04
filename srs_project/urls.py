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
    path('change-password/', views.change_password, name='change_password'),
    path('card/create/', views.card_create, name='card_create'),
    path('collections/', views.collections, name='collections'),
    path('collections/create/', views.create_collection, name='create_collection'),
    path('game_select_category/', views.game_select_category, name='game_select_category'),
    path('game/group/save/', views.save_group_result, name='save_group_result'),
    path('game/group/<str:category>/<int:group_index>/', views.game_group, name='game_group'),
    path('game/<str:category>/<int:count>/', views.game, name='game'),
    path('game/end/<str:session_id>/', views.end_game, name='end_game'),  # Изменено на str
    path('stats/', views.stats, name='stats'),
    path('dictionary/', views.dictionary, name='dictionary'),
    path('dictionary/search/', views.dictionary_search, name='dictionary_search'),
    path('card/<int:card_id>/delete/', views.card_delete, name='card_delete'),
    

    # ── Сессии изучения (SM-2) ──────────────────────────────────────────────
    path('study/', views.study_select, name='study_select'),
    path('study/due-count/', views.study_due_count, name='study_due_count'),
    path('study/answer/', views.study_answer, name='study_answer'),
    path('study/<str:category>/', views.study_session_start, name='study_session_start'),
]
