# -*- coding: utf-8 -*-

import os
import re
import sys
import time
import pickle
import pprint
import platform

from datetime import datetime, timedelta
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException

class LinkedInPy():

    """
        Class, allows to create a selenium chromedriver object and 
        parse users posts.
        As arguments, it accepts the linkedin user account name for parsing, 
        and the login and password of the account through which parsing takes place.
    """

    def __init__(self, account, login, password):
        self.account = account
        self.login = login
        self.password = password
        
        self.script_dir = os.getcwd()
        self.driver_path = self.get_system_chromedriver()
        
        self.linkedin_url = 'https://www.linkedin.com/'
        self.login_url = '{0}login'.format(self.linkedin_url)
        self.owner_url = '{0}in/{1}/'.format(self.linkedin_url, self.account)
        self.owner_posts_url = '{0}detail/recent-activity/shares/'.format(self.owner_url)
        
        self.driver = None

    def get_system_chromedriver(self):

        """ 
            The method takes script directory as argument and depending on 
            the OS, determines the Chrome driver file and, if it exists 
            in the working directory, returns the absolute path to it. 
        """

        os_system = platform.system()
        if os_system == 'Linux':
            chrome_driver = 'chromedriver_linux_64'
        elif os_system == 'Windows':
            chrome_driver = 'chromedriver.exe'
        elif os_system == 'Darwin':
            chrome_driver = 'chromedriver_mac_64'
        else:
            print('Chrome driver is not supported on your OS!')
            e = input('Press any button to exit...')
            sys.exit()

        driver_path = os.path.join(self.script_dir, chrome_driver)
        if os.path.isfile(driver_path):
            return driver_path
        else:
            print('Chrome driver is not exist in working directory: "{0}"'.format(script_dir))
            e = input('Press any button to exit...')
            sys.exit()

    def start_driver_session(self):

        """ 
            The method initializes selenium chrome driver with options 
            and return driver object.
        """
        
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--ignore-certificate-errors")
            options.add_argument("--test-type")
            options.add_argument("--no-sandbox")
            self.driver = webdriver.Chrome( options=options, 
                                            executable_path=self.driver_path)
        except:
            print('Can init Chrome Web Driver')
            print(sys.exc_info())
            sys.exit()
        return

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

        cookie_file = os.path.join(self.script_dir, 'cookiefile')

        if os.path.isfile(cookie_file):
            self.driver.get(self.linkedin_url)
            cookies = pickle.load(open(cookie_file, "rb"))
            for cookie in cookies:
                # Cookie "expiry" needs to keep session active. 
                # This is date in timestamp format
                # Date should be at least one year longer
                today = datetime.now()
                yeartoday = today + timedelta(days=365)
                yeartimestamp = time.mktime(yeartoday.timetuple())
                cookie['expiry'] = yeartimestamp
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

                self.driver.find_element_by_xpath('//*[@id="app__container"]/main/div/form/div[3]/button').click()
                
                # After login save cookies as python object to the pickle file
                pickle.dump(self.driver.get_cookies(), open(cookie_file, 'wb'))
            except NoSuchElementException:
                print('\n-------------------- ERROR ------------------------\n')
                print('On Login Page ( "{}" )\ndriver cant find element.\n'.format(self.login_url))
                print('Check manually if the page opens!\nOr check internet connection!\n')
                print('---------------------------------------------------\n')
                self.driver.quit()
                sys.exit()
        return

    def get_posts(self, last_posts_qty=None):

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

        # Open page with posts for account
        self.driver.get(self.owner_posts_url)
        
        # Get start page height coord to scroll
        scroll_height_func = 'return document.body.scrollHeight'
        start_page_height = self.driver.execute_script(scroll_height_func)
        
        flag = True
        start_div = 0
        all_posts_divs = []
        
        while flag:
            visible_divs = self.get_list_post_divs()
            qty_visible_divs = len(visible_divs)
            
            all_posts_divs.extend(visible_divs[start_div:qty_visible_divs])
  
            divs_qty = len(all_posts_divs)
            
         
            if last_posts_qty and divs_qty >= last_posts_qty:
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

    def collect_posts_info(self, all_posts_divs):
        
        """ Parse post divs and collect info from it """
        
        posts = []
        for div in all_posts_divs:
            post_dict = {}
            post_dict['owner_url'] = self.owner_url
            post_dict['owner'] = self.get_author(div)
            post_dict['timestamp'] = self.get_post_timestamp(div)
            post_dict['text'] = self.get_post_text(div)
            post_dict['url'] = self.get_post_url(div)
            post_dict['likes'] = self.get_likes_qty(div)
            post_dict['comments'] = self.get_comments_qty(div)
            posts.append(post_dict)
        self.driver.quit()
        return posts

    def scroll_page(self, scroll_height_func):
        self.driver.execute_script('window.scrollTo(0, \
                                            document.body.scrollHeight);')
        time.sleep(3)
        return self.driver.execute_script(scroll_height_func)

    def get_list_post_divs(self):
        try:
            div_xpath = '//div[@class="occludable-update ember-view"]'
            return self.driver.find_elements_by_xpath(div_xpath)
        except NoSuchElementException:
            print('This account dont have a posts.')
            self.driver.quit()
            sys.exit()

    def get_post_url(self, div):
        try:
            # Find "more" button in post div, scroll to it and click.
            #btn_xpath = './/artdeco-dropdown'
            #copy_btn_xpath = './/*[@class="option-share-via"]'
            url_xpath = './/*[@class="artdeco-toast-item__cta"]'
            
            copy_btn_tag = 'artdeco-dropdown-item'
            js_copy_btn_click = 'arguments[0].getElementsByTagName("{0}")[0].click();'.format(copy_btn_tag)
            self.driver.execute_script(js_copy_btn_click, div)
            
            return self.driver.find_element_by_xpath(url_xpath).get_attribute("href")
        except NoSuchElementException:
            return 'NoPostUrl'

    @staticmethod
    def get_author(div):
        try:
            xpath = './/*[@data-control-name="actor"]/h3/span/span[@dir="ltr"]'
            return div.find_element_by_xpath(xpath).text
        except NoSuchElementException:
            return 'NoAuthor'
    
    @staticmethod
    def get_post_timestamp(div):
        try:
            xpath = './/*[@class="feed-shared-actor__sub-description t-12 t-black--light t-normal"]/div/span[1]'
            time_period_str = div.find_element_by_xpath(xpath).text.lower()
            # Sometimes post date seems like "Published • 6mo", 
            # or "3w • Edited".
            split_period = time_period_str.split(' ')
            period = None
            qty_period = None
            for p in split_period:
                qty_period = re.findall('\d+', p)
                if qty_period:
                    qty_period = qty_period[0]
                    period = re.findall('\D+', p)[0]
                    break

            today = datetime.now()
            if period == 'h':
                post_date = today - timedelta(hours=int(qty_period))
            elif period == 'd':
                post_date = today - timedelta(days=int(qty_period))
            elif period == 'w':
                post_date = today - timedelta(weeks=int(qty_period))
            elif period == 'mo':
                post_date = today - timedelta(days=int(qty_period)*30)
            elif period == 'yr':
                post_date = today - timedelta(days=int(qty_period)*365)
            return time.mktime(post_date.timetuple())
        except NoSuchElementException:
            return 'NoPostDate'

    @staticmethod
    def get_post_text(div):
        try:
            xpath = './/*[@class="feed-shared-text__text-view feed-shared-text-view white-space-pre-wrap break-words ember-view"]/span[1]'
            return div.find_element_by_xpath(xpath).text
        except NoSuchElementException:
            return 'NoText'

    @staticmethod
    def get_likes_qty(div):
        try:
            likes_xpath = './/*[@data-control-name="likes_count"]'
            qty_xpath = './/*[@class="v-align-middle social-details-social-counts__reactions-count"]'
            likes_button = div.find_element_by_xpath(likes_xpath)
            qty_likes = likes_button.find_element_by_xpath(qty_xpath).text
        except NoSuchElementException:
            qty_likes = 0
        return int(qty_likes)

    @staticmethod
    def get_comments_qty(div):
        try:
            comments_xpath = './/*[@data-control-name="comments_count"]/span'
            comments_text = div.find_element_by_xpath(comments_xpath).text
            comments_qty = re.findall('\d+', comments_text)[0]
        except NoSuchElementException:
            comments_qty = 0
        return int(comments_qty)


if __name__ == '__main__':

    account = ''
    login = ''
    password = ''
    post_qty = None
    
    linkedin_bot  = LinkedInPy(account, login, password)
    linkedin_bot.start_driver_session()
    linkedin_bot.login_to_linkedin()

    posts = linkedin_bot.get_posts(last_posts_qty=post_qty)
    results = linkedin_bot.collect_posts_info(posts)

    pprint.pprint(results)
