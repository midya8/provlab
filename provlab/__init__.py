def analyze(request):
    from .core import analyze as implementation

    return implementation(request)
