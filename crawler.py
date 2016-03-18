#!/usr/bin/env python 
import sys 
import socket
import textwrap
from HTMLParser import HTMLParser
#Parse out links from HTTP response
class linkParser(HTMLParser):
	def handle_starttag(self, tag, attrs):
		link_list = []
		if tag == "a":
			for name, value in attrs:
				if name == "href":
					print value
					link_list.append(value)
#Parse out the cookies from the HTTP response

def compile_response(response):
	if response.find('chunked'):
		for item in response.split('\n'):
			if str(item).isdigit():
				print item
		


def parse_cookies(response):
	cookie_dictionary = {}
	for item in response.split("\n"):
		if "Set-Cookie" in item:
			cookie = item.split()[1]
			cookie = cookie[:-1]
			cookie = cookie.split('=')
			cookie_name = cookie[0]
			cookie_value = cookie[1]
			cookie_dictionary[cookie_name] = cookie_value
			print cookie
	return cookie_dictionary

def make_login_string(cookie_string, csrfmiddlewaretoken):
	username = "001968841"
	password = "LG56YYQK"
	login_string = """
					POST /accounts/login/ HTTP/1.1
					Host: fring.ccs.neu.edu
					Referer: http://fring.ccs.neu.edu/accounts/login/?next=/fakebook/b
					Content-Type: application/x-www-form-urlencoded
					Content-Length: 95
					Origin: http://fring.ccs.neu.edu
					Cookie: %s 

					username=%s&password=%s&csrfmiddlewaretoken=%s&next=

					"""
	print textwrap.dedent(login_string % (cookie_string, username, password, csrfmiddlewaretoken))
	return textwrap.dedent(login_string % (cookie_string, username, password, csrfmiddlewaretoken))
def connect():
	s = socket.socket()
	s.connect(("fring.ccs.neu.edu", 80))
	return s 


def make_cookie_string(cookie_dictionary):
	myCS = ""
	for key, value in cookie_dictionary.iteritems():
		current_str = "%s=%s; "
		current_str = current_str % (key, value)
		myCS += current_str
	return myCS[:-1]



def make_get_request(cookie_string, url_to_get, dum):
	request_string = """
					GET /fakebook/ HTTP/1.1
					Host: fring.ccs.neu.edu
					Pragma: no-cache
					Cache-Control: no-cache
					Cookie: %s

					"""
	request_string = textwrap.dedent(request_string % (cookie_string))
	print request_string
	dum.sendall(request_string)
	response = dum.recv(10000)
	print response
	# print response

def main():
	parser = linkParser()
	s = connect()
	home_page = "GET /accounts/login/?next=/fakebook/ HTTP/1.1\r\nHost: fring.ccs.neu.edu\r\n\r\n"
	s.send(home_page)
	response = s.recv(10000)
	compile_response(response)
	cookies = parse_cookies(response)
	links = parser.feed(response)
	cookie_string = make_cookie_string(cookies)
	login_string = make_login_string(cookie_string, cookies['csrftoken'])
	s.send(login_string)
	response = s.recv(10000)
	print response
	cookies = parse_cookies(response)
	cookie_string = make_cookie_string(cookies)
	make_get_request(cookie_string, '/fakebook/', s)

if __name__ == "__main__":
	main()