def base_context_processor(request):
    return {
        'BASE_URL': request.build_absolute_uri("/").rstrip("/")
    }
