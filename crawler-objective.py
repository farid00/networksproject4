#!/usr/bin/env python 
import sys 
import socket
import textwrap
from urlparse import urlparse
from HTMLParser import HTMLParser
import re
import time
import binascii

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
                        if value not in self.LinksVisitted and value not in self.LinksToVisit:
                            self.LinksToVisit.append(value)

    def handle_data(self, data):
            if 'FLAG' in data:
                print "!!!!!!!!!!!!!!"
                self.Flags.append(data.split("FLAG: ", 1)[1])



class WebCrawler():
    def __init__(self, username, password):
        # these can probably be sets
        self.LinksToVisit = []
        self.LinksVisitted = []
        self.Flags = []
        self.username = username
        self.password = password


        self.parser = linkParser(LinksToVisit=self.LinksToVisit, LinksVisitted=self.LinksVisitted, Flags=self.Flags)
        self.sock = socket.socket()
        self.sock.connect(("fring.ccs.neu.edu", 80))

    def crawl(self):
        home_page = "GET /accounts/login/ HTTP/1.1\r\nHost: fring.ccs.neu.edu\r\n\r\n"
        self.sock.send(home_page)
        response = self.sock.recv(4096)
        response = self.compile_response(response)
        cookies = self.parse_cookies(response)
        cookie_string = self.make_cookie_string(cookies)
        login_string = self.make_login_string(cookie_string, cookies['csrftoken'])
        self.sock.send(login_string)
        response = self.sock.recv(4096)
        # TODO: ??????? should this return something? below
        self.compile_response(response)
        cookies = self.parse_cookies(response)
        cookie_string = self.make_cookie_string(cookies)
        resp, statuscode = self.make_get_request(url_to_get='/fakebook/', cookie_string=cookie_string)
        self.parser.feed(resp)
        is_closed = False



        if not self.LinksToVisit:
            print 'NO LINKS AT START COULD NOT CRAWL'

        while self.LinksToVisit:
            NextUrl = self.LinksToVisit[0]
            print NextUrl

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
                if redirecturl not in self.LinksVisitted and redirecturl not in self.LinksToVisit:
                    self.LinksToVisit.insert(0, redirecturl)
            elif int(sc) == 403:
                print '403 error, abandoning url'

            # print http_response
            self.LinksVisitted.append(NextUrl)
            self.LinksToVisit.pop(0)

            if http_response:
                self.parser.feed(http_response)
            if is_closed:
                self.sock = socket.socket()
                self.sock.connect(("fring.ccs.neu.edu", 80))
                is_closed = False

        if self.FLAGS:
            print "FLAGS:"
            for flag in self.FLAGS:
                print flag
        else:
            print 'NO FLAGS FOUND'


    #Parse out the cookies from the HTTP response
    def recvall(self, length_left):
        length_left = length_left
        response = ""
        while True:
            if length_left > 0:
                new_response = self.sock.recv(length_left)
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
                #is this the first packet?

                if current_response.find('Content-Type') > 0:
                    m = re.search(r"(?<=\r\n\r\n)[0-9A-Fa-f]*(?=\r\n)", current_response)
                else:
                    m = re.search(r"[0-9A-Fa-f]*(?=\r\n)", current_response)
                if int(m.group(0), 16) == 0:
                    return reassembled_response
                #add 2 because of the final carriage return and line return on chunk
                chunk_length = int(m.group(0), 16)
                #split on the clrf number
                body_response = response.split(m.group(0) + '\r\n')[1]
                length_left = chunk_length - len(body_response)
                if length_left > 0:
                    length_left += 2
                if length_left < -2:
                    return body_response
                new_response = self.recvall(length_left)
                body_response += new_response
                # print '**********************'
                # print str(chunk_length)
                # print str(len(body_response))
                # print length_left
                # print repr(current_response)
                # print '**********************'
                reassembled_response += body_response
                current_response = self.sock.recv(4096)
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
                        Referer: http://fring.ccs.neu.edu/accounts/login/?next=/fakebook/b
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

        response = self.sock.recv(4096)
        status_code = self.get_status_code(response)

        response = self.compile_response(response)
        return (response, status_code)

    def get_status_code(self, response):
        return response.split()[1]


def main():
    #TODO: login with command line args

    # Isaac's credentials 
    username = "001939560"
    password = "66H5YT05"

    # Matt's credientials
    # username = "001968841"
    # password = "LG56YYQK"
    crawler = WebCrawler(username=username, password=password)
    crawler.crawl()

    


if __name__ == "__main__":
    main()