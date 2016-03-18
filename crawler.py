#!/usr/bin/env python 
import sys 
import socket
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

def login():
	username = "001968841"
	password = "LG56YYQK"
def connect():
	s = socket.socket()
	s.connect(("fring.ccs.neu.edu", 80))
	return s 
def main():
	parser = linkParser()
	s = connect()
	home_page = "GET /accounts/login/?next=/fakebook/ HTTP/1.1\r\nHost: fring.ccs.neu.edu\r\n\r\n"
	s.send(home_page)
	response = s.recv(4096)
	parse_cookies(response)
	parser.feed(response)

if __name__ == "__main__":
	main()