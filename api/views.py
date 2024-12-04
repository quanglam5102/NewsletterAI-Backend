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

def filter_recent_news(text, selection_type):
    lines = text.split('\n')
    current_date = datetime.now()
    current_month = current_date.month
    previous_month = (current_date.month - 1) or 12
    current_year = current_date.year
    previous_year = current_year - 1 if previous_month == 12 else current_year

    recent_news = []
    
    # Iterate through the lines
    for i in range(1, len(lines) - 1):  # Start at index 1 and go up to second-to-last line
        try:
            # Attempt to parse the line using different formats
            try:
                date = datetime.strptime(lines[i], "%B %d, %Y")  # Format: Month Day, Year
            except ValueError:
                date = datetime.strptime(lines[i], "%m/%d/%Y")  # Format: MM/DD/YYYY

            # Check if the date is in the current or previous month
            if (date.month == current_month and date.year == current_year) or \
               (date.month == previous_month and date.year == previous_year):
                
                # Handle the selection type
                if selection_type == "before":
                    # Select one line before the date and the date line
                    if i > 0:  # Make sure there's a previous line
                        recent_news.append(lines[i - 1])
                    recent_news.append(lines[i])
                elif selection_type == "after":
                    # Select the date line and one line after the date
                    recent_news.append(lines[i])
                    if i + 1 < len(lines):  # Make sure there's a next line
                        recent_news.append(lines[i + 1])
                elif selection_type == "both":
                    # Select one line before, the date line, and one line after
                    if i > 0:  # Make sure there's a previous line
                        recent_news.append(lines[i - 1])
                    recent_news.append(lines[i])
                    if i + 1 < len(lines):  # Make sure there's a next line
                        recent_news.append(lines[i + 1])

        except (ValueError, IndexError):
            # Skip lines that can't be parsed as a date or are out of range
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

def get_text_from_urls(urls, start_texts, selection_types):
    """
    Fetch text from multiple URLs with customizable start texts and selection behaviors for text extraction.

    Args:
        urls (list): A list of URLs to fetch text from.
        start_texts (dict): A dictionary mapping each URL to its starting text.
        selection_types (dict): A dictionary mapping each URL to its selection behavior ('before', 'after', or 'both').

    Returns:
        dict: A dictionary mapping URLs to their fetched and selected text.
    """
    results = {}

    for url in urls:
        success, page_text = get_text_from_url(url)
        if success:
            start_text = start_texts.get(url, None)
            selection_type = selection_types.get(url, "both")
            if start_text:
                try:
                    start_index = page_text.index(start_text)
                    selected_text = page_text[start_index:]
                    results[url] = filter_recent_news(selected_text, selection_type)
                except ValueError:
                    results[url] = None
            else:
                results[url] = None
        else:
            results[url] = None

    return results

@api_view(['GET'])
def recent_news_view(request):
    urls = [
        'https://vinfastauto.us/investor-relations/news',
        'https://vinfastauto.ca/en/newsroom',
        'https://electrifynews.com/?s=vinfast'
    ]

    start_texts = {
        "https://vinfastauto.us/investor-relations/news": "News\n",
        "https://vinfastauto.ca/en/newsroom": "Director of Communications\n",
        "https://electrifynews.com/?s=vinfast": "AUTO\n"
    }

    selection_types = {
        "https://vinfastauto.us/investor-relations/news": "after",
        "https://vinfastauto.ca/en/newsroom": "both",
        "https://electrifynews.com/?s=vinfast": "before"
    }
    results = get_text_from_urls(urls, start_texts, selection_types)
    all_text = []
    for url, page_text in results.items():
        if page_text:
            all_text.append(f"Source: {url}\n\n{page_text}")
        else:
            print(f"No content found for URL: {url}")

    if not all_text: 
        return Response({"error": "No content found from the provided URLs."}, status=status.HTTP_404_NOT_FOUND)
    
    concatenated_text = "\n---\n".join(all_text)
    gpt_response = get_gpt_response(concatenated_text)

    if "Error:" in gpt_response:
        return Response({"error": gpt_response}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
        return Response({"newsletter": gpt_response}, status=status.HTTP_200_OK)

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
        
# Test View to say Hello World
def hello_world(request):
    return JsonResponse({"message": "Hello, World!"})
