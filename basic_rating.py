from datetime import datetime
import logging
from math import ceil
from lxml import etree
from pymongo import MongoClient
from crawler import Spider, Crawler, Job

__author__ = 'nonamenix'

from requests import Session
from utils import Timer
from itertools import product

logging.basicConfig(level='DEBUG')
import sys


class BasicRatingSpider(Spider):
    PAGE_INFO_TOTAL = 'data-total'
    PAGE_INFO_OFFSET = 'data-offset'
    PAGE_INFO_DISPLAYED = 'data-displayed'
    PAGE_INFO_QUERY = 'data-query'

    available_realms = ['ru', 'com', 'asia', 'eu']
    base_search_url = "http://worldofwarships.%(realm)s/cbt/accounts/search/"

    default_headers = {
        'User-Agent': 'WOWS Rating Scanner',
        'X-Requested-With': 'XMLHttpRequest',


    }

    def _generate_jobs(self):
        return [Job(url=self.search_url, params={'search': query}) for query in self.queries]

    def _get_queries(self):
        products = product('abcdefghijklmnopqrstuvwxyz1234567890_', repeat=3)
        return [''.join(query) for query in products]

    def __init__(self, session_id, realm, *args, **kwargs):
        super(BasicRatingSpider, self).__init__(*args, **kwargs)

        self.session_id = session_id
        self.session = Session()
        self.session.headers.update(self.default_headers)
        self.session.cookies.update({
            'sessionid': session_id,
        })

        if realm in self.available_realms:
            self.realm = realm
            self.search_url = self.base_search_url % {'realm': realm}
            self.default_headers['Referer'] = self.search_url
            self.default_headers['Host'] = 'worldofwarships.%s' % self.realm,
        else:
            raise Exception("Bad realm")

        self.queries = self._get_queries()
        self.client = MongoClient()
        self.db = self.client['rating']
        self.leaderboard = self.db['leaderboard']

        self.jobs = self._generate_jobs()

    def _process_user_table_rows(self, rows):
        """
        Create user basic statistic in database

        :param rows: etree nodes
        """
        for row in rows:
            children = row.getchildren()
            spa_id = row.attrib.values()[0]
            characteristics = [child.text or child.getchildren()[0].text for child in children]
            user = {
                'user': characteristics[1],
                'battles': int(characteristics[2]),
                'victories': int(characteristics[3]),
                'experience': int(characteristics[4]),
                'spa_id': int(spa_id),
                'updated_at': datetime.utcnow(),
                'realm': self.realm
            }
            user['vpb'] = round(float(user['victories']) / user['battles'] if user['battles'] else 0, 4) * 100

            self.leaderboard.insert_one(user)

    def _add_extra_pages(self, job, page_info):
        """

        :param job:
        :param page_info:
        :return:
        """
        if int(page_info[self.PAGE_INFO_TOTAL]) > 0 and int(page_info[self.PAGE_INFO_OFFSET]) == 0:
            # Add jobs for next pages
            pages_count = int(ceil(float(page_info[self.PAGE_INFO_TOTAL]) / float(page_info[self.PAGE_INFO_DISPLAYED])))
            extra_page_numbers = range(2, pages_count + 1)
            for page_number in extra_page_numbers:
                params = {
                    'search': job.params['search'],
                    'page': page_number
                }
                self.crawler.add_job(
                    Job(url=job.url, params=params)
                )

    def _process_search_page_result(self, job):
        doc = etree.fromstring(job.response.text, parser=etree.HTMLParser(recover=True))
        page_info = doc.xpath('//*[@class="js-accounts-search"]')[0].attrib
        self._process_user_table_rows(doc.xpath('//table/tbody/tr'))
        self._add_extra_pages(job, page_info)

    def preprocess(self, job):
        logger = logging.getLogger(__name__ + '.preprocess')
        logger.info(job)

    def postprocess(self, job):
        logger = logging.getLogger(__name__ + '.postprocess')
        print self.crawler.jobq.qsize(), job

        self._process_search_page_result(job)


if __name__ == '__main__':
    with Timer():
        session = sys.argv[1]
        realm = sys.argv[2]

        spider = BasicRatingSpider(session, realm=realm)
        Crawler(spider).start()

