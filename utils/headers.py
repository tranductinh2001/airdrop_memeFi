# utils/headers.py

import random

def get_random_accept():
    accept_options = [
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "application/json, text/javascript, */*; q=0.01",
        "text/plain, */*; q=0.01"
    ]
    return random.choice(accept_options)

def get_random_accept_language():
    accept_language_options = [
        "en-US,en;q=0.9",
        "vi-VN,vi;q=0.9,fr-FR;q=0.8,fr;q=0.7,en-US;q=0.6,en;q=0.5",
        "en-GB,en;q=0.9,en-US;q=0.8,vi;q=0.7"
    ]
    return random.choice(accept_language_options)

def get_random_referer():
    referer_options = [
        "https://www.google.com/",
        "https://www.facebook.com/",
        "https://tg-app.memefi.club/"
    ]
    return random.choice(referer_options)

def get_random_sec_fetch_site():
    sec_fetch_site_options = [
        "same-origin",
        "same-site",
        "cross-site"
    ]
    return random.choice(sec_fetch_site_options)

def get_random_headers(user_agent):
    headers = {
        'Accept': get_random_accept(),
        'Accept-Language': get_random_accept_language(),
        'Content-Language': 'en-GB',
        'Content-Type': 'application/json',
        'Origin': 'https://tg-app.memefi.club',
        'Referer': get_random_referer(),
        'Sec-Ch-Ua': '"Not/A)Brand";v="99", "Google Chrome";v="115", "Chromium";v="115"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': get_random_sec_fetch_site(),
        'User-Agent': user_agent
    }
    return headers
