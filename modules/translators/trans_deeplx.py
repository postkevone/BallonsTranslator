"""
Modified From PyDeepLX

Author: Vincent Young
Date: 2023-04-27 00:44:01
LastEditors: Vincent Young
LastEditTime: 2023-05-21 03:58:18
FilePath: /PyDeepLX/PyDeepLX/PyDeepLX.py
Telegram: https://t.me/missuo

Copyright © 2023 by Vincent, All Rights Reserved.

MIT License

Copyright (c) 2023 OwO Network Limited

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from .base import *
# import signal

# class TimeoutException(Exception):
#     pass

# def timeout_handler(signum, frame):
#     raise TimeoutException("Timed out!")

import random
import time
import json
import httpx
from langdetect import detect
import brotli
import gzip  # Import gzip module for handling gzip compression
import re

from utils.logger import logger as LOGGER


deeplAPI_base = "https://www2.deepl.com/jsonrpc" # Base URL for DeepL API
deepl_client_params = "client=chrome-extension,1.28.0" # Client parameters as used in Chrome extension v1.28.0
headers = {  # Headers, simplified and aligned with deepx.py
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.9',  # Simplified Accept-Language like in deepx.py
    'Accept-Encoding': 'gzip, deflate, br',  # Accept-Encoding added as in deepx.py
    'Authorization': 'None',
    'Cache-Control': 'no-cache',
    'Content-Type': 'application/json',
    'DNT': '1',
    'Origin': 'chrome-extension://cofdbpoegempjloogbagkncekinflcnj',
    'Pragma': 'no-cache',
    'Priority': 'u=1, i',
    'Referer': 'https://www.deepl.com/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'none',
    'Sec-GPC': '1',
    'User-Agent': 'DeepLBrowserExtension/1.28.0 Mozilla/5.0 (Windows NT 10.0; Win64; x64)',  # User-Agent like in deepx.py
}


class TooManyRequestsException(Exception):
    "Raised when there is a 429 error"

    def __str__(self):
        return "Error: Too many requests, your IP has been blocked by DeepL temporarily, please don't request it frequently in a short time."


def detectLang(translateText) -> str:
    """Detects the language of the text using langdetect."""
    try: #  Error handling for cases when langdetect cannot determine the language
        language = detect(translateText)
        return language.upper()
    except:
        return "EN" # Default language or alternative error handling


def getICount(translateText) -> int:
    """Counts the number of 'i' characters in the text, used in DeepL request."""
    return translateText.count("i")


def getRandomNumber() -> int:
    """Generates a random number used as request ID, similar to deepx.py."""
    src = random.Random(time.time()) # Random initialization as in deepx.py
    num = src.randint(8300000, 8399999) # Range as in deepx.py
    return num * 1000


def getTimestamp(iCount: int) -> int:
    """Generates a timestamp used in DeepL request, based on 'i' count."""
    ts = int(time.time() * 1000)

    if iCount == 0:
        return ts

    iCount += 1
    return ts - ts % iCount + iCount

def format_post_data(post_data_dict, id_val):
    """Formats post data string with specific spacing for 'method' key."""
    post_data_str = json.dumps(post_data_dict, ensure_ascii=False)
    if (id_val + 5) % 29 == 0 or (id_val + 3) % 13 == 0:
        post_data_str = post_data_str.replace('"method":"', '"method" : "', 1) # Replace only once
    else:
        post_data_str = post_data_str.replace('"method":"', '"method": "', 1) # Replace only once
    return post_data_str

def is_richtext(text: str) -> bool:
    """Checks if the text contains HTML-like tags."""
    return bool(re.search(r'<[^>]+>', text))

def deepl_split_text(text: str, tag_handling: bool = None, proxies=None) -> dict:
    """Sends request to DeepL API to split text before translation."""
    source_lang = 'auto'
    text_type = 'richtext' if (tag_handling or is_richtext(text)) else 'plaintext' # Uses is_richtext and tag_handling
    postData = {
        "jsonrpc": "2.0",
        "method": "LMT_split_text",
        "params": {
            "commonJobParams": {
                "mode": "translate"
            },
            "lang": {
                "lang_user_selected": source_lang
            },
            "texts": [text],
            "textType": text_type
        },
        "id": getRandomNumber()
    }
    postDataStr = format_post_data(postData, getRandomNumber()) # Uses getRandomNumber for ID
    url = f"{deeplAPI_base}?{deepl_client_params}&method=LMT_split_text" # URL as in deepx.py
    return make_deepl_request(url, postDataStr, proxies)


def make_deepl_request(url, postDataStr, proxies):
    """Makes a request to DeepL API, handles proxies, decompression, and errors."""
    client = httpx.Client(headers=headers, proxy=proxies, timeout=30) # Proxy setup as in deepx.py, timeout added
    try:
        resp = client.post(url=url, content=postDataStr) # Sends content instead of data
        if not resp.is_success: # Checks resp.is_success instead of respStatusCode
            return {'error': resp.text} # Returns error dict as in deepx.py
        try:
            return resp.json() # Tries to parse JSON
        except json.JSONDecodeError: # Handles JSONDecodeError
            try:  # Attempts gzip decompression if brotli fails, as in deepx.py
                return json.loads(gzip.decompress(resp.content))
            except Exception:
                try:
                    return resp.json()  # Tries to parse JSON again (in case it's not gzip)
                except:
                    try:
                        return json.loads(brotli.decompress(resp.content)) # Brotli decompression as in deepx.py
                    except Exception as e:
                        LOGGER.error(f"Decompression error: {e}, content: {resp.content[:100]}") # Logs decompression error
                        return {'error': 'Failed to decompress response'} # Returns decompression error

    except httpx.HTTPError as e: # Catches httpx errors (timeouts, connection errors, etc.)
        LOGGER.error(f"HTTPError: {e}") # Logs HTTP errors
        LOGGER.error(f"Request URL: {url}") # Logs request URL
        LOGGER.error(f"Request Data: {postDataStr}") # Logs request data
        return {'error': str(e)} # Returns error dict for httpx errors


def deepl_response_to_deeplx(data: dict) -> dict:
    """Transforms DeepL API response to DeepLX format, including alternatives."""
    alternatives = []
    if 'result' in data and 'translations' in data['result'] and len(data['result']['translations']) > 0:
        num_beams = len(data['result']['translations'][0].get('beams', []))
        for i in range(num_beams):
            alternative_str = ""
            for translation in data['result']['translations']:
                beams = translation.get('beams', [])
                if i < len(beams):
                    sentences = beams[i].get('sentences', [])
                    if sentences:
                        alternative_str += sentences[0].get('text', '')
                alternatives.append(alternative_str)
    source_lang = data.get('result', {}).get('source_lang', 'unknown')
    target_lang = data.get('result', {}).get('target_lang', 'unknown')
    main_translation = " ".join(
        translation.get('beams', [{}])[0].get('sentences', [{}])[0].get('text', '')
        for translation in data.get('result', {}).get('translations', [])
    )
    return {
        "alternatives": alternatives,
        "code": 200,
        "data": main_translation,
        "id": data.get('id', None),
        "method": "Free",
        "source_lang": source_lang,
        "target_lang": target_lang
    }


def translate_core(
    text,
    sourceLang,
    targetLang,
    tagHandling,
    dl_session = "", # dl_session for Pro API, not used in this free version
    proxies=None,
):
    """Core translation function, orchestrates split text and handle jobs requests."""
    if not text:
        return {"code": 404, "message": "No text to translate"}

    split_result_json = deepl_split_text(text, tagHandling in ("html", "xml"), proxies) # tag_handling_bool is calculated here, using deepl_split_text
    if 'error' in split_result_json: # Error check from deepl_split_text
        return {"code": 503, "message": split_result_json['error']} # 503 Service Unavailable, returns error message

    if sourceLang == "auto" or not sourceLang: # Language detection if sourceLang is auto or not provided
        sourceLang_detected = split_result_json.get("result", {}).get("lang", {}).get("detected")
        if sourceLang_detected:
            sourceLang = sourceLang_detected.lower() # tolower() as in deepx.py
        else:
            sourceLang = detectLang(text).lower() # tolower() and fallback to langdetect

    i_count = getICount(text) # getICount

    jobs = []
    try: # try-except for accessing chunks as in deepx.py
        chunks = split_result_json['result']['texts'][0]['chunks']
    except (KeyError, IndexError, TypeError): # TypeError added for robustness
        return {'code': 503, 'message': 'Unexpected response structure from split_text'} # Returns error if split_text response structure is incorrect

    for idx, chunk in enumerate(chunks):
        sentence = chunk['sentences'][0] # sentence as in deepx.py
        context_before = [chunks[idx-1]['sentences'][0]['text']] if idx > 0 else [] # context_before as in deepx.py
        context_after = [chunks[idx+1]['sentences'][0]['text']] if idx < len(chunks) - 1 else [] # context_after as in deepx.py

        jobs.append({ # job as in deepx.py
            "kind": "default",
            "preferred_num_beams": 4, # preferred_num_beams = 4 as in deepx.py
            "raw_en_context_before": context_before,
            "raw_en_context_after": context_after,
            "sentences": [{
                "prefix": sentence['prefix'],
                "text": sentence['text'],
                "id": idx + 1
            }]
        })


    targetLang_code = targetLang.upper() # targetLang_code to upper
    postData = { # postData for LMT_handle_jobs as in deepx.py
        "jsonrpc": "2.0",
        "method": "LMT_handle_jobs",
        "id": getRandomNumber(), # getRandomNumber for ID
        "params": {
            "commonJobParams": {
                "mode": "translate"
            },
            "lang": {
                "source_lang_computed": sourceLang.upper(), # sourceLang to upper
                "target_lang": targetLang_code # targetLang_code (upper)
            },
            "jobs": jobs,
            "priority": 1,
            "timestamp": getTimestamp(i_count) # timestamp
        }
    }


    postDataStr = format_post_data(postData, getRandomNumber()) # format_post_data, getRandomNumber for ID
    url = f"{deeplAPI_base}?{deepl_client_params}&method=LMT_handle_jobs" # URL for LMT_handle_jobs
    translate_result_json = make_deepl_request(url, postDataStr, proxies) # make_deepl_request

    if 'error' in translate_result_json: # Error check from make_deepl_request
        return {"code": 503, "message": translate_result_json['error']} # Returns error if there is an error

    deeplx_result = deepl_response_to_deeplx(translate_result_json) # Transforms response using deepl_response_to_deeplx
    return deeplx_result # Returns result in DeepLX format


def translate(
    text,
    sourceLang=None,
    targetLang=None,
    numberAlternative=0, # numberAlternative is not used, same as in deepx.py
    printResult=False,
    proxies=None,
):
    """Main translate function, calls core translation and handles output."""
    tagHandling = False # tagHandling default False, as in deepx.py (can be made a parameter if needed)

    result_json = translate_core(text, sourceLang, targetLang, tagHandling, proxies=proxies) # Calls translate_core

    if result_json and result_json["code"] == 200: # Checks for code 200
        if printResult:
            print(result_json["data"]) # Prints main translation
        return result_json["data"] # Returns only main translation
    else:
        error_message = result_json.get("message", "Unknown error") if result_json else "Request failed" # Error message
        LOGGER.error(f"Translation error: {error_message}") # Logs error
        raise Exception(f"Translation failed: {error_message}") # Raises exception


@register_translator('DeepL Free')
class DeepLX(BaseTranslator):
    """DeepL Free Translator class, implements BaseTranslator interface."""
    cht_require_convert = True
    params: Dict = {
        'delay': 0.0,
        'proxy': { # Proxy parameter definition, similar to ocr_google_lens.py
            'value': '',
            'description': 'Proxy address (e.g., http(s)://user:password@host:port or socks4/5://user:password@host:port)'
        },
    }
    concate_text = True

    def _setup_translator(self):
        """Sets up language map for DeepL Free translator."""
        self.lang_map = { # lang_map including '繁體中文'
            '简体中文': 'zh',
            '日本語': 'ja',
            'English': 'en',
            'Français': 'fr',
            'Deutsch': 'de',
            'Italiano': 'it',
            'Português': 'pt',
            'Brazilian Portuguese': 'pt-br',
            'русский язык': 'ru',
            'Español': 'es',
            'български език': 'bg',
            'Český Jazyk': 'cs',
            'Dansk': 'da',
            'Ελληνικά': 'el',
            'Eesti': 'et',
            'Suomi': 'fi',
            'Magyar': 'hu',
            'Lietuvių': 'lt',
            'latviešu': 'lv',
            'Nederlands': 'nl',
            'Polski': 'pl',
            'Română': 'ro',
            'Slovenčina': 'sk',
            'Slovenščina': 'sl',
            'Svenska': 'sv',
            'Indonesia': 'id',
            'украї́нська мо́ва': 'uk',
            '한국어': 'ko',
            'Arabic': 'ar',
            '繁體中文': 'zh-TW', # Added '繁體中文' and language code 'zh-TW'
        }
        self.textblk_break = '\n'

    def __init__(self, source='auto', target='en', raise_unsupported_lang=True, **params):
        """Initializes DeepLX translator, including proxy setup."""
        self.proxy = params.get('proxy', {}).get('value') # Get proxy URL string from params
        super().__init__(source, target, raise_unsupported_lang=raise_unsupported_lang)


    def _translate(self, src_list: List[str]) -> List[str]:
        """Translates a list of strings using DeepL Free API."""
        result = []
        source = self.lang_map[self.lang_source]
        target = self.lang_map[self.lang_target]
        proxies = self.proxy # Get proxy from self.proxy for use in translate function

        for t in src_list:
            try: # try-except block for handling translation errors for individual text blocks
                tl = translate(t, source, target, proxies=proxies) # Pass proxy to translate function
                result.append(tl)
            except Exception as e: # Catches exceptions from translate function
                LOGGER.error(f"Translation failed for text: '{t}'. Error: {e}") # Logs error
                result.append(None) # Appends None in case of error

        return result
