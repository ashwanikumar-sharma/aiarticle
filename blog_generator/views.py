from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import json
from pytube import YouTube
import os
import assemblyai as aai
import http.client
import logging
from .models import BlogPost

# Configure logging
logger = logging.getLogger(__name__)

# Create your views here.
@login_required
def index(request):
    return render(request, 'index.html')

@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            yt_link = data['link']
        except (KeyError, json.JSONDecodeError):
            return JsonResponse({'error': 'Invalid data sent'}, status=400)

        # Get YouTube title
        try:
            title = yt_title(yt_link)
        except Exception as e:
            logger.error(f"Error fetching YouTube title: {e}")
            return JsonResponse({'error': "Failed to fetch YouTube title"}, status=500)

        # Get transcript
        try:
            transcription = get_transcription(yt_link)
            if not transcription:
                return JsonResponse({'error': "Failed to get transcript"}, status=500)
        except Exception as e:
            logger.error(f"Error fetching transcript: {e}")
            return JsonResponse({'error': "Failed to fetch transcript"}, status=500)

        # Use OpenAI to generate the blog
        try:
            blog_content = generate_blog_from_transcription(transcription)
            if not blog_content:
                return JsonResponse({'error': "Failed to generate blog article"}, status=500)
            new_blog_article = BlogPost.objects.create(
                user = request.user,
                youtube_title = title,
                youtube_link = yt_link,
                generated_content = blog_content,

            )
            new_blog_article.save()
        except Exception as e:
            logger.error(f"Error generating blog: {e}")
            return JsonResponse({'error': "Failed to generate blog article"}, status=500)

        # Return blog article as a response
        return JsonResponse({'content': blog_content})
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

def yt_title(link):
    yt = YouTube(link)
    return yt.title

def download_audio(link):
    yt = YouTube(link)
    video = yt.streams.filter(only_audio=True).first()
    out_file = video.download(output_path=settings.MEDIA_ROOT)
    base, ext = os.path.splitext(out_file)
    new_file = base + '.mp3'
    os.rename(out_file, new_file)
    return new_file

def get_transcription(link):
    audio_file = download_audio(link)
    aai.settings.api_key = "6bea7aa5c4664ca0936de0b685f86782"

    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_file)

    return transcript.text

def generate_blog_from_transcription(transcription):
    conn = http.client.HTTPSConnection("chatgpt-42.p.rapidapi.com")

    prompt = f"Summarize this YouTube video transcript in form of comprehensible blog article.Summarize with in 100 words \n\n{transcription}\n\nArticle:"

    payload = json.dumps({
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "system_prompt": "",
        "temperature": 0.9,
        "top_k": 5,
        "top_p": 0.9,
        "max_tokens": 500,
        "web_access": False
    })

    headers = {
        'x-rapidapi-key': "f47d9da8bemshda3eca3cdbe3d8ep185b22jsnc067a5f4c4df",  # Your actual API key
        'x-rapidapi-host': "chatgpt-42.p.rapidapi.com",
        'Content-Type': "application/json"
    }

    conn.request("POST", "/conversationgpt4-2", payload, headers)

    res = conn.getresponse()
    data = res.read()

    response_json = json.loads(data.decode("utf-8"))

    # Extracting the generated content from the 'result' field of the response
    generated_content = response_json['result']

    return generated_content

def blog_list ( request):
    blog_articles = BlogPost.objects.filter(user = request.user)
    return render (request,'all-blogs.html' , {'blog_articles': blog_articles})
def blog_details(request,pk):
    blog_article_detail = BlogPost.objects.get(id=pk)
    if(request.user == blog_article_detail.user):
        return render(request, 'blog-details.html' , {'blog_article_detail' : blog_article_detail})
    else:
        return redirect('/')


def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            error_message = "Invalid username or password"
            return render(request, 'login.html', {'error_message': error_message})

    return render(request, 'login.html')

def user_signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeatPassword = request.POST['repeatPassword']

        if password == repeatPassword:
            try:
                user = User.objects.create_user(username, email, password)
                user.save()
                login(request, user)
                return redirect('/')
            except Exception as e:
                logger.error(f"Error creating user: {e}")
                error_message = 'Error creating account'
                return render(request, 'signup.html', {'error_message': error_message})
        else:
            error_message = 'Passwords do not match'
            return render(request, 'signup.html', {'error_message': error_message})

    return render(request, 'signup.html')

def user_logout(request):
    logout(request)
    return redirect('/')
