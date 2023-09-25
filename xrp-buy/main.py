import os
import re
import time
import json
import asyncio
import aiohttp
import platform
import requests
from bs4 import BeautifulSoup
from transliterate import translit

start_time = time.time()

""" Создание необходимых директорий:
    obj/ содержит сохраненные ссылки и html-файлы для обработки, 
    data/ содержит итоговые данные - json-файлы 
"""
dirs = ['obj/', 'obj/cats/', 'data/']
for i in dirs:
    if not os.path.exists(i):
        os.mkdir(i)

""" Определение основных переменных, необходимых для сетевых запросов
"""
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36'
}
url = 'https://xrp-buy.ru/'

""" Запрос к главной странице сайта, сохранение html-страницы
"""
page = requests.get(url=url, headers=headers)

with open('obj/index.html', 'w', encoding='utf-8') as file:
    file.write(page.text)

""" Чтение сохраненной html-страницы, парсинг по тегам категорий,
    сохранение ссылок на категории в файл-json ('название категории': 'ссылка на категорию')
"""
with open('obj/index.html', 'r', encoding='utf-8') as file:
    src = file.read()

soup = BeautifulSoup(src, 'lxml')

categories_dict = {}
categories = soup.find(class_='cat-item').find_previous().find_all('a')
for i in categories:
    title = i.text.replace('\t', '_').replace('\n', '_')
    title = re.sub(r'\s+', '_', title)
    if title == 'Видео':
        continue
    title_translit = translit(title, 'ru', reversed=True)
    link = i['href']
    categories_dict[title_translit] = link

    with open('obj/categories.json', 'w', encoding='utf-8') as file:
        json.dump(categories_dict, file, indent=4, ensure_ascii=False) 


""" Чтение файла со ссылками на категории,
    создание асинхронных запросов к страницам категорий, парсинг ссылок на статьи определенных категорий,
    обход пагинации страниц категорий, сохранение ссылок на статьи в отдельную директорию в файлы txt
"""
category = {}

with open('obj/categories.json', 'r') as file:
    category = json.load(file)


async def fetch(session, url, retry = 5):
    try:
        async with session.get(url, headers=headers) as response:
            status_code = response.status
            print(f'[DONE] {url} {status_code}')
            return await response.text()
    except:
        await asyncio.sleep(5)
        if retry:
            print(f'[INFO] Attempt {retry}: {url}')
            return await fetch(session, url, retry=(retry - 1))
        else:
            raise


async def scrap_category(key: str, value: str):
    articles_list = []

    async with aiohttp.ClientSession() as session:
        html = await fetch(session, value)
        soup = BeautifulSoup(html, 'lxml')
        pagination = soup.find(class_='next page-numbers')
        if pagination:
            pages_count = pagination.find_previous().text
            for page in range(1, int(pages_count) + 1):
                url_pagination = f'{value}page/{page}'
                html = await fetch(session, url_pagination)
                soup = BeautifulSoup(html, 'lxml')
                articles = soup.find_all(class_='content-thumb')
                for i in articles:
                    article_a = i.find('a')
                    article_href = article_a.get('href')
                    articles_list.append(article_href)
        else:
            articles = soup.find_all(class_='content-thumb')
            for i in articles:
                article_a = i.find('a')
                article_href = article_a.get('href')
                articles_list.append(article_href)

    with open(f'obj/cats/{key.lower()}.txt', 'w') as file:
        for i in articles_list:            
            file.write(i + '\n')


async def start_scrap_category():
    tasks = []
    for key, value in category.items():
        tasks.append(asyncio.create_task(scrap_category(key, value)))
    await asyncio.gather(*tasks)


""" Определение списка текстовых файлов в директории obj/cats, чтение ссылок на статьи,
    сохранение данных из ссылок в файлы json
"""
async def scrap_article():

    async with aiohttp.ClientSession() as session:
        path = 'obj/cats'
        files_cats = os.listdir(path)

        for filename in files_cats:
            with open(f'obj/cats/{filename}', 'r') as file:
                articles = [link.strip() for link in file.readlines()]

                data = []

                for i in articles:
                    html = await fetch(session, i)
                    soup = BeautifulSoup(html, 'lxml')

                    article = soup.find('article')
                    article_title = article.find('header').text
                    article_date = article.find('span', class_='entry-meta-date').text
                    article_body = article.find('div', class_='entry-content').text

                    result_data = {
                        'title': article_title.replace('\n', ''),
                        'date': article_date,
                        'body': article_body.replace('\n', ''),
                    }

                    data.append(result_data)

                    filename_json = filename.replace('txt', 'json')
                    with open(f'data/{filename_json}', 'w', encoding='utf-8') as file:
                        json.dump(data, file, indent=4, ensure_ascii=False)


async def start_scrap_articles():
    tasks = []
    tasks.append(asyncio.create_task(scrap_article()))
    await asyncio.gather(*tasks)


async def main():
    await start_scrap_category()
    await start_scrap_articles()


""" Запуск асинхронного процесса
"""
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
asyncio.run(main())

finish_time = time.time()
print(f'Время работы парсера: {round(finish_time - start_time)} секунд')
