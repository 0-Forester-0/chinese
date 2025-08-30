# from django.db import models
# from django.contrib.auth.models import User
# from djongo.models import JSONField

# class Card(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     character = models.CharField(max_length=10)
#     pinyin = models.CharField(max_length=50)
#     meaning = models.CharField(max_length=100)
#     category = models.CharField(max_length=50, default='HSK1')
#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"{self.character} ({self.pinyin})"

# class Collection(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     name = models.CharField(max_length=100)
#     category = models.CharField(max_length=50, default='HSK1')
#     cards = JSONField(default=list)
#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return self.name

# class GameSession(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     category = models.CharField(max_length=50, default='HSK1')
#     correct_answers = models.IntegerField(default=0)
#     total_answers = models.IntegerField(default=0)
#     percentage = models.FloatField(default=0.0)
#     remaining_cards = JSONField(default=list)
#     answer_history = JSONField(default=dict)  # Хранит {character: {'correct': int, 'total': int}}
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     def __str__(self):
#         return f"GameSession {self.category} for {self.user.username} ({self.percentage}%)"


from django.db import models
from django.contrib.auth.models import User
from djongo.models import JSONField

class Card(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    character = models.CharField(max_length=10)
    pinyin = models.CharField(max_length=50)
    meaning = models.CharField(max_length=100)
    category = models.CharField(max_length=50, default='HSK1')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.character} ({self.pinyin})"

class Collection(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, default='HSK1')
    cards = JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class GameSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.CharField(max_length=50, default='HSK1')
    correct_answers = models.IntegerField(default=0)
    total_answers = models.IntegerField(default=0)
    percentage = models.FloatField(default=0.0)
    remaining_cards = JSONField(default=list)
    answer_history = JSONField(default=dict)  # Хранит {character: {'correct': int, 'total': int}}
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"GameSession {self.category} for {self.user.username} ({self.percentage}%)"
