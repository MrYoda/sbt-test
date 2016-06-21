import csv
import logging
import argparse
import random
from collections import defaultdict

import tornado.httpclient
import tornado.ioloop
import tornado.web
import tornado.gen


CONFIG_FILENAME = 'config.csv'
GET_PARAM_NAME = 'category[]'


class MainHandler(tornado.web.RequestHandler):
    @tornado.gen.coroutine
    def get(self, *args, **kwargs):
        # get request categories
        request_categories = self.get_request_categories()

        # get available banners
        available_banners = self.get_available_banners_for_categories(
            request_categories
        )
        if available_banners:
            # choose banner for show
            target_banner = self.choose_banner(available_banners)

            # prepare and show banner
            self.output_banner(target_banner)
        else:
            self.banner_not_found()

        # finalize
        self.finish()

    def get_request_categories(self):
        """ Returns list of requested categories
        """
        return [category.decode() for category
                in self.request.arguments.get(GET_PARAM_NAME, [])]

    def get_available_banners_for_categories(self, categories):
        """ Returns available banners for categories
        """
        # get unique list of available banners in request categories
        if categories:  # banners only in these categories
            available_banners = [banner_url for category in categories
                                 for banner_url in self.application.banner_categories[category]]
            available_banners = list(set(available_banners))
        else:  # all banners
            available_banners = self.application.banner_urls

        # filter available banners by positive available show count
        available_banners = [banner_url for banner_url in available_banners
                             if self.application.banner_shows[banner_url] > 0]

        # check if last banner may be removed from available banners
        last_banner = self.application.get_last_banner(self.request.remote_ip)
        if last_banner and last_banner in available_banners:
            if len(available_banners) > 1:  # remove last banner if available more than one
                available_banners.remove(last_banner)
        return available_banners

    @staticmethod
    def choose_banner(banners):
        """ Choose target banner from banner list
        """
        # simple random
        n = random.randint(0, len(banners)-1)
        return banners[n]

    def output_banner(self, banner_url):
        """ Outputs banner html
        """
        html = self.banner_wrapper(banner_url)
        self.write(html)
        # decrease banner shows
        self.application.banner_shows[banner_url] -= 1
        # set last banner for current ip
        self.application.set_last_banner(self.request.remote_ip, banner_url)

    @staticmethod
    def banner_wrapper(banner_url):
        """ Wraps banner into html for response
        """
        # so simple
        return '{url}<img src="{url}" alt="{alt}">'.format(
            url=banner_url,
            alt='Banner'
        )

    def banner_not_found(self):
        """ Set 404 NOT FOUND
        """
        self.set_status(404)
        self.write('Not found')


class Application(tornado.web.Application):
    """ Banners application
    """
    def __init__(self, handlers=None, default_host="", transforms=None,
                 **settings):
        super().__init__(handlers, default_host, transforms, **settings)
        self.banner_urls = list()
        self.banner_shows = dict()
        self.banner_categories = defaultdict(list)
        self.read_config()

        self.last_banners = dict()  # dict {ip: banner_url}

    def read_config(self):
        """ Reads config from CSV and stores in data structures
        """
        with open(CONFIG_FILENAME, newline='') as f:
            reader = csv.reader(f, delimiter=';')
            for row in reader:
                url = row[0]
                shows = int(row[1])
                categories = row[2:]
                self.banner_urls.append(url)
                for category in categories:
                    self.banner_categories[category].append(url)
                self.banner_shows[url] = shows

    def get_last_banner(self, ip):
        """ Return last showed banner by IP
        """
        return self.last_banners.get(ip)

    def set_last_banner(self, ip, banner_url):
        """ Set last showed banner by IP
        """
        self.last_banners[ip] = banner_url


def parse_args():
    """ Parses arguments and return its values """
    argparser = argparse.ArgumentParser()
    argparser.add_argument('--host', help='Server host')
    argparser.add_argument('--port', type=int, help='Server port', default=8080)
    return argparser.parse_args()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    server_args = parse_args()
    logging.debug('Server running with arguments: %s', server_args)

    app = Application([
        (r'/', MainHandler),
    ])
    app.listen(server_args.port, address=server_args.host)
    tornado.ioloop.IOLoop.current().start()
