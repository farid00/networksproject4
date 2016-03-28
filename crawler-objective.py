#!/usr/bin/env python 
import sys 
import socket
import textwrap
from urlparse import urlparse
from HTMLParser import HTMLParser
import re
import time
import binascii
import Queue
import threading
import select
cond = threading.Condition()
Flags = []
SESSION = ''

class SetQueue(Queue.Queue):

    def _init(self, maxsize):
        self.maxsize = maxsize
        self.queue = set()

    def _put(self, item):
        self.queue.add(item)

    def _get(self):
        return self.queue.pop()

class linkParser(HTMLParser):
    def __init__(self, LinksToVisit, LinksVisitted, Flags):
        self.LinksToVisit = LinksToVisit
        self.LinksVisitted = LinksVisitted
        self.Flags = Flags
        HTMLParser.__init__(self)



    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for attr, value in attrs:
                if attr == 'href':
                    url = urlparse(value)
                    # domain in case its an absolute url thats probably still fine
                    if not url.scheme or url.scheme == 'fring.ccs.neu.edu':
                        if value not in self.LinksVisitted.queue and value not in self.LinksToVisit.queue:
                            self.LinksToVisit.put(value)

    def handle_data(self, data):
        global Flags
        if 'FLAG' in data:
            for a in range (0, 30):
                print "!!!!!!!!!!!!!!"
            Flags.append(data.split("FLAG: ", 1)[1])



class WebCrawler():
    def __init__(self, username, password, LinksVisitted, LinksToVisit):
        # these can probably be sets
        self.LinksVisitted = LinksVisitted
        self.Flags = []
        self.username = username
        self.password = password
        self.LinksToVisit = LinksToVisit


        self.parser = linkParser(LinksToVisit=self.LinksToVisit, LinksVisitted=self.LinksVisitted, Flags=self.Flags)
        self.sock = socket.socket()
        self.sock.connect(("fring.ccs.neu.edu", 80))
        self.sock.setblocking(0)

    def crawl(self):
        global SESSION
        cookies = {}

        home_page = "GET /accounts/login/ HTTP/1.1\r\nHost: fring.ccs.neu.edu\r\n\r\n"
        while not cookies.get('csrftoken'):
            self.sock.send(home_page)
            response = self.safe_recv(4096)
            response = self.compile_response(response)
            cookies = self.parse_cookies(response)
            cookie_string = self.make_cookie_string(cookies)
        login_string = self.make_login_string(cookie_string, cookies.get('csrftoken'))
        self.sock.send(login_string)
        response = self.safe_recv(4096)
        cookies = self.parse_cookies(response)
        cookie_string = self.make_cookie_string(cookies)
        SESSION = cookie_string
        resp, statuscode = self.make_get_request(url_to_get='/fakebook/', cookie_string=cookie_string)
        self.parser.feed(resp)
        is_closed = False



        if not self.LinksToVisit:
            print 'NO LINKS AT START COULD NOT CRAWL'

        while not self.LinksToVisit.empty():
            try:
                NextUrl = str(self.LinksToVisit.get(0))
            except:
                continue
            print "*****{} {} {}*****".format(NextUrl.ljust(40), str(self.LinksToVisit.qsize()).ljust(40), str(self.LinksVisitted.qsize()).ljust(40))

            #cookie string shouldnt change except maybe the csrf will but idk if thats neccesary
            (http_response, sc) = self.make_get_request(url_to_get=NextUrl, cookie_string=cookie_string)
            if http_response.find("Connection: close") > -1:
                is_closed = True

            # should this be a while? if it 500's more than once shouldnt we keep trying?
            if int(sc) == 500:
                self.sock = socket.socket()
                self.sock.connect(("fring.ccs.neu.edu", 80))
                (http_response, sc) = self.make_get_request(url_to_get=NextUrl, cookie_string=cookie_string)
            elif int(sc) == 301:
                # TODO: this is a kind of wonky algorithm but it works
                redirecturl = http_response.split("Location: ",1)[1].split()[0]
                cond.acquire()
                if redirecturl not in self.LinksVisitted.queue and redirecturl not in self.LinksToVisit:
                    self.LinksToVisit.insert(redirecturl)
                    cond.notify()
                    cond.release()
            elif int(sc) == 403:
                print '403 error, abandoning url'

            self.LinksVisitted.put(NextUrl)

            if http_response:
                self.parser.feed(http_response)
            if is_closed:
                self.sock = socket.socket()
                self.sock.connect(("fring.ccs.neu.edu", 80))
                is_closed = False


    #Parse out the cookies from the HTTP response
    def recvall(self, length_left):
        length_left = length_left
        response = ""
        while True:
            if length_left > 0:
                new_response = self.safe_recv(4096)
                length_left = length_left - len(new_response)
                # print str(len(new_response)) + ' new length'
                # print str(length_left) + ' length left'
                response += new_response
            else:
                return response

    def compile_response(self, response):
        # print "$$$$$$$$$$$$$$$$$$$$$$$$"
        # print repr(response)
        # print "$$$$$$$$$$$$$$$$$$$$$$$$$"
        if response.find('chunked') > 0:

            current_response = response
            reassembled_response = ""
            while True:
                # if current_response.find('Content-Type') > 0:
                #     m = re.search(r"(?<=\r\n\r\n)[0-9A-Fa-f]*(?=\r\n)", current_response)
                # else:
                m = re.findall(r"(?<=\r\n)[0-9A-Fa-f]{3}(?=\r\n)|[0-9A-Fa-f]{1}(?=\r\n\r\n)", current_response)
                #add 2 because of the final carriage return and line return on chunk
                #split on the csrf number
                body_response = re.sub(r"(\r\n[0-9A-Fa-f]{3}\r\n)", '', current_response)
                reassembled_response += body_response
                if '0' in m:
                    return reassembled_response
                current_response = self.safe_recv(4096)
        else:
            response = response
            total_length = re.search(r"(?<=Content-Length: )\d+", response)
            body_response = re.search(r"(?<=\r\n\r\n).*", response, re.DOTALL)
            length_left = int(total_length.group(0)) - int(len(body_response.group(0)))
            response += self.recvall(length_left)
            return response
            

    def parse_cookies(self, response):
        cookie_dictionary = {}
        for item in response.split("\n"):
            if "Set-Cookie" in item:
                cookie = item.split()[1]
                cookie = cookie[:-1]
                cookie = cookie.split('=')
                cookie_name = cookie[0]
                cookie_value = cookie[1]
                cookie_dictionary[cookie_name] = cookie_value

        return cookie_dictionary

    def make_login_string(self, cookie_string, csrfmiddlewaretoken):
        login_string = """
                        POST /accounts/login/ HTTP/1.1
                        Host: fring.ccs.neu.edu
                        Referer: http://fring.ccs.neu.edu/accounts/login/?next=/fakebook/
                        Content-Type: application/x-www-form-urlencoded
                        Content-Length: 95
                        Origin: http://fring.ccs.neu.edu
                        Cookie: {} 

                        username={}&password={}&csrfmiddlewaretoken={}&next=

                        """

        login_string = login_string.format(cookie_string, self.username, self.password, csrfmiddlewaretoken)
        return textwrap.dedent(login_string)


    def make_cookie_string(self, cookie_dictionary):
        myCS = ""
        for key, value in cookie_dictionary.iteritems():
            current_str = "%s=%s; "
            current_str = current_str % (key, value)
            myCS += current_str

        return myCS[:-1]


    def make_get_request(self, url_to_get, cookie_string):
        request_string = """
                    GET {} HTTP/1.1
                    Host: fring.ccs.neu.edu
                    Pragma: no-cache
                    Cache-Control: no-cache
                    Cookie: {}
                    
                    """
        request_string = textwrap.dedent(request_string.format(url_to_get, cookie_string))
        self.sock.sendall(request_string)

        response = self.safe_recv(4096) 
        status_code = self.get_status_code(response)

        response = self.compile_response(response)
        return (response, status_code)

    def get_status_code(self, response):
        return response.split()[1]

    def print_flags(self):
        if self.Flags:
            print "FLAGS:"
            for flag in self.Flags:
                print flag
        else:
            print 'NO FLAGS FOUND'

    def safe_recv(self, length):
        try:
            read, write, other = select.select([self.sock], [], [])
            return read[0].recv(length)
        except Exception as e:
            # TODO: does this make sense? also check lack of use in recvall method im not sure it will work there.
            print 'connection reset by peer error'
            for a in range(0,30):
                print '&&&&&&&&&&&&'
            self.sock = socket.socket()


def print_flags():
    global Flags
    if Flags:
        print "FLAGS:"
        for flag in Flags:
            print flag
    else:
        print 'NO FLAGS FOUND'
def main(argv):
    LinksToVisit = SetQueue()
    LinksVisitted = SetQueue()
    if len(argv) >= 2:
        username = argv[0]
        password = argv[1]
    if len(argv) == 1:
        print 'error: incorrect number of arguments'
    else:

        # Isaac's credentials 
        username = "001939560"
        password = "66H5YT05"

        # Matt's credientials
        #username = "001968841"
        #password = "LG56YYQK"
        crawler = WebCrawler(username=username, password=password, LinksVisitted = LinksVisitted, LinksToVisit=LinksToVisit)
        crawler2 = WebCrawler(username=username, password=password, LinksVisitted = LinksVisitted, LinksToVisit=LinksToVisit)
        crawler3 = WebCrawler(username=username, password=password, LinksVisitted = LinksVisitted, LinksToVisit=LinksToVisit)
        crawler4 = WebCrawler(username=username, password=password, LinksVisitted = LinksVisitted, LinksToVisit=LinksToVisit)
        crawler5 = WebCrawler(username=username, password=password, LinksVisitted = LinksVisitted, LinksToVisit=LinksToVisit)
        crawler6 = WebCrawler(username=username, password=password, LinksVisitted = LinksVisitted, LinksToVisit=LinksToVisit)
        crawler7 = WebCrawler(username=username, password=password, LinksVisitted = LinksVisitted, LinksToVisit=LinksToVisit)
        crawler8 = WebCrawler(username=username, password=password, LinksVisitted = LinksVisitted, LinksToVisit=LinksToVisit)
        t1 = threading.Thread(target=crawler.crawl, args=[])
        t2 = threading.Thread(target=crawler2.crawl, args=[])
        t3 = threading.Thread(target=crawler3.crawl, args=[])
        t4 = threading.Thread(target=crawler4.crawl, args=[])
        t5 = threading.Thread(target=crawler5.crawl, args=[])
        t6 = threading.Thread(target=crawler6.crawl, args=[])
        t7 = threading.Thread(target=crawler7.crawl, args=[])
        t8 = threading.Thread(target=crawler8.crawl, args=[])
        t1.start()
        t2.start()
        t3.start()
        t4.start()
        t5.start()
        t6.start()
        t7.start()
        t8.start()
        t1.join()
        t2.join()
        t3.join()
        t4.join()
        t5.join()
        t6.join()
        t7.join()
        t8.join()
        print_flags()

if __name__ == "__main__":
    main(sys.argv[1:])


# TODO:
# last big error
# out of bounds when trying to get status code