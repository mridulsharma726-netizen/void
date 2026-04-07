import requests

def is_internet_on():
    """Check if internet is available by making a fast request."""
    try:
        requests.get("http://www.google.com", timeout=3)
        return True
    except requests.RequestException:
        return False
