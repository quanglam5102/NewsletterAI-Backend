from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from openai import OpenAI
from django.conf import settings

from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import csrf_exempt
import json
from rest_framework_simplejwt.tokens import RefreshToken

def select_lines(text, start_index, end_index):
    lines = text.split('\n')
    selected_lines = lines[start_index:end_index + 1]
    return "\n".join(selected_lines)

def get_text_from_url(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        text = soup.get_text(separator='\n', strip=True)
        return True, text
    else:
        return False, f"Error: Unable to fetch the page. Status code: {response.status_code}"

def filter_recent_news(text):
    lines = text.split('\n')
    current_date = datetime.now()
    current_month = current_date.month
    previous_month = (current_date.month - 1) or 12
    current_year = current_date.year
    previous_year = current_year - 1 if previous_month == 12 else current_year

    recent_news = []
    for i in range(len(lines)):
        try:
            date = datetime.strptime(lines[i], "%B %d, %Y")
            if (date.month == current_month and date.year == current_year) or \
               (date.month == previous_month and date.year == previous_year):
                recent_news.append(lines[i])
                recent_news.append(lines[i + 1])
        except ValueError:
            continue

    return "\n".join(recent_news)

# Function to interact with GPT-4 API
def get_gpt_response(website_text):
    prompt = f"Below is the website data about Vinfast company: {website_text}\n\n---\n\nGiven the context above, write me a 1000-word newsletter summarizing all that information, excluding the salutation (e.g., 'Dear [Recipient's Name]') and the signature block (e.g., 'Best Regards,' '[Your Name]', and '[Your Position]'). Focus only on the subject and main body content and select only positive information about the company."

    client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
    )

    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model="gpt-4o",
    )
    print(chat_completion.choices[0].message.content)
    return chat_completion.choices[0].message.content

# API View
# @api_view(['GET'])
# def recent_news_view(request):
#     url = 'https://vinfastauto.us/investor-relations/news'
#     success, page_text = get_text_from_url(url)

#     if success:
#         selected_text = select_lines(page_text, 10, 518)
#         recent_news = filter_recent_news(selected_text)
        
#         if not recent_news:
#             return Response({"error": "No recent news found."}, status=status.HTTP_404_NOT_FOUND)

#         gpt_response = get_gpt_response(recent_news)

#         if "Error:" in gpt_response:
#             return Response({"error": gpt_response}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#         return Response({"newsletter": gpt_response}, status=status.HTTP_200_OK)
#     else:
#         return Response({"error": page_text}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def get_text_from_urls(urls):
    """Fetch text from multiple URLs."""
    results = {}
    for url in urls:
        success, page_text = get_text_from_url(url)
        if success:
            results[url] = page_text
        else:
            results[url] = None  # Indicate failure for this URL
    return results

@api_view(['GET'])
def recent_news_view(request):
    urls = [
        'https://vinfastauto.us/investor-relations/news',
        'https://www.reddit.com/r/VinFastCommunity/',
        'https://community.vinfastauto.us/forums/topic/discussions/'
    ]
    
    fetched_data = get_text_from_urls(urls)
    all_text = []

    for url, page_text in fetched_data.items():
        if page_text is None:
            continue
        all_text.append(page_text)
    
    if not all_text:
        return Response({"error": "No content found from the provided URLs."}, status=status.HTTP_404_NOT_FOUND)
    
    concatenated_text = "\n\n---\n\n".join(all_text)
    return Response({"newsletter": concatenated_text}, status=status.HTTP_200_OK)


# Test View to say Hello World
def hello_world(request):
    return JsonResponse({"message": "Hello, World!"})

class ChatbotView(APIView):
    def post(self, request, *args, **kwargs):
        # Get the message from the request body
        user_message = request.data.get('message')

        # Check if the message is provided
        if not user_message:
            return Response({"error": "No message provided."}, status=status.HTTP_400_BAD_REQUEST)

        client = OpenAI(
        api_key=settings.OPENAI_API_KEY,)

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": user_message,
                }
            ],
            model="gpt-4o",
        )
        content = chat_completion.choices[0].message.content
        return Response({"response": content}, status=status.HTTP_200_OK)
    
# Managing Users
@csrf_exempt
def register_user(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')

            if User.objects.filter(username=username).exists():
                return JsonResponse({'success': False, 'message': 'Username already exists'}, status=400)

            user = User.objects.create_user(username=username, password=password)
            return JsonResponse({'success': True, 'message': 'User registered successfully'}, status=201)

        except KeyError as e:
            return JsonResponse({'success': False, 'message': f'Missing field: {str(e)}'}, status=400)

        except Exception as e:
            return JsonResponse({'success': False, 'message': f'An error occurred: {str(e)}'}, status=500)

@csrf_exempt
def login_user(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')

            # Authenticate user
            user = authenticate(username=username, password=password)
            if user is not None:
                # Login user
                login(request, user)

                # Generate JWT token
                refresh = RefreshToken.for_user(user)
                token = str(refresh.access_token)

                # Respond with success, token, and user info
                return JsonResponse({
                    'success': True,
                    'token': token,
                    'user': {
                        'username': user.username,
                        'email': user.email
                    }
                }, status=200)

            # Invalid credentials
            return JsonResponse({'success': False, 'message': 'Invalid username or password'}, status=401)

        except KeyError as e:
            return JsonResponse({'success': False, 'message': f'Missing field: {str(e)}'}, status=400)

        except Exception as e:
            return JsonResponse({'success': False, 'message': f'An error occurred: {str(e)}'}, status=500)
