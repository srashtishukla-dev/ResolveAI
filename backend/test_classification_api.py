"""Manually test the authenticated ticket classification API."""

import argparse
import getpass
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def post_json(url, payload, headers=None):
    request_headers = {'Content-Type': 'application/json'}
    if headers:
        request_headers.update(headers)
    request = Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers=request_headers,
        method='POST',
    )
    with urlopen(request) as response:
        return response.status, json.loads(response.read().decode('utf-8'))


def main():
    parser = argparse.ArgumentParser(
        description='Test ResolveAI ticket category classification.'
    )
    parser.add_argument(
        '--base-url',
        default='http://127.0.0.1:8000',
        help='Django server URL (default: http://127.0.0.1:8000)',
    )
    args = parser.parse_args()
    base_url = args.base_url.rstrip('/')

    username = input('Django username: ')
    password = getpass.getpass('Django password: ')

    try:
        _, token_response = post_json(
            f'{base_url}/api/token/',
            {'username': username, 'password': password},
        )
        del password
        access_token = token_response['access']
        _, result = post_json(
            f'{base_url}/api/ai/classify/',
            {
                'title': 'Payment failed',
                'description': 'Money was deducted but my order is still pending',
            },
            {'Authorization': 'Bearer ' + access_token},
        )
    except KeyError:
        print('Authentication failed: no access token was returned.')
        return 1
    except HTTPError as exc:
        print(f'Request failed with HTTP {exc.code}: {exc.reason}')
        return 1
    except URLError as exc:
        print(f'Could not connect to the Django server: {exc.reason}')
        return 1

    print(f"Predicted category: {result.get('predicted_category')}")
    print(f"Confidence: {result.get('confidence')}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
