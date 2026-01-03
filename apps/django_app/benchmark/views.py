import random
from django.http import JsonResponse
from django.db.models import Prefetch
from .models import Post, Comment

NUM_POSTS = 50_000

def db_test(request):
    post_id = random.randint(1, NUM_POSTS)
    
    # Django ORM efficient fetching:
    # 1. Post + User (JOIN)
    # 2. Comments + User (JOIN in 2nd query)
    try:
        post = Post.objects.select_related('user').prefetch_related(
            Prefetch('comments', queryset=Comment.objects.select_related('user'))
        ).get(id=post_id)
    except Post.DoesNotExist:
         return JsonResponse({"error": "Post not found"}, status=404)
         
    return JsonResponse({
        "post_id": post.id,
        "title": post.title,
        "author": post.user.username,
        "last_updated": post.created_at.isoformat(),
        "comments": [
            {"user": c.user.username, "content": c.content} 
            for c in post.comments.all()
        ]
    })
