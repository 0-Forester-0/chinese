from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .forms import CardForm, RegisterForm
from .models import Card, Collection, GameSession
from .hsk_data import HSK1_CHARACTERS
from .hsk2_data import HSK2_CHARACTERS
from .hsk3_data import HSK3_CHARACTERS
from pymongo import MongoClient
from bson import ObjectId
import random
import os
import json
import datetime
import unicodedata

HSK_CHARACTERS = {
    'HSK1': HSK1_CHARACTERS,
    'HSK2': HSK2_CHARACTERS,
    'HSK3': HSK3_CHARACTERS,
}

HSK_WORDS_COUNT = {
    'HSK1': 151,
    'HSK2': 250,
    'HSK3': 762
}

def remove_tones(pinyin_str):
    """Преобразует пиньинь с тонами в пиньинь без тонов, убирая пробелы."""
    try:
        # Нормализуем строку, чтобы разделить диакритические знаки
        normalized = unicodedata.normalize('NFD', pinyin_str.lower())
        # Удаляем диакритические знаки (тоны)
        without_tones = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
        # Убираем пробелы
        return without_tones.replace(' ', '')
    except Exception as e:
        print(f"Error removing tones from pinyin '{pinyin_str}': {str(e)}")
        return pinyin_str.replace(' ', '')  # Возвращаем строку без пробелов в случае ошибки

def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = RegisterForm()
    return render(request, 'register.html', {'form': form})

@login_required
def home(request):
    cards = Card.objects.filter(user=request.user)
    
    stats = {'HSK1': {'correct': 0, 'total': 0, 'percentage': 0.0},
             'HSK2': {'correct': 0, 'total': 0, 'percentage': 0.0},
             'HSK3': {'correct': 0, 'total': 0, 'percentage': 0.0}}
    weak_words = []
    strong_words = []

    for category in stats.keys():
        completed_sessions = GameSession.objects.filter(
            user=request.user, 
            category=category,
            total_answers=len(HSK_CHARACTERS[category])
        ).order_by('-percentage')
        
        # Находим сессию с лучшим процентом
        if completed_sessions.exists():
            stats[category]['best_percentage'] = completed_sessions.first().percentage
            
        sessions = GameSession.objects.filter(user=request.user, category=category)
        print(f"Sessions for {category}: {sessions.count()}")
        for session in sessions:
            stats[category]['correct'] += session.correct_answers
            stats[category]['total'] += session.total_answers
            answer_history = session.answer_history if session.answer_history is not None else {}
            print(f"Answer history for session {session.id}: {answer_history}")
            for character, history in answer_history.items():
                correct = history.get('correct', 0)
                total = history.get('total', 0)
                if total > 0:
                    percentage = (correct / total) * 100
                    word_data = {
                        'character': character,
                        'pinyin': HSK_CHARACTERS[category][character]['pinyin'],
                        'meaning': HSK_CHARACTERS[category][character]['meaning'],
                        'percentage': round(percentage, 1)
                    }
                    if percentage < 50:
                        weak_words.append(word_data)
                    elif percentage >= 80:
                        strong_words.append(word_data)
        if stats[category]['total'] > 0:
            stats[category]['percentage'] = round((stats[category]['correct'] / stats[category]['total']) * 100, 1)
    
    weak_words = sorted(weak_words, key=lambda x: x['percentage'])[:5]
    strong_words = sorted(strong_words, key=lambda x: x['percentage'], reverse=True)[:5]
    
    print(f"Stats: {stats}")
    print(f"Weak words: {weak_words}")
    print(f"Strong words: {strong_words}")
    
    return render(request, 'home.html', {
        'cards': cards,
        'stats': stats,
        'weak_words': weak_words,
        'strong_words': strong_words
    })

# @login_required
# def stats(request):
#     sessions = GameSession.objects.filter(user=request.user).order_by('-created_at')
#     stats = {'HSK1': {'correct': 0, 'total': 0, 'percentage': 0.0},
#              'HSK2': {'correct': 0, 'total': 0, 'percentage': 0.0},
#              'HSK3': {'correct': 0, 'total': 0, 'percentage': 0.0}}
    
#     for session in sessions:
#         stats[session.category]['correct'] += session.correct_answers
#         stats[session.category]['total'] += session.total_answers
#         if stats[session.category]['total'] > 0:
#             stats[session.category]['percentage'] = round((stats[session.category]['correct'] / stats[session.category]['total']) * 100, 1)
    
#     print(f"All sessions: {list(sessions)}")
#     print(f"Stats for stats page: {stats}")
    
#     return render(request, 'stats.html', {
#         'sessions': sessions,
#         'stats': stats
#     })

@login_required
def stats(request):
    sessions = GameSession.objects.filter(user=request.user).order_by('-created_at')
    HSK_TOTAL = {'HSK1': 151, 'HSK2': 250, 'HSK3': 762}
    stats = {
        'HSK1': {'best_percentage': 0.0},
        'HSK2': {'best_percentage': 0.0},
        'HSK3': {'best_percentage': 0.0}
    }

    # Для таблицы: пересчитываем процент для каждой сессии
    for session in sessions:
        total_cards = HSK_TOTAL.get(session.category, 0)
        if total_cards > 0:
            session.calculated_percentage = round((session.correct_answers / total_cards) * 100, 1)
        else:
            session.calculated_percentage = 0.0

    # Для графика: ищем лучший процент по каждой категории
    for cat in ['HSK1', 'HSK2', 'HSK3']:
        cat_sessions = [s for s in sessions if s.category == cat]
        if cat_sessions:
            stats[cat]['best_percentage'] = max(s.calculated_percentage for s in cat_sessions)

    return render(request, 'stats.html', {
        'sessions': sessions,
        'stats': stats
    })

@login_required
def card_create(request):
    if request.method == 'POST':
        form = CardForm(request.POST)
        if form.is_valid():
            card = form.save(commit=False)
            card.user = request.user
            category = form.cleaned_data['category']
            character = form.cleaned_data['character']
            card.meaning = HSK_CHARACTERS[category][character]['meaning']
            card.pinyin = HSK_CHARACTERS[category][character]['pinyin']
            card.category = category
            card.save()
            return redirect('home')
    else:
        form = CardForm()
    return render(request, 'card_create.html', {
        'form': form,
        'hsk_characters': json.dumps(HSK_CHARACTERS),
    })

@login_required
def create_collection(request):
    client = MongoClient('mongodb+srv://forester:FOR010604est@srs.u9xgrvs.mongodb.net/?retryWrites=true&w=majority&appName=SRS')
    db = client['chinese_srs']
    if request.method == 'POST':
        num_cards = int(request.POST.get('num_cards', 10))
        category = request.POST.get('category', 'HSK1')
        cards = list(db['flashcards_card'].find({'user_id': request.user.id, 'category': category}))
        selected_cards = random.sample(cards, min(num_cards, len(cards))) if cards else []
        card_ids = [str(card['_id']) for card in selected_cards]
        collection = Collection.objects.create(
            user=request.user,
            name=f"Подборка {category} ({len(selected_cards)} карточек)",
            category=category,
            cards=card_ids
        )
        return redirect('collections')
    return render(request, 'create_collection.html', {'categories': ['HSK1', 'HSK2', 'HSK3']})

@login_required
def collections(request):
    collections = Collection.objects.filter(user=request.user)
    client = MongoClient('mongodb+srv://forester:FOR010604est@srs.u9xgrvs.mongodb.net/?retryWrites=true&w=majority&appName=SRS')
    db = client['chinese_srs']
    for collection in collections:
        card_ids = [ObjectId(card_id) for card_id in collection.cards]
        cards = db['flashcards_card'].find({'_id': {'$in': card_ids}})
        collection.cards = list(cards)
        collection.card_count = len(collection.cards)
    return render(request, 'collections.html', {'collections': collections})

@login_required
def game_select_category(request):
    categories = ['HSK1', 'HSK2', 'HSK3']
    return render(request, 'game_select_category.html', {'categories': categories})

@login_required
# def game(request, category):
#     if category not in HSK_CHARACTERS:
#         return redirect('game_select_category')

#     client = MongoClient('mongodb+srv://forester:FOR010604est@srs.u9xgrvs.mongodb.net/?retryWrites=true&w=majority&appName=SRS')
#     db = client['chinese_srs']

#     session = GameSession.objects.filter(user=request.user, category=category, total_answers__lt=len(HSK_CHARACTERS[category])).first()
#     if not session:
#         cards_data = [{'character': char, 'pinyin': data['pinyin'], 'meaning': data['meaning']} for char, data in HSK_CHARACTERS[category].items()]
#         session = GameSession.objects.create(
#             user=request.user,
#             category=category,
#             remaining_cards=[card['character'] for card in cards_data],
#             answer_history={}
#         )
#         print(f"Created new session: {str(session.id)}")
    
#     print(f"Rendering game with session_id: {str(session.id)}")
#     cards_data = [{'character': char, 'pinyin': data['pinyin'], 'meaning': data['meaning']} for char, data in HSK_CHARACTERS[category].items()]
def game(request, category):
    if category not in HSK_CHARACTERS:
        return redirect('game_select_category')

    client = MongoClient('mongodb+srv://forester:FOR010604est@srs.u9xgrvs.mongodb.net/?retryWrites=true&w=majority&appName=SRS')
    db = client['chinese_srs']

    # Удаляем все сессии пользователя для этой категории с total_answers=0
    # db['flashcards_gamesession'].delete_many({
    #     'user_id': request.user.id,
    #     'category': category,
    #     'total_answers': 0
    # })


    cards_data = [{'character': char, 'pinyin': data['pinyin'], 'meaning': data['meaning']} 
                     for char, data in HSK_CHARACTERS[category].items()]

    # Создаем новую сессию только если нет активных
    session = db['flashcards_gamesession'].find_one({
        'user_id': request.user.id,
        'category': category,
        'is_finished': False
    })

    if not session:
        
        new_session = {
            'user_id': request.user.id,
            'category': category,
            'remaining_cards': [card['character'] for card in cards_data],
            'answer_history': {},
            'correct_answers': 0,
            'total_answers': 0,
            'percentage': 0.0,
            'created_at': datetime.datetime.now(),
            'updated_at': datetime.datetime.now(),
            'is_finished': False
        }
        session_id = db['flashcards_gamesession'].insert_one(new_session).inserted_id
        session = db['flashcards_gamesession'].find_one({'_id': session_id})
        print(f"Created new session: {session_id}")  
    else:
        print(f"Continuing existing session: {session['_id']}")

    total_cards_in_category = len(HSK_CHARACTERS[category])

    return render(request, 'game.html', {
        'cards_json': json.dumps(cards_data),
        'session_id': str(session['_id']),
        'category': category,
        'total_cards_in_category': total_cards_in_category,
        'correct_answers': session['correct_answers'],
        'total_answers': session['total_answers'],
        'percentage': session['percentage'],
        'remaining_cards': json.dumps(session['remaining_cards'])
    })

@login_required
@csrf_exempt
def end_game(request, session_id):
    if not session_id or session_id == 'None':
        print("Invalid session_id received:", session_id)
        return JsonResponse({'status': 'error', 'message': 'Invalid session ID'}, status=400)
    
    client = MongoClient('mongodb+srv://forester:FOR010604est@srs.u9xgrvs.mongodb.net/?retryWrites=true&w=majority&appName=SRS')
    db = client['chinese_srs']
    
    try:
        session = db['flashcards_gamesession'].find_one({'_id': ObjectId(session_id), 'user_id': request.user.id})
        if not session:
            print(f"Session not found for ID: {session_id}")
            return JsonResponse({'status': 'error', 'message': 'Session not found'}, status=404)
        
        if request.method == 'POST':
            data = json.loads(request.body)
            correct_answers = data.get('correct_answers', session.get('correct_answers', 0))
            total_answers = data.get('total_answers', session.get('total_answers', 0))
            remaining_cards = data.get('remaining_cards', session.get('remaining_cards', []))
            answer_history = data.get('answer_history', {})
            is_finished = data.get('is_finished', False)  # <-- вот это

            print(f"Received answer_history: {answer_history}")

            current_answer_history = session.get('answer_history', {})
            for character, history in answer_history.items():
                if character not in current_answer_history:
                    current_answer_history[character] = {'correct': 0, 'total': 0}
                current_answer_history[character]['correct'] += history.get('correct', 0)
                current_answer_history[character]['total'] += history.get('total', 0)

            percentage = (correct_answers / total_answers * 100) if total_answers > 0 else 0.0

            db['flashcards_gamesession'].update_one(
                {'_id': ObjectId(session_id)},
                {
                    '$set': {
                        'correct_answers': correct_answers,
                        'total_answers': total_answers,
                        'remaining_cards': remaining_cards,
                        'answer_history': current_answer_history,
                        'percentage': percentage,
                        'updated_at': datetime.datetime.now(),
                        'is_finished': is_finished  # <-- только если надо
                    }
                }
            )
            print(f"Saved session: {session_id}, answer_history: {current_answer_history}, is_finished: {is_finished}")

            return JsonResponse({'status': 'success'})
        return redirect('home')
    except Exception as e:
        print(f"Error querying session with ID {session_id}: {str(e)}")
        return JsonResponse({'status': 'error', 'message': 'Invalid session ID'}, status=400)
        
        return redirect('home')
    except Exception as e:
        print(f"Error querying session with ID {session_id}: {str(e)}")
        return JsonResponse({'status': 'error', 'message': 'Invalid session ID'}, status=400)

@login_required
def dictionary(request):
    return render(request, 'dictionary.html')

@login_required
@csrf_exempt
def dictionary_search(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            query = data.get('query', '').lower().strip()
            if not query:
                return JsonResponse([], safe=False)
            
            results = []
            query_without_tones = remove_tones(query)
            print(f"Search query: {query}, Query without tones: {query_without_tones}")
            
            for category in HSK_CHARACTERS:
                for character, data in HSK_CHARACTERS[category].items():
                    pinyin_without_tones = remove_tones(data['pinyin'].lower())
                    print(f"Checking word: {character}, Pinyin: {data['pinyin']}, Pinyin without tones: {pinyin_without_tones}")
                    if (query_without_tones in pinyin_without_tones or
                        query in data['meaning'].lower()):
                        results.append({
                            'character': character,
                            'pinyin': data['pinyin'],
                            'meaning': data['meaning'],
                            'category': category
                        })
            
            print(f"Search results: {results}")
            return JsonResponse(results, safe=False)
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {str(e)}")
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)
