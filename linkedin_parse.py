# -*- coding: utf-8 -*-

import os
import re
import sys
import time
import xlrd
import arrow
import loguru
import pickle
import pprint
import random
import hashlib
import platform

import pandas as pd
from langdetect import detect
from typing import Tuple, Union

from selenium import webdriver
from elasticsearch import Elasticsearch
from selenium.webdriver import DesiredCapabilities
from selenium.common.exceptions import WebDriverException, \
    NoSuchElementException, JavascriptException

from config import

class LinkedInPy:

    """
        Class, allows to create a selenium chromedriver object and
        parse users posts.
        As arguments, it accepts the linkedin user account name for parsing,
        and the login and password of the account through which parsing takes place.
    """

    def __init__(self, login, password):
        self.login = login
        self.password = password

        self.script_dir = os.getcwd()
        self.driver_path = self.get_system_chromedriver()

        self.account_url = None
        self.linkedin_url = 'https://www.linkedin.com/'
        self.login_url = '{0}login'.format(self.linkedin_url)

        self.driver = None

    def get_system_chromedriver(self):

        """
            The method takes script directory as argument and depending on
            the OS, determines the Chrome driver file and, if it exists
            in the working directory, returns the absolute path to it.
        """

        os_system = platform.system()
        if os_system == 'Linux':
            chrome_driver = 'chromedriver'
        elif os_system == 'Windows':
            chrome_driver = 'chromedriver.exe'
        elif os_system == 'Darwin':
            chrome_driver = 'chromedriver_mac_64'
        else:
            loguru.logger.exception('Chrome driver is not supported on your OS!')
            return False

        if platform.system() == 'Linux':
            driverpath = "/usr/local/bin/webdriver"
        else:
            driverpath = self.script_dir
        driver_path = os.path.join(driverpath, chrome_driver)
        return driverpath

    def start_driver_session(self, mb=True):

        """
            The method initializes selenium chrome driver with options
            and return driver object.
        """

        loguru.logger.debug('Start Driver Session')

        try:
            mobile_emulation = { "deviceName": "iPhone X" }
            options = webdriver.ChromeOptions()
            options.add_argument('--ignore-certificate-errors')
            options.add_argument('--test-type')
            options.add_argument('--no-sandbox')
            options.add_argument('--dns-prefetch-disable')
            options.add_argument('--lang=en-US')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable_infobars')
            options.add_argument('--disable-setuid-sandbox')
            capabilities = DesiredCapabilities.CHROME

            loguru.logger.debug(self.driver_path)
            self.driver = webdriver.Chrome("assets/chromedriver_mac_64",
                                           options=options,
                                           desired_capabilities=capabilities)
        except:
             loguru.logger.exception('Cant init Chrome Web Driver')
             return False

    def login_to_linkedin(self):

        """
            The method for login to linkedin.
            1. If cookie file not in working folder - open linkedin login page,
                authorize, get cookies and save its into pickle file like python
                object.
            2. If cookie file exist - open linkedin main page, load to driver cookies
                from file.
            Return driver object.
        """

        loguru.logger.debug('Login to Linkedin')
        cookie_file = os.path.join(self.script_dir, 'cookiefile')
        
        if os.path.isfile(cookie_file):
            self.driver.get(self.linkedin_url)
            cookies = pickle.load(open(cookie_file, "rb"))
            for cookie in cookies:
                # Cookie "expiry" needs to keep session active.
                # This is date in timestamp format
                # Date should be at least one year longer
                today = arrow.now()
                cookie['expiry'] = today.shift(years=+1).timestamp
                self.driver.add_cookie(cookie)
        else:
            self.driver.get(self.login_url)
            try:
                username = self.driver.find_element_by_id('username')
                username.clear()
                username.send_keys(self.login)

                password = self.driver.find_element_by_id('password')
                password.clear()
                password.send_keys(self.password)
                password.submit()

                # After login save cookies as python object to the pickle file
                pickle.dump(self.driver.get_cookies(), open(cookie_file, 'wb'))
            except NoSuchElementException:
                loguru.logger.exception('NoSuchElementException')
                return False
        return True

    def get_posts(self, last_posts_qty=None, account_url=None) -> list:

        """
            Method to get a list off all div's that contains posts.
            Posts are displaying on the page dynamically as scroll, so
            to get all posts, used the JS function ( window.scrollTo() )
            to scroll to the end of page.
            ------------------------- WARNING -------------------------
            If last_posts_qty is None and account contains lots of posts,
            this procedure will be very time-consuming and resource-intensive.
            It’s better to limit the number of posts you need.
            Or use other methods and libraries to get all the posts.
            -----------------------------------------------------------
        """

        loguru.logger.debug('Get Posts Divs')

        self.account_url = account_url
        # Open page with posts for account
        self.driver.get(account_url)

        # Get start page height coord to scroll
        scroll_height_func = 'return document.body.scrollHeight'
        start_page_height = self.driver.execute_script(scroll_height_func)

        flag = True
        start_div = 0
        all_posts_divs = []

        while flag:
            visible_divs = self.get_list_post_divs()
            if not visible_divs:
                flag = False
            qty_visible_divs = len(visible_divs)

            all_posts_divs.extend(visible_divs[start_div:qty_visible_divs])

            divs_qty = len(all_posts_divs)

            if last_posts_qty and divs_qty >= int(last_posts_qty):
                flag = False
            else:
                end_page_height = self.scroll_page(scroll_height_func)
                if start_page_height == end_page_height:
                    flag = False
                start_page_height = end_page_height
                start_div = qty_visible_divs

        # First open page have 5 visible posts. If we need less posts - get slice.
        if last_posts_qty and last_posts_qty <= 5:
            return all_posts_divs[:last_posts_qty]
        else:
            return all_posts_divs

    def collect_posts_info(self, all_posts_divs: list) -> dict:

        """ Parse post divs and collect info from it """

        loguru.logger.debug('Collect Posts Info')

        posts = []
        for div in all_posts_divs:
            try:
                post_dict = {}
                post_dict['owner_url'] = self.account_url
                post_dict['owner'] = self.get_author(div)
                post_dict['owner_id'] = self.get_owner_id()
                post_dict['timestamp'] = self.get_post_timestamp(div)
                post_dict['foundtime'] = self.get_post_foundtime()
                post_dict['isodate'] = self.get_post_isodate(post_dict['timestamp'])
                post_dict['text'] = self.get_post_text(div)
                post_dict['title'] = self.get_post_title(post_dict['text'])
                post_dict['url'] = self.get_post_url(div)
                post_dict['likes'] = self.get_likes_qty(div)
                post_dict['comments'] = self.get_comments_qty(div)
                post_dict['language'] = self.get_language(post_dict['text'])
                post_dict['smitype'] = 7
                post_dict['country'] = 'ua'
                post_dict['region'] = 'default'
                post_dict['source'] = 'linkedin'
                post_dict['photos'] = []
                post_dict['videos'] = []
                post_dict['id'] = hashlib.md5(post_dict['url'].encode("utf-8")).hexdigest()
                posts.append(post_dict)
            except (JavascriptException, NoSuchElementException) as err:
                loguru.logger.exception(err)
                continue
        return posts

    def scroll_page(self, scroll_height_func: str) -> webdriver:
        self.driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
        time.sleep(3)
        return self.driver.execute_script(scroll_height_func)

    def get_list_post_divs(self) -> webdriver:
        div_xpath = '//div[@class="occludable-update ember-view"]'
        return self.driver.find_elements_by_xpath(div_xpath)

    def get_post_url(self, div: webdriver) -> str:
        url_xpath = './/*[@class="artdeco-toast-item__cta"]'
        copy_image_icon = 'li-icon[type=link-icon]'
        js_copy_btn_click = 'arguments[0].querySelector("{0}").click();'.format(copy_image_icon)
        self.driver.execute_script(js_copy_btn_click, div)

        return self.driver.find_element_by_xpath(url_xpath).get_attribute("href")

    def get_owner_id(self) -> str:
        return self.account_url.split('/')[-2]

    @staticmethod
    def get_post_title(text: str) -> str:
        text = text.split(' ')[:3]
        text = ' '.join(text)
        return f'{text}...'

    @staticmethod
    def get_author(div: webdriver) -> str:
        xpath = './/*[@class="feed-shared-actor__title"]/span/span[@dir="ltr"]'
        return div.find_element_by_xpath(xpath).text

    @staticmethod
    def get_post_foundtime():
        return arrow.now(TIMEZONE).timestamp

    @staticmethod
    def get_post_timestamp(div: webdriver) -> int:
        xpath = './/*[@class="feed-shared-actor__sub-description t-12 t-black--light t-normal v-align-top"]/div/span[1]'
        time_period_str = div.find_element_by_xpath(xpath).text.lower()

        # Sometimes post date seems like "Published • 6mo",
        # or "3w • Edited".
        split_period = time_period_str.split(' ')
        period = None
        qty_period = None
        for p in split_period:
            qty_period = re.findall('\d+', p)
            if qty_period:
                qty_period = int(qty_period[0])
                period = re.findall('\D+', p)[0]
                break

        # today = datetime.now()
        post_date = None
        today = arrow.utcnow()
        if period == 'm':
            post_date = today.shift(minutes=-qty_period).timestamp
        elif period == 'h':
            post_date = today.shift(hours=-qty_period).timestamp
        elif period == 'd':
            post_date = today.shift(days=-qty_period).timestamp
        elif period == 'w':
            post_date = today.shift(weeks=-qty_period).timestamp
        elif period == 'mo':
            post_date = today.shift(months=-qty_period).timestamp
        elif period == 'yr':
            post_date = today.shift(years=-qty_period).timestamp
        return int(post_date)

    @staticmethod
    def get_post_text(div: webdriver) -> str:
        xpath = './/*[@class="feed-shared-text__text-view feed-shared-text-view white-space-pre-wrap break-words ember-view"]/span[1]'
        text = div.find_element_by_xpath(xpath).text

        try:
            xpath_img = './/*[@class="feed-shared-article__meta flex-grow-1 full-width tap-target app-aware-link ember-view"]'
            link = div.find_element_by_xpath(xpath_img).get_attribute("href")
        except NoSuchElementException:
            link = ''
        link_tag = f'<br><a href = {link}></a>'
        text = text.encode('utf-8', errors='ignore').decode('utf-8')
        text = text+link_tag

        return text

    @staticmethod
    def get_likes_qty(div: webdriver) -> int:
        try:
            likes_xpath = './/*[@data-control-name="likes_count"]'
            qty_xpath = './/*[@class="v-align-middle social-details-social-counts__reactions-count"]'
            likes_button = div.find_element_by_xpath(likes_xpath)
            qty_likes = likes_button.find_element_by_xpath(qty_xpath).text
            qty_likes = qty_likes.replace(',', '')
        except NoSuchElementException:
            qty_likes = 0
        return int(qty_likes)

    @staticmethod
    def get_comments_qty(div: webdriver) -> int:
        try:
            comments_xpath = './/*[@data-control-name="comments_count"]/span'
            comments_text = div.find_element_by_xpath(comments_xpath).text
            comments_qty = re.findall('\d+', comments_text)[0]
        except NoSuchElementException:
            comments_qty = 0
        return int(comments_qty)

    @staticmethod
    def get_post_isodate(timestamp: int) -> str:
        return arrow.get(timestamp).isoformat()

    @staticmethod
    def get_language(text: str) -> str:
        try:
            language = detect(text)
        except:
            language = 'en'
        return language


def scrapping():
    data = pd.read_csv(f'./csv/{CSV_PATH}', sep=';')
    chan_list = pd.DataFrame(data, columns=['news_chan_list'])

    linkedin_bot = LinkedInPy(LOGIN, PASSWORD)
    linkedin_bot.start_driver_session()
    linkedin_bot.login_to_linkedin()
    loguru.logger.debug("Successfully Log In")

    for url in chan_list['news_chan_list']:
        posts = linkedin_bot.get_posts(last_posts_qty=int(MAX_POSTS),
                                       account_url=url)
        results = linkedin_bot.collect_posts_info(posts)
        if not results:
            loguru.logger.exception("No Posts Found - Check Parser")
            continue
        for result in results:
            loguru.logger.debug("Status of upload: " + elastic_export(APISERVER,
                                                                  HTTP_LOGIN,
                                                                  HTTP_PASSWORD,
                                                                  PORT,
                                                                  MAINCOLLECTION,
                                                                  MAININDEX,
                                                                  result))

        time.sleep(3)
    loguru.logger.debug("Successful Accounts Parsing")

    try:
        loguru.logger.debug("Session End Properly")
        linkedin_bot.driver.quit()
    except WebDriverException:
        loguru.logger.debug("Session Not End Properly")


def periodic_scrapping():
    try:
        scrapping()
    except:
        loguru.logger.exception('PERIODIC ------ LINKEDIN')
    loguru.logger.debug('Sleeping time -_- zzzzzz')
    time.sleep(random.randint(SLEEPING_TIME[0], SLEEPING_TIME[1]))


def elastic_export(apiserver, http_login, http_password, port, searchindex,
                   thisdoctype, newsbody):
    # Index by Elastic
    es = Elasticsearch([apiserver], http_auth=(http_login, http_password), port=port)

    if newsbody:
        try:
            es.create(index=searchindex, doc_type=thisdoctype, body=newsbody, id=newsbody['id'])
        except:
            try:
                loguru.logger.debug('Already exist in Elastic')
                print('Id = ' + newsbody['id'] + ' was upload \n')
            except:
                loguru.logger.exception('Export to elastic')
                return 'bad'
    return 'ok'

if __name__ == '__main__':

    loguru.logger.add("logsfiles/" + OUT_LOG, backtrace=False)

    while True:
        periodic_scrapping()
