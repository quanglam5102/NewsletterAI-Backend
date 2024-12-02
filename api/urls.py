from django.urls import path
from .views import hello_world, recent_news_view, ChatbotView, register_user, login_user

urlpatterns = [
    path('hello/', hello_world),
    path('newsletter/', recent_news_view, name='newsletter'),
    path('chatbot/', ChatbotView.as_view(), name='chatbot'),
    path('register/', register_user, name='register'),
    path('login/', login_user, name='login')
]
