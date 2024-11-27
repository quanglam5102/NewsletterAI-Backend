from django.urls import path
from .views import hello_world, recent_news_view, ChatbotView

urlpatterns = [
    path('hello/', hello_world),
    path('newsletter/', recent_news_view, name='newsletter'),
    path('chatbot/', ChatbotView.as_view(), name='chatbot'),
]
