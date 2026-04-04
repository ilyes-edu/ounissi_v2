from django.contrib.auth.decorators import login_required
from functools import wraps
from .utils import getLoggedData


def with_logged_data(func):
    @wraps(func)
    @login_required
    def wrapper(request, *args, **kwargs):
        logged_data = getLoggedData(request)
        response = func(request, *args, **kwargs)

        if isinstance(response, dict):  # If view returns a context dictionary
            response.update(logged_data=logged_data)
        elif isinstance(response, tuple) and len(response) == 2:  # If view returns a template and context tuple
            template, context = response
            context.update(logged_data=logged_data)
            response = (template, context)
        elif hasattr(response, 'context_data'):  # If response is a rendered template
            response.context_data.update(logged_data=logged_data)

        return response

    return wrapper
