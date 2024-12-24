# meme.py

import asyncio
import json
import random
import string
import time
from datetime import datetime
from urllib.parse import unquote
import cloudscraper
import aiohttp  # Thêm aiohttp cho các yêu cầu async
from utils.headers import get_random_headers  # Import hàm mới từ headers.py
from utils.query import (
    QUERY_USER, QUERY_LOGIN, MUTATION_GAME_PROCESS_TAPS_BATCH,
    QUERY_BOOSTER, QUERY_NEXT_BOSS, QUERY_TASK_VERIF,
    QUERY_TASK_COMPLETED, QUERY_GET_TASK, QUERY_TASK_ID, QUERY_GAME_CONFIG
)

url = "https://api-gw-tg.memefi.club/graphql"

# ANSI color codes
black = "\033[0;30m"
red = "\033[0;31m"
green = "\033[0;32m"
yellow = "\033[0;33m"
blue = "\033[0;34m"
magenta = "\033[0;35m"
cyan = "\033[0;36m"
white = "\033[0;37m"
reset = "\033[0m"

def log(msg, color=white, account_info=""):
    now = datetime.now().isoformat(" ").split(".")[0]
    if account_info:
        print(f"{black}[{now}]{reset} [{account_info}] {color}{msg}{reset}")
    else:
        print(f"{black}[{now}]{reset} {color}{msg}{reset}")

def log2(message, color):
    print(f"{color}{message}\033[0m", end="\r")

def generate_random_nonce(length=52):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def format_proxy(proxy):
    """
    Chuyển đổi định dạng proxy từ ip:port:username:password sang http://username:password@ip:port
    Nếu proxy không có username và password, chỉ chuyển sang http://ip:port
    """
    parts = proxy.split(':')
    if len(parts) == 4:
        ip, port, username, password = parts
        return f"http://{username}:{password}@{ip}:{port}"
    elif len(parts) == 2:
        ip, port = parts
        return f"http://{ip}:{port}"
    else:
        log("❌ Định dạng proxy không hợp lệ!", red)
        return None

class ProxyManager:
    def __init__(self, proxy_file):
        self.proxy_file = proxy_file
        self.all_proxies = self.load_proxies()
        self.valid_proxies = []
        self.lock = asyncio.Lock()  # Đảm bảo an toàn khi truy cập proxy trong môi trường bất đồng bộ

    def load_proxies(self):
        try:
            with open(self.proxy_file, 'r') as file:
                proxies = [line.strip() for line in file if line.strip()]
            if not proxies:
                log("❌ Danh sách proxy trống!", red)
            return proxies
        except FileNotFoundError:
            log(f"❌ Không tìm thấy file proxy: {self.proxy_file}", red)
            return []

    async def get_random_proxy(self):
        async with self.lock:
            if not self.valid_proxies:
                log("❌ Không còn proxy nào khả dụng!", red)
                return None
            return random.choice(self.valid_proxies)

    async def mark_bad_proxy(self, proxy, account_info=""):
        async with self.lock:
            if proxy in self.valid_proxies:
                self.valid_proxies.remove(proxy)
                log(f"🔴 Proxy bị loại bỏ: {proxy}", red, account_info)
                if not self.valid_proxies:
                    log("❌ Tất cả proxy đều không hoạt động!", red, account_info)

    async def validate_proxies(self):
        """
        Kiểm tra tất cả các proxy và chỉ giữ lại những proxy hợp lệ.
        """
        log("🔍 Bắt đầu kiểm tra các proxy...", cyan)
        tasks = [self.check_proxy(proxy) for proxy in self.all_proxies]
        results = await asyncio.gather(*tasks)
        self.valid_proxies = [proxy for proxy, is_valid in zip(self.all_proxies, results) if is_valid]
        invalid_proxies = [proxy for proxy, is_valid in zip(self.all_proxies, results) if not is_valid]
        for proxy in invalid_proxies:
            log(f"❌ Proxy không hợp lệ: {proxy}", red)
        log(f"✅ Hoàn tất kiểm tra proxy. Số proxy hợp lệ: {len(self.valid_proxies)}", green)
        if not self.valid_proxies:
            log("❌ Không có proxy nào hợp lệ sau khi kiểm tra!", red)

    async def check_proxy(self, proxy):
        """
        Kiểm tra xem proxy có hoạt động không bằng cách kiểm tra IP.
        """
        formatted_proxy = format_proxy(proxy)
        if not formatted_proxy:
            return False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('http://ip-api.com/json', proxy=formatted_proxy, timeout=10) as response:
                    if response.status != 200:
                        return False
                    ip_info = await response.json()
                    return ip_info.get('status') == 'success'
        except Exception:
            return False

async def fetch(account_line, proxy_manager, account_info="", user_agent=""):
    max_retries = 3
    for attempt in range(max_retries):
        proxy = await proxy_manager.get_random_proxy()
        if not proxy:
            log("❌ Không có proxy nào khả dụng để sử dụng.", red, account_info)
            return None

        formatted_proxy = format_proxy(proxy)
        if not formatted_proxy:
            log("❌ Định dạng proxy không hợp lệ sau khi chuyển đổi!", red, account_info)
            await proxy_manager.mark_bad_proxy(proxy, account_info)
            continue

        try:
            with open('data.txt', 'r') as file:
                lines = file.readlines()
                raw_data = lines[account_line - 1].strip()

            tg_web_data = unquote(unquote(raw_data))
            query_id = tg_web_data.split('query_id=', maxsplit=1)[1].split('&user', maxsplit=1)[0]
            user_data = tg_web_data.split('user=', maxsplit=1)[1].split('&auth_date', maxsplit=1)[0]
            auth_date = tg_web_data.split('auth_date=', maxsplit=1)[1].split('&hash', maxsplit=1)[0]
            hash_ = tg_web_data.split('hash=', maxsplit=1)[1].split('&', maxsplit=1)[0]

            user_data_dict = json.loads(unquote(user_data))

            data = {
                "operationName": "MutationTelegramUserLogin",
                "variables": {
                    "webAppData": {
                        "auth_date": int(auth_date),
                        "hash": hash_,
                        "query_id": query_id,
                        "checkDataString": f"auth_date={auth_date}\nquery_id={query_id}\nuser={unquote(user_data)}",
                        "user": {
                            "id": user_data_dict["id"],
                            "allows_write_to_pm": user_data_dict["allows_write_to_pm"],
                            "first_name": user_data_dict["first_name"],
                            "last_name": user_data_dict["last_name"],
                            "username": user_data_dict.get("username", "Username không được đặt"),
                            "language_code": user_data_dict["language_code"],
                            "version": "7.2",
                            "platform": "ios"
                        }
                    }
                },
                "query": QUERY_LOGIN
            }

            # Sử dụng cloudscraper với proxy đã định dạng
            scraper = cloudscraper.create_scraper()
            proxies = {
                "http": formatted_proxy,
                "https": formatted_proxy
            }
            # Lấy headers ngẫu nhiên với User-Agent tương ứng
            headers = get_random_headers(user_agent)

            # Sử dụng asyncio.to_thread để chạy các lệnh đồng bộ trong luồng riêng
            response = await asyncio.to_thread(scraper.post, url, headers=headers, json=data, proxies=proxies)
            json_response = response.json()

            if 'errors' in json_response:
                log("Có lỗi trong phản hồi. Đang thử lại...", yellow, account_info)
            else:
                access_token = json_response['data']['telegramUserLogin']['access_token']
                return access_token

        except Exception as e:
            log(f"❌ Lỗi không mong muốn: {e}. Đang thử lại...", red, account_info)

        await asyncio.sleep(0.5)  # Wait for 5 seconds before retrying

    log("❌ Đã hết số lần thử lại. Chuyển sang tác vụ tiếp theo.", red, account_info)
    return None

async def check_user(index, proxy_manager, user_agent):
    account_info = f"Tài khoản {index + 1}"
    access_token = await fetch(index + 1, proxy_manager, account_info, user_agent)
    if not access_token:
        return None

    # Lấy headers ngẫu nhiên với User-Agent tương ứng
    headers = get_random_headers(user_agent)
    headers['Authorization'] = f'Bearer {access_token}'

    json_payload = {
        "operationName": "QueryTelegramUserMe",
        "variables": {},
        "query": QUERY_USER
    }

    max_retries = 3
    for attempt in range(max_retries):
        proxy = await proxy_manager.get_random_proxy()
        if not proxy:
            log("❌ Không có proxy nào khả dụng để sử dụng.", red, account_info)
            return None

        formatted_proxy = format_proxy(proxy)
        if not formatted_proxy:
            log("❌ Định dạng proxy không hợp lệ sau khi chuyển đổi!", red, account_info)
            await proxy_manager.mark_bad_proxy(proxy, account_info)
            continue

        try:
            scraper = cloudscraper.create_scraper()
            proxies = {
                "http": formatted_proxy,
                "https": formatted_proxy
            }
            # Lấy headers ngẫu nhiên với User-Agent tương ứng
            current_headers = get_random_headers(user_agent)
            current_headers['Authorization'] = f'Bearer {access_token}'

            response = await asyncio.to_thread(scraper.post, url, headers=current_headers, json=json_payload, proxies=proxies)

            if response.status_code == 200:
                response_data = response.json()
                if 'errors' in response_data:
                    log(f"❌ Lỗi Query ID Sai", red, account_info)
                    return None
                else:
                    user_data = response_data['data']['telegramUserMe']
                    return user_data
            else:
                log(f"❌ Lỗi với trạng thái {response.status_code}, thử lại...", red, account_info)
                await proxy_manager.mark_bad_proxy(proxy, account_info)
        except Exception as e:
            log(f"❌ Lỗi khi kiểm tra người dùng: {e}. Đánh dấu proxy là không tốt và thử lại.", red, account_info)
            await proxy_manager.mark_bad_proxy(proxy, account_info)

        await asyncio.sleep(0.5)  # Wait before retrying

    log(f"❌ Đã hết số lần thử lại cho tài khoản {index + 1}.", red, account_info)
    return None

async def activate_energy_recharge_booster(index, proxy_manager, user_agent):
    account_info = f"Tài khoản {index + 1}"
    access_token = await fetch(index + 1, proxy_manager, account_info, user_agent)
    if not access_token:
        return None

    # Lấy headers ngẫu nhiên với User-Agent tương ứng
    headers = get_random_headers(user_agent)
    headers['Authorization'] = f'Bearer {access_token}'

    recharge_booster_payload = {
        "operationName": "telegramGameActivateBooster",
        "variables": {"boosterType": "Recharge"},
        "query": QUERY_BOOSTER
    }

    max_retries = 3
    for attempt in range(max_retries):
        proxy = await proxy_manager.get_random_proxy()
        if not proxy:
            log("❌ Không có proxy nào khả dụng để sử dụng.", red, account_info)
            return None

        formatted_proxy = format_proxy(proxy)
        if not formatted_proxy:
            log("❌ Định dạng proxy không hợp lệ sau khi chuyển đổi!", red, account_info)
            await proxy_manager.mark_bad_proxy(proxy, account_info)
            continue

        try:
            scraper = cloudscraper.create_scraper()
            proxies = {
                "http": formatted_proxy,
                "https": formatted_proxy
            }
            # Lấy headers ngẫu nhiên với User-Agent tương ứng
            current_headers = get_random_headers(user_agent)
            current_headers['Authorization'] = f'Bearer {access_token}'

            response = await asyncio.to_thread(scraper.post, url, headers=current_headers, json=recharge_booster_payload, proxies=proxies)

            if response.status_code == 200:
                response_data = response.json()
                if response_data and 'data' in response_data and 'telegramGameActivateBooster' in response_data['data']:
                    new_energy = response_data['data']['telegramGameActivateBooster']['currentEnergy']
                    log(f"Nạp năng lượng thành công. Năng lượng hiện tại: {new_energy}", green, account_info)
                    return new_energy
                else:
                    log("❌ Không thể kích hoạt Recharge Booster: Dữ liệu không đầy đủ hoặc không có.", red, account_info)
            else:
                log(f"❌ Gặp sự cố với mã trạng thái {response.status_code}, thử lại...", red, account_info)
                await proxy_manager.mark_bad_proxy(proxy, account_info)
        except Exception as e:
            log(f"❌ Lỗi khi kích hoạt Recharge Booster: {e}. Đánh dấu proxy là không tốt và thử lại.", red, account_info)
            await proxy_manager.mark_bad_proxy(proxy, account_info)

        await asyncio.sleep(0.5)  # Wait before retrying

    log("❌ Đã hết số lần thử lại khi kích hoạt Recharge Booster.", red, account_info)
    return None

async def activate_booster(index, proxy_manager, user_agent):
    account_info = f"Tài khoản {index + 1}"
    access_token = await fetch(index + 1, proxy_manager, account_info, user_agent)
    if not access_token:
        return None

    # Lấy headers ngẫu nhiên với User-Agent tương ứng
    headers = get_random_headers(user_agent)
    headers['Authorization'] = f'Bearer {access_token}'

    turbo_booster_payload = {
        "operationName": "telegramGameActivateBooster",
        "variables": {"boosterType": "Turbo"},
        "query": QUERY_BOOSTER
    }

    max_retries = 3
    for attempt in range(max_retries):
        proxy = await proxy_manager.get_random_proxy()
        if not proxy:
            log("❌ Không có proxy nào khả dụng để sử dụng.", red, account_info)
            return None

        formatted_proxy = format_proxy(proxy)
        if not formatted_proxy:
            log("❌ Định dạng proxy không hợp lệ sau khi chuyển đổi!", red, account_info)
            await proxy_manager.mark_bad_proxy(proxy, account_info)
            continue

        try:
            scraper = cloudscraper.create_scraper()
            proxies = {
                "http": formatted_proxy,
                "https": formatted_proxy
            }
            # Lấy headers ngẫu nhiên với User-Agent tương ứng
            current_headers = get_random_headers(user_agent)
            current_headers['Authorization'] = f'Bearer {access_token}'

            response = await asyncio.to_thread(scraper.post, url, headers=current_headers, json=turbo_booster_payload, proxies=proxies)

            if response.status_code == 200:
                response_data = response.json()
                if 'data' in response_data and 'telegramGameActivateBooster' in response_data['data']:
                    current_health = response_data['data']['telegramGameActivateBooster']['currentBoss']['currentHealth']
                    if current_health == 0:
                        log("Boss đã bị hạ gục, chuyển boss tiếp theo...", yellow, account_info)
                        await set_next_boss(index, proxy_manager, user_agent)
                    else:
                        initial_hit = 500000000
                        for _ in range(10):
                            total_hit = initial_hit
                            for retry in range(3):
                                tap_payload = {
                                    "operationName": "MutationGameProcessTapsBatch",
                                    "variables": {
                                        "payload": {
                                            "nonce": generate_random_nonce(),
                                            "tapsCount": int(total_hit)
                                        }
                                    },
                                    "query": MUTATION_GAME_PROCESS_TAPS_BATCH
                                }

                                tap_result = await submit_taps(index, tap_payload, proxy_manager, account_info, user_agent)
                                if tap_result is None:
                                    log(f"❌ Gặp sự cố khi tap, thử lại lần {retry + 1} với {total_hit//2} taps...", yellow, account_info)
                                    total_hit //= 2
                                    if retry == 2:
                                        log("❌ Không thể tap sau 3 lần thử. Chuyển sang vòng lặp tiếp theo.", red, account_info)
                                    await asyncio.sleep(0.5)
                                    continue

                                if isinstance(tap_result, dict) and 'data' in tap_result and 'telegramGameProcessTapsBatch' in tap_result['data']:
                                    tap_data = tap_result['data']['telegramGameProcessTapsBatch']
                                    if tap_data['currentBoss']['currentHealth'] == 0:
                                        log("Boss đã bị hạ gục, chuyển boss tiếp theo...", yellow, account_info)
                                        await set_next_boss(index, proxy_manager, user_agent)
                                    log(f"Đang tap Memefi2 : Balance 💎 {tap_data['coinsAmount']} Năng lượng : {tap_data['currentEnergy']} / {tap_data['maxEnergy']}", green, account_info)
                                    # Thêm độ trễ giữa các lần tap
                                    await asyncio.sleep(random.uniform(0.5, 1))  # Thêm delay ngẫu nhiên giữa 0.5 đến 2 giây
                                    break
                                else:
                                    log(f"❌ Kết quả tap không hợp lệ: {tap_result}", red, account_info)

                                await asyncio.sleep(0.2)

                            if tap_result is None:
                                continue
            else:
                log(f"❌ Gặp sự cố với mã trạng thái {response.status_code}, thử lại...", red, account_info)
                await proxy_manager.mark_bad_proxy(proxy, account_info)
        except Exception as e:
            log(f"❌ Lỗi khi kích hoạt Turbo Booster: {e}. Đánh dấu proxy là không tốt và thử lại.", red, account_info)
            await proxy_manager.mark_bad_proxy(proxy, account_info)

        await asyncio.sleep(0.5)  # Wait before retrying

    log("Kết thúc quá trình kích hoạt Turbo Boost", cyan, account_info)

async def submit_taps(index, json_payload, proxy_manager, account_info="", user_agent=""):
    max_retries = 3
    for attempt in range(max_retries):
        proxy = await proxy_manager.get_random_proxy()
        if not proxy:
            log("❌ Không có proxy nào khả dụng để sử dụng.", red, account_info)
            return None

        formatted_proxy = format_proxy(proxy)
        if not formatted_proxy:
            log("❌ Định dạng proxy không hợp lệ sau khi chuyển đổi!", red, account_info)
            await proxy_manager.mark_bad_proxy(proxy, account_info)
            continue

        try:
            access_token = await fetch(index + 1, proxy_manager, account_info, user_agent)
            if not access_token:
                return None

            # Lấy headers ngẫu nhiên với User-Agent tương ứng
            headers = get_random_headers(user_agent)
            headers['Authorization'] = f'Bearer {access_token}'

            scraper = cloudscraper.create_scraper()
            proxies = {
                "http": formatted_proxy,
                "https": formatted_proxy
            }

            response = await asyncio.to_thread(scraper.post, url, headers=headers, json=json_payload, proxies=proxies)

            if response.status_code == 200:
                response_data = response.json()
                return response_data
            else:
                log(f"❌ Thất bại với trạng thái {response.status_code}, thử lại...", red, account_info)
                await proxy_manager.mark_bad_proxy(proxy, account_info)
        except Exception as e:
            log(f"Lỗi: {e}", red, account_info)
            await proxy_manager.mark_bad_proxy(proxy, account_info)

        await asyncio.sleep(0.5)  # Wait before retrying

    log("❌ Đã hết số lần thử lại cho tap.", red, account_info)
    return None

async def set_next_boss(index, proxy_manager, user_agent):
    account_info = f"Tài khoản {index + 1}"
    access_token = await fetch(index + 1, proxy_manager, account_info, user_agent)
    if not access_token:
        return None

    # Lấy headers ngẫu nhiên với User-Agent tương ứng
    headers = get_random_headers(user_agent)
    headers['Authorization'] = f'Bearer {access_token}'

    json_payload = {
        "operationName": "telegramGameSetNextBoss",
        "variables": {},
        "query": QUERY_NEXT_BOSS
    }

    max_retries = 3
    for attempt in range(max_retries):
        proxy = await proxy_manager.get_random_proxy()
        if not proxy:
            log("❌ Không có proxy nào khả dụng để sử dụng.", red, account_info)
            return None

        formatted_proxy = format_proxy(proxy)
        if not formatted_proxy:
            log("❌ Định dạng proxy không hợp lệ sau khi chuyển đổi!", red, account_info)
            await proxy_manager.mark_bad_proxy(proxy, account_info)
            continue

        try:
            scraper = cloudscraper.create_scraper()
            proxies = {
                "http": formatted_proxy,
                "https": formatted_proxy
            }
            # Lấy headers ngẫu nhiên với User-Agent tương ứng
            current_headers = get_random_headers(user_agent)
            current_headers['Authorization'] = f'Bearer {access_token}'

            response = await asyncio.to_thread(scraper.post, url, headers=current_headers, json=json_payload, proxies=proxies)

            if response.status_code == 200:
                response_data = response.json()
                if response_data and 'data' in response_data:
                    log("Boss tiếp theo đã được đặt thành công!", green, account_info)
                    return response_data
                else:
                    log("❌ Không thể đặt Boss tiếp theo: Dữ liệu không đầy đủ hoặc không có.", red, account_info)
            else:
                log(f"❌ Gặp sự cố với mã trạng thái {response.status_code}, thử lại...", red, account_info)
                await proxy_manager.mark_bad_proxy(proxy, account_info)
        except Exception as e:
            log(f"❌ Lỗi khi đặt Boss tiếp theo: {e}. Đánh dấu proxy là không tốt và thử lại.", red, account_info)
            await proxy_manager.mark_bad_proxy(proxy, account_info)

        await asyncio.sleep(0.5)  # Wait before retrying

    log("❌ Đã hết số lần thử lại khi đặt Boss tiếp theo.", red, account_info)
    return None

async def check_stat(index, proxy_manager, user_agent):
    account_info = f"Tài khoản {index + 1}"
    access_token = await fetch(index + 1, proxy_manager, account_info, user_agent)
    if not access_token:
        return None

    # Lấy headers ngẫu nhiên với User-Agent tương ứng
    headers = get_random_headers(user_agent)
    headers['Authorization'] = f'Bearer {access_token}'

    json_payload = {
        "operationName": "QUERY_GAME_CONFIG",
        "variables": {},
        "query": QUERY_GAME_CONFIG
    }

    max_retries = 3
    for attempt in range(max_retries):
        proxy = await proxy_manager.get_random_proxy()
        if not proxy:
            log("❌ Không có proxy nào khả dụng để sử dụng.", red, account_info)
            return None

        formatted_proxy = format_proxy(proxy)
        if not formatted_proxy:
            log("❌ Định dạng proxy không hợp lệ sau khi chuyển đổi!", red, account_info)
            await proxy_manager.mark_bad_proxy(proxy, account_info)
            continue

        try:
            scraper = cloudscraper.create_scraper()
            proxies = {
                "http": formatted_proxy,
                "https": formatted_proxy
            }
            # Lấy headers ngẫu nhiên với User-Agent tương ứng
            current_headers = get_random_headers(user_agent)
            current_headers['Authorization'] = f'Bearer {access_token}'

            response = await asyncio.to_thread(scraper.post, url, headers=current_headers, json=json_payload, proxies=proxies)

            if response.status_code == 200:
                response_data = response.json()
                if 'errors' in response_data:
                    return None
                else:
                    user_data = response_data['data']['telegramGameGetConfig']
                    return user_data
            else:
                log(f"❌ Lỗi với trạng thái {response.status_code}, thử lại...", red, account_info)
                await proxy_manager.mark_bad_proxy(proxy, account_info)
        except Exception as e:
            log(f"❌ Lỗi khi kiểm tra thống kê: {e}. Đánh dấu proxy là không tốt và thử lại.", red, account_info)
            await proxy_manager.mark_bad_proxy(proxy, account_info)

        await asyncio.sleep(0.5)  # Wait before retrying

    log("❌ Đã hết số lần thử lại cho kiểm tra thống kê.", red, account_info)
    return None

async def animate_energy_recharge(duration):
    frames = ["|", "/", "-", "\\"]
    end_time = time.time() + duration
    while time.time() < end_time:
        remaining_time = int(end_time - time.time())
        for frame in frames:
            log2(f"Đang nạp lại năng lượng {frame} - Còn lại {remaining_time} giây", cyan)
            await asyncio.sleep(0.25)
    log2("Nạp năng lượng hoàn thành.", green)

async def process_account(index, user_data, first_name, last_name, proxy_manager, user_agent):
    account_info = f"Tài khoản {index + 1}: {first_name} {last_name}"
    proxy = await proxy_manager.get_random_proxy()
    if not proxy:
        log("❌ Không có proxy nào khả dụng để sử dụng.", red, account_info)
        return

    should_continue_to_next_account = False
    stat_result = await check_stat(index, proxy_manager, user_agent)

    if stat_result is not None:
        user_data = stat_result
        log("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~", cyan, account_info)
        log(f"Tài khoản {index + 1} : {first_name} {last_name}", cyan, account_info)
        log(f"Balance 💎 {user_data.get('coinsAmount', 'Unknown')} Năng lượng : {user_data.get('currentEnergy', 'Unknown')} / {user_data.get('maxEnergy', 'Unknown')}", green, account_info)
        log(f"Boss LV {user_data['currentBoss'].get('level', 'Unknown')} ❤️  {user_data['currentBoss'].get('currentHealth', 'Unknown')} - {user_data['currentBoss'].get('maxHealth', 'Unknown')}", green, account_info)
        log(f"Turbo {user_data['freeBoosts'].get('currentTurboAmount', 'Unknown')} Recharge {user_data['freeBoosts'].get('currentRefillEnergyAmount', 'Unknown')}", green, account_info)
    else:
        log(f"⚠️ Cảnh báo: Không thể truy xuất dữ liệu người dùng cho tài khoản {index + 1}. Chuyển sang tài khoản tiếp theo.", red, account_info)
        return

    if 'currentBoss' in user_data:
        lv_boss = user_data['currentBoss']['level']
        mau_boss = user_data['currentBoss']['currentHealth']
        if lv_boss >= 10 and mau_boss == 0:
            log(f"=================== {first_name} {last_name} KẾT THÚC ====================", magenta, account_info)
            should_continue_to_next_account = True
        if mau_boss == 0:
            log("Boss đã bị hạ gục, chuyển boss tiếp theo...", yellow, account_info)
            await set_next_boss(index, proxy_manager, user_agent)

    log("Bắt đầu tap", green, account_info)

    energy_now = user_data['currentEnergy']
    recharge_available = user_data['freeBoosts']['currentRefillEnergyAmount']
    if not should_continue_to_next_account:
        while energy_now > 500 or recharge_available > 0:
            total_tap = random.randint(100, 200)
            tap_payload = {
                "operationName": "MutationGameProcessTapsBatch",
                "variables": {
                    "payload": {
                        "nonce": generate_random_nonce(),
                        "tapsCount": total_tap
                    }
                },
                "query": MUTATION_GAME_PROCESS_TAPS_BATCH
            }

            tap_result = await submit_taps(index, tap_payload, proxy_manager, account_info, user_agent)
            if tap_result is not None:
                user_data = await check_stat(index, proxy_manager, user_agent)
                if user_data is None:
                    log(f"❌ Không thể cập nhật trạng thái sau khi tap, chuyển sang tài khoản tiếp theo.", red, account_info)
                    break
                energy_now = user_data['currentEnergy']
                recharge_available = user_data['freeBoosts'].get('currentRefillEnergyAmount', 0)
                log(f"Đang tap Memefi2 : Balance 💎 {user_data.get('coinsAmount', 'Unknown')} Năng lượng : {energy_now} / {user_data.get('maxEnergy', 'Unknown')}", green, account_info)
            else:
                log(f"❌ Lỗi với trạng thái {tap_result}, thử lại...", red, account_info)

            # Thêm độ trễ ngẫu nhiên từ 1 đến 3 giây
            await asyncio.sleep(random.uniform(0.5, 1))

            if energy_now < 500:
                if recharge_available > 0:
                    log("Hết năng lượng, kích hoạt Recharge...", yellow, account_info)
                    await activate_energy_recharge_booster(index, proxy_manager, user_agent)
                    user_data = await check_stat(index, proxy_manager, user_agent)
                    if user_data is None:
                        log(f"❌ Không thể cập nhật trạng thái sau khi Recharge, chuyển sang tài khoản tiếp theo.", red, account_info)
                        break
                    energy_now = user_data['currentEnergy']
                    recharge_available = user_data['freeBoosts'].get('currentRefillEnergyAmount', 0)
                else:
                    log("Năng lượng dưới 500 và không còn Recharge, chuyển sang tài khoản tiếp theo.", yellow, account_info)
                    break

            if user_data['freeBoosts'].get('currentTurboAmount', 0) > 0:
                await activate_booster(index, proxy_manager, user_agent)
    if should_continue_to_next_account:
        return

async def main():
    log("Bắt đầu Memefi bot...", magenta)

    # Đọc proxy từ proxy.txt thông qua ProxyManager
    proxy_manager = ProxyManager('proxy.txt')
    if not proxy_manager.all_proxies:
        log("❌ Không có proxy nào để sử dụng. Dừng chương trình.", red)
        return

    # Kiểm tra các proxy ngay khi bắt đầu
    await proxy_manager.validate_proxies()
    if not proxy_manager.valid_proxies:
        log("❌ Không còn proxy nào hợp lệ sau khi kiểm tra. Dừng chương trình.", red)
        return

    # Đọc data.txt và useragent.txt
    try:
        with open('data.txt', 'r') as data_file:
            account_lines = data_file.readlines()

        if not account_lines:
            log("❌ data.txt trống!", red)
            return

        with open('useragent.txt', 'r') as ua_file:
            useragent_lines = ua_file.readlines()

        if not useragent_lines:
            log("❌ useragent.txt trống!", red)
            return

        if len(useragent_lines) < len(account_lines):
            log("❌ Số dòng trong useragent.txt ít hơn số dòng trong data.txt!", red)
            return
        else:
            # Nếu useragent.txt có nhiều hơn, chỉ lấy đủ số lượng tương ứng với data.txt
            useragent_lines = useragent_lines[:len(account_lines)]

    except FileNotFoundError as e:
        log(f"❌ Không tìm thấy file: {e.filename}", red)
        return

    while True:
        accounts = []

        # Tạo danh sách các nhiệm vụ kiểm tra người dùng đồng thời
        check_user_tasks = [
            check_user(index, proxy_manager, useragent_lines[index].strip())
            for index, line in enumerate(account_lines)
        ]

        # Thực hiện kiểm tra người dùng đồng thời
        check_user_results = await asyncio.gather(*check_user_tasks, return_exceptions=True)

        for index, result in enumerate(check_user_results):
            account_info = f"Tài khoản {index + 1}"
            if isinstance(result, Exception):
                log(f"❌ {account_info}: Lỗi xảy ra trong quá trình kiểm tra người dùng.", red, account_info)
                continue

            if result is not None:
                first_name = result.get('firstName', 'Unknown')
                last_name = result.get('lastName', 'Unknown')
                user_agent = useragent_lines[index].strip()
                accounts.append((index, result, first_name, last_name, user_agent))
            else:
                log(f"❌ {account_info}: Token không hợp lệ hoặc có lỗi xảy ra", red, account_info)

        # Đặt giới hạn số lượng tài khoản được xử lý đồng thời
        semaphore = asyncio.Semaphore(30)  # Giới hạn ở mức 5

        async def process_account_with_semaphore(*args, **kwargs):
            async with semaphore:
                await process_account(*args, **kwargs)

        # Tạo danh sách các nhiệm vụ xử lý tài khoản đồng thời với semaphore
        account_tasks = [
            process_account_with_semaphore(index, result, first_name, last_name, proxy_manager, user_agent)
            for index, result, first_name, last_name, user_agent in accounts
        ]

        # Thực hiện xử lý tài khoản đồng thời
        await asyncio.gather(*account_tasks, return_exceptions=True)

        log("=== [ TẤT CẢ TÀI KHOẢN ĐÃ ĐƯỢC XỬ LÝ ] ===", magenta)
        await animate_energy_recharge(600)  # Thêm độ trễ trước khi lặp lại vòng while

if __name__ == "__main__":
    asyncio.run(main())
