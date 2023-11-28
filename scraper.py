import operator
import os
import re
import time
import json
import concurrent.futures
from requests import Response, Session
from datetime import datetime
from bs4 import BeautifulSoup
from queue import Queue


MAX_THREADS = 4
MILLION = 1000000


class Scraper:
    url_queue = Queue(maxsize=0)
    app_data = dict()
    queue_store = dict()
    total_apps = dict()
    base_url = 'https://app.sensortower.com'
    session = Session()

    def get_page(self, url) -> Response:
        while True:
            response = self.session.get(url)
            if response.status_code == 200:
                return response
            elif response.status_code == 410:
                self.saving_data(self.app_data)
                with open('apps.json', 'w') as f:
                    json.dump(self.total_apps, f)
                    f.close()
                input('Press Enter to continue...')
            else:
                print(f"Status code {response.status_code}, sleeping for 90 second")
                time.sleep(90)

    def initialize_list(self) -> None:
        date = datetime.today().strftime('%Y-%m-%d')
        content = self.get_page(
            f'https://app.sensortower.com/api/android/rankings/'
            f'get_category_rankings?category=game&country=US&date={date}&device=MOBILE&limit=200')
        content = content.json()

        for row in content:
            for url in row:
                self.url_queue.put(f'{self.base_url}{url["app_view_url"]}overview')
                self.queue_store.update({f'{self.base_url}{url["app_view_url"]}overview': None})
                self.total_apps.update({f'{self.base_url}{url["app_view_url"]}overview': None})

    def page_info(self, url) -> None:
        content = self.get_page(url).content
        soup = BeautifulSoup(content, 'html.parser')
        comment = re.findall(r'params: (.*)', str(soup))
        data = json.loads(comment[1])

        if operator.not_(self.is_game_exist(f'{self.base_url}{data["app_view_url"]}overview')):
            self.app_data[f'{self.base_url}{data["app_view_url"]}overview'] = data
            self.total_apps.update({f'{self.base_url}{data["app_view_url"]}overview': None})

            for related_app in data['related_apps']:
                '''
                @todo change 'game' to a list of all game cat
                '''
                if 'game' in related_app['categories'] and operator.not_(self.is_game_exist(f'{self.base_url}{related_app["app_view_url"]}overview')):
                    self.url_queue.put(f'{self.base_url}{related_app["app_view_url"]}overview')
                    self.queue_store.update({f'{self.base_url}{related_app["app_view_url"]}overview': None})

    def is_game_exist(self, game_id) -> bool:
        return game_id in self.total_apps

    @staticmethod
    def saving_data(data) -> None:
        with open('saved_data.json', 'w') as f:
            json.dump(data, f)
            f.close()

    def run(self) -> None:
        if os.path.exists('./apps.json') and os.path.exists('./queue_bank.json'):
            with open('apps.json', 'r') as f:
                self.total_apps = json.load(f)
                f.close()
            with open('queue_bank.json', 'r') as f:
                self.queue_store = json.load(f)
                for key in self.queue_store.keys():
                    self.url_queue.put(key)
                f.close()
        else:
            self.initialize_list()
            with open('top_charts.json', 'w') as f:
                json.dump(self.queue_store, f)
                f.close()

        save_condition = 1000 * (len(self.app_data) // 1000) + 1000

        while len(self.app_data) < 25000 and not self.url_queue.empty():  # Change 1,000,000
            threads = min(MAX_THREADS, self.url_queue.qsize())
            if len(self.app_data) < save_condition:
                with concurrent.futures.ThreadPoolExecutor(threads) as executor:
                    urls = []
                    while len(urls) < 3:
                        url = self.url_queue.get()
                        if operator.not_(self.is_game_exist(url)):
                            urls.append(url)
                        if self.queue_store.get(url):
                            self.queue_store.pop(url)
                    if len(urls):
                        executor.map(self.page_info, urls)
                with open('queue_bank.json', 'w') as f:
                    json.dump(self.queue_store, f)
                    f.close()
                with open('apps.json', 'w') as f:
                    json.dump(self.total_apps, f)
                    f.close()

            else:
                self.saving_data(self.app_data)
                save_condition += 1000

            print('queue size:', self.url_queue.qsize())
            print('app_data counter:', len(self.app_data))
            print('total_apps counter:', len(self.total_apps))

        print('reached 25000 apps saving...')
        self.saving_data(self.app_data)
        with open('apps.json', 'w') as f:
            json.dump(self.total_apps, f)
            f.close()


if __name__ == '__main__':
    Scraper().run()
    print('finished')
