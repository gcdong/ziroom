import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import TimeoutException
import re
import urllib.request
import os
from PIL import Image
import pytesseract
import pymysql
import time


class Ziromm():
    def __init__(self, url, host, user, password, db, table):
        self.url = url
        self.table = table
        self.conn = pymysql.connect(host=host, user=user,
                                    passwd=password, db=db, charset='utf8')
        self.cur = self.conn.cursor()
        self.browser = webdriver.Chrome()
        self.wait = WebDriverWait(self.browser, 10)

    def save(self, data):
        keys = ','.join(data.keys())
        values = ', '.join(['%s'] * len(data))
        id = data.get('id')
        sql = "SELECT id FROM %s WHERE id=%s" % (self.table, id)
        self.cur.execute(sql)
        # 找出这个ID有没有,有的话跳出,没有的话写入
        if self.cur.rowcount > 0:
            print('跳出循环')
        else:
            sql = 'INSERT INTO {table}({keys}) VALUES ({values})'.format(table=self.table, keys=keys, values=values)
            self.cur.execute(sql, tuple(data.values()))
            self.conn.commit()

    def get_html(self, url):
        self.browser.get(url)
        try:
            self.wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.priceDetail .price .num')))
            return BeautifulSoup(self.browser.page_source, "lxml")
        except TimeoutException:
            print('这个页面没有数据')

    def load_html(self, bsObj, area, address):
        time.sleep(1)
        js_str = bsObj.find(string=re.compile("//static8.ziroom.com/phoenix/pc/images/price/(.*).png"))
        img_url = 'http:' + re.search('//static8.ziroom.com/phoenix/pc/images/price/(.*).png', js_str).group(0)
        path = './code.png'
        urllib.request.urlretrieve(img_url, path)
        image = Image.open(path)
        code = pytesseract.image_to_string(image, config='--psm 6')
        ul = bsObj.select("ul[id='houseList']")
        li_list = ul[0].select("li")

        for li in li_list:
            href = li.select('h3 > a')[0].attrs.get('href')
            if re.search('ziroom.com/z/vr/([0-9]*).html', href) is None:
                print('自如寓')
                continue
            id = re.search('gz.ziroom.com/z/vr/([0-9]*).html', href).group(1)
            detail = li.select('.detail > p')
            d1 = detail[0].select('span')[0].text
            d2 = detail[0].select('span')[1].text
            d3 = detail[0].select('span')[2].text
            d4 = detail[1].select('span')[0].text
            size = re.search('(.*) ㎡', d1).group(1)
            floor = re.search('([0-9]*)/([0-9]*)', d2).group(1)
            total_floor = re.search('([0-9]*)/([0-9]*)', d2).group(2)
            room = re.search('([0-9]*)室([0-9]*)厅', d3).group(1)
            hall = re.search('([0-9]*)室([0-9]*)厅', d3).group(2)
            matchd4 = re.search('距([0-9]*号线|APM|广佛线)(.*)站(.*)米', d4)
            if matchd4 is not None:
                line = matchd4.group(1)
                station = matchd4.group(2)
                distance = matchd4.group(3)
            else:
                line = '0'
                station = '0'
                distance = '0'
            taps = li.select(".room_tags")[0].text.replace("\n", ",")[1:]
            prices = li.select(".priceDetail .price span")[1:]
            price_str = ''
            for price in prices:
                style = price.attrs.get('style')
                if style is not None:
                    i = re.search('background-position:-([0-9]*)px', style).group(1)
                    k = int(int(i) / 30)
                    price_str += code[k:k + 1]
            data = {
                "price": price_str,
                "size": size.replace("约", ""),
                "floor": floor,
                "total_floor": total_floor,
                "room": room,
                "hall": hall,
                "line": line,
                "station": station,
                "distance": distance,
                "taps": taps,
                "href": href,
                "id": id,
                "area": area,
                "address": address
            }
            self.save(data)
            print(data)

    def begin_link(self, url, area, address):
        bsObj = self.get_html(url)
        if bsObj is not None:
            page_str = bsObj.find(string=re.compile('共([0-9]*)页'))
            self.load_html(bsObj, area, address)
            if page_str:
                page = re.search('共([0-9]*)页', page_str).group(1)
                for p in range(2, int(page) + 1):
                    bsObj = self.get_html(url + '?p=' + str(p))
                    self.load_html(bsObj, area, address)

    def main(self):
        r = requests.get(self.url)
        bsObj = BeautifulSoup(r.text, 'lxml')
        lis = bsObj.select('.zIndex6 ul li')
        for li in lis[1:]:
            area = li.select('span')[0].select('a')[0].text
            hs = li.select('span')[2:]
            for h in hs:
                address = h.select('a')[0].text
                href = 'http:' + h.select('a')[0].attrs.get('href')
                self.begin_link(href, area, address)


a = Ziromm('http://gz.ziroom.com/z/nl/z3.html', '127.0.0.1', 'root', 'root', 'ziroom', 'guangzhou')
a.main()
