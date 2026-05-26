from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .forms import CardForm, RegisterForm
from .models import Card, Collection, GameSession
from .hsk_order import HSK1_ORDER, HSK2_ORDER, HSK3_ORDER
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

HSK_ORDER = {
    'HSK1': HSK1_ORDER,
    'HSK2': HSK2_ORDER,
    'HSK3': HSK3_ORDER,
}

HSK_CHARACTERS = {
    'HSK1': HSK1_CHARACTERS,
    'HSK2': HSK2_CHARACTERS,
    'HSK3': HSK3_CHARACTERS,
}

HSK_WORDS_COUNT = {
    'HSK1': 496,
    'HSK2': 764,
    'HSK3': 966
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
    HSK_TOTAL = {'HSK1': 496, 'HSK2': 764, 'HSK3': 966}

    # ── Статистика тестов ───────────────────────────────────────────────────
    test_stats = {
        'HSK1': {'best_percentage': 0.0},
        'HSK2': {'best_percentage': 0.0},
        'HSK3': {'best_percentage': 0.0},
    }
    for session in sessions:
        total_cards = HSK_TOTAL.get(session.category, 0)
        session.calculated_percentage = (
            round((session.correct_answers / total_cards) * 100, 1)
            if total_cards > 0 else 0.0
        )
    for cat in ['HSK1', 'HSK2', 'HSK3']:
        cat_sessions = [s for s in sessions if s.category == cat]
        if cat_sessions:
            test_stats[cat]['best_percentage'] = max(
                s.calculated_percentage for s in cat_sessions
            )

    # ── SM-2 статистика ─────────────────────────────────────────────────────
    client = MongoClient(MONGO_URI)
    db     = client['chinese_srs']
    now    = datetime.datetime.now()

    sm2_records = list(db['card_study_stats'].find({'user_id': request.user.id}))
    client.close()

    # Агрегат по категориям
    sm2_stats = {}
    for cat, total in HSK_TOTAL.items():
        cat_records = [r for r in sm2_records if r.get('category') == cat]

        studied     = len(cat_records)
        due_today   = sum(1 for r in cat_records if r.get('next_review', now) <= now)
        # «Освоено» — карточки с n >= 2 и интервалом >= 7 дней
        mastered    = sum(1 for r in cat_records if r.get('n', 0) >= 2 and r.get('interval', 0) >= 7)
        new_cards   = total - studied
        total_answers   = sum(r.get('total_count', 0)   for r in cat_records)
        correct_answers = sum(r.get('correct_count', 0) for r in cat_records)
        avg_ef = (
            round(sum(r.get('ef', 2.5) for r in cat_records) / studied, 2)
            if studied > 0 else 2.5
        )
        accuracy = (
            round(correct_answers / total_answers * 100, 1)
            if total_answers > 0 else 0.0
        )

        sm2_stats[cat] = {
            'total':           total,
            'studied':         studied,
            'due_today':       due_today,
            'mastered':        mastered,
            'new_cards':       new_cards,
            'total_answers':   total_answers,
            'correct_answers': correct_answers,
            'accuracy':        accuracy,
            'avg_ef':          avg_ef,
            'studied_pct':     round(studied  / total * 100, 1) if total > 0 else 0,
            'mastered_pct':    round(mastered / total * 100, 1) if total > 0 else 0,
        }

    # Ближайшие к повторению карточки (до 30 штук) — для таблицы
    upcoming = sorted(
        sm2_records,
        key=lambda r: r.get('next_review', now)
    )[:30]
    for r in upcoming:
        char = r.get('character', '')
        cat  = r.get('category', 'HSK1')
        r['pinyin']  = HSK_CHARACTERS.get(cat, {}).get(char, {}).get('pinyin', '')
        r['meaning'] = HSK_CHARACTERS.get(cat, {}).get(char, {}).get('meaning', '')
        nr = r.get('next_review', now)
        r['overdue'] = nr <= now
        r['next_review_str'] = nr.strftime('%d.%m.%Y') if hasattr(nr, 'strftime') else str(nr)

    # Суммарный SM-2 по всем категориям (для сводной карточки)
    sm2_total = {
        'studied':       sum(v['studied']   for v in sm2_stats.values()),
        'mastered':      sum(v['mastered']  for v in sm2_stats.values()),
        'due_today':     sum(v['due_today'] for v in sm2_stats.values()),
        'total_answers': sum(v['total_answers'] for v in sm2_stats.values()),
    }

    return render(request, 'stats.html', {
        'sessions':   sessions,
        'test_stats': test_stats,           # переименовано из stats → test_stats
        'sm2_stats':  sm2_stats,
        'sm2_total':  sm2_total,
        'upcoming':   upcoming,
    })

@login_required
def card_delete(request, card_id):
    if request.method == 'POST':
        card = Card.objects.filter(id=card_id, user=request.user).first()
        if card:
            card.delete()
    return redirect('home')


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
def get_ordered_chars(category):
    """
    Возвращает слова категории в педагогическом порядке.
    Слова из ORDER идут первыми, остальные добавляются в конец.
    """
    all_chars = list(HSK_CHARACTERS[category].keys())
    order = HSK_ORDER.get(category, [])

    if not order:
        return all_chars  # для HSK2/3 — как было

    # Фильтруем: только те, что реально есть в словаре
    ordered = [c for c in order if c in HSK_CHARACTERS[category]]

    # Добавляем в конец всё, что не попало в список
    ordered_set = set(ordered)
    tail = [c for c in all_chars if c not in ordered_set]

    return ordered + tail

@login_required
def game_select_category(request):
    categories = ['HSK1', 'HSK2', 'HSK3']
    count_options = [10, 20, 30]
    return render(request, 'game_select_category.html', {
        'categories': categories,
        'count_options': count_options,
    })

@login_required
def game(request, category, count=20):
    if category not in HSK_CHARACTERS:
        return redirect('game_select_category')

    count = max(5, min(50, count))  # защита от некорректных значений

    client = MongoClient(MONGO_URI)
    db = client['chinese_srs']

    # Выбираем случайные count иероглифов из категории
    all_chars = list(HSK_CHARACTERS[category].keys())
    selected_chars = random.sample(all_chars, min(count, len(all_chars)))

    cards_data = [
        {
            'character': char,
            'pinyin': HSK_CHARACTERS[category][char]['pinyin'],
            'meaning': HSK_CHARACTERS[category][char]['meaning'],
        }
        for char in selected_chars
    ]

    # Создаём новую сессию для этого захода
    new_session = {
        'user_id': request.user.id,
        'category': category,
        'count': count,
        'remaining_cards': selected_chars,
        'answer_history': {},
        'correct_answers': 0,
        'total_answers': 0,
        'percentage': 0.0,
        'created_at': datetime.datetime.now(),
        'updated_at': datetime.datetime.now(),
        'is_finished': False,
    }
    session_id = db['flashcards_gamesession'].insert_one(new_session).inserted_id
    client.close()

    return render(request, 'game.html', {
        'cards_json': json.dumps(cards_data),
        'session_id': str(session_id),
        'category': category,
        'count': count,
        'total_cards_in_category': count,
        'correct_answers': 0,
        'total_answers': 0,
        'percentage': 0.0,
        'remaining_cards': json.dumps(selected_chars),
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

MONGO_URI = 'mongodb+srv://forester:FOR010604est@srs.u9xgrvs.mongodb.net/?retryWrites=true&w=majority&appName=SRS'


def _sm2_update(stats, quality):
    """
    Обновляет параметры карточки по алгоритму SM-2.
    quality: 0 — не знаю, 3 — с трудом, 5 — легко
    """
    ef       = stats.get('ef', 2.5)
    n        = stats.get('n', 0)
    interval = stats.get('interval', 1)

    if quality >= 3:
        if n == 0:
            interval = 1
        elif n == 1:
            interval = 6
        else:
            interval = round(interval * ef)
        n += 1
    else:
        # Провал — сброс
        n        = 0
        interval = 1

    # Обновление коэффициента лёгкости
    ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ef = max(1.3, round(ef, 4))

    next_review = datetime.datetime.now() + datetime.timedelta(days=interval)
    return ef, n, interval, next_review


@login_required
def study_select(request):
    """Страница выбора категории и количества карточек."""
    if request.method == 'POST':
        category = request.POST.get('category', 'HSK1')
        count    = max(1, min(200, int(request.POST.get('count', 20))))
        return redirect('study_session_start', category=category, count=count)
    return render(request, 'study_select.html', {
        'categories': ['HSK1', 'HSK2', 'HSK3']
    })


@login_required
def study_due_count(request):
    """
    AJAX: возвращает количество карточек, готовых к повторению,
    и количество новых карточек для выбранной категории.
    """
    category = request.GET.get('category', 'HSK1')
    if category not in HSK_CHARACTERS:
        return JsonResponse({'due': 0, 'new_count': 0})

    client = MongoClient(MONGO_URI)
    db     = client['chinese_srs']
    now    = datetime.datetime.now()

    all_chars = set(HSK_CHARACTERS[category].keys())

    # Карточки с историей изучения
    studied = {
        s['character']: s
        for s in db['card_study_stats'].find(
            {'user_id': request.user.id, 'category': category}
        )
    }

    due_count = sum(
        1 for char, s in studied.items()
        if char in all_chars and s.get('next_review', now) <= now
    )
    new_count = len(all_chars - set(studied.keys()))

    client.close()
    return JsonResponse({'due': due_count, 'new_count': new_count})


@login_required
def study_session_start(request, category, count):
    """Формирует список карточек для сессии и рендерит страницу изучения."""
    if category not in HSK_CHARACTERS:
        return redirect('study_select')

    count  = max(1, min(200, int(count)))
    client = MongoClient(MONGO_URI)
    db     = client['chinese_srs']
    now    = datetime.datetime.now()

    all_chars = get_ordered_chars(category)

    # Загружаем статистику пользователя по этой категории
    all_stats = {
        s['character']: s
        for s in db['card_study_stats'].find(
            {'user_id': request.user.id, 'category': category}
        )
    }
    client.close()

    # 1. Карточки, срок повторения которых наступил
    due_cards = [
        char for char in all_chars
        if char in all_stats
        and all_stats[char].get('next_review', now) <= now
    ]
    due_cards.sort(key=lambda c: all_stats[c].get('next_review', now))

    # 2. Новые карточки (ещё никогда не изучались)
    NEW_PER_SESSION = 10
    new_cards = [char for char in all_chars if char not in all_stats]
    new_cards = new_cards[:NEW_PER_SESSION]

    # Объединяем: сначала просроченные, затем новые
    session_chars = (due_cards + new_cards)[:count]

    cards_data = [
        {
            'character': char,
            'pinyin':    HSK_CHARACTERS[category][char]['pinyin'],
            'meaning':   HSK_CHARACTERS[category][char]['meaning'],
            'is_new':    char not in all_stats,
            'n':         all_stats.get(char, {}).get('n', 0),
        }
        for char in session_chars
    ]

    return render(request, 'study_session.html', {
        'cards_json': json.dumps(cards_data, ensure_ascii=False),
        'category':   category,
        'count':      len(cards_data),
    })


@login_required
@csrf_exempt
def study_answer(request):
    """
    AJAX POST: принимает оценку пользователя и обновляет параметры SM-2
    в коллекции card_study_stats.

    Тело запроса (JSON):
        character — иероглиф
        category  — HSK1 / HSK2 / HSK3
        quality   — 0 (не знаю) | 3 (с трудом) | 5 (легко)
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        data      = json.loads(request.body)
        character = data['character']
        category  = data.get('category', 'HSK1')
        quality   = int(data['quality'])

        if quality not in (0, 1, 2, 3, 4, 5):
            quality = max(0, min(5, quality))
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    client = MongoClient(MONGO_URI)
    db     = client['chinese_srs']

    # Находим или создаём запись статистики
    stats = db['card_study_stats'].find_one({
        'user_id':   request.user.id,
        'character': character,
        'category':  category,
    }) or {
        'ef':            2.5,
        'n':             0,
        'interval':      1,
        'correct_count': 0,
        'total_count':   0,
    }

    ef, n, interval, next_review = _sm2_update(stats, quality)

    correct_count = stats.get('correct_count', 0) + (1 if quality >= 3 else 0)
    total_count   = stats.get('total_count',   0) + 1

    db['card_study_stats'].update_one(
        {'user_id': request.user.id, 'character': character, 'category': category},
        {'$set': {
            'ef':            ef,
            'n':             n,
            'interval':      interval,
            'next_review':   next_review,
            'correct_count': correct_count,
            'total_count':   total_count,
            'updated_at':    datetime.datetime.now(),
        }},
        upsert=True
    )
    client.close()

    return JsonResponse({
        'status':      'success',
        'interval':    interval,
        'next_review': next_review.strftime('%Y-%m-%d'),
        'ef':          ef,
        'n':           n,
    })
