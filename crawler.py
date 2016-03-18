#!/usr/bin/env python 
import sys 
import socket
import textwrap
from urlparse import urlparse
from HTMLParser import HTMLParser
import re
import time
import binascii
#Parse out links from HTTP response

# these can probably be sets
LinksToVisit = []
LinksVisitted =[]
FLAGS = []

class linkParser(HTMLParser):
	def handle_starttag(self, tag, attrs):
		if tag == 'a':
			for attr, value in attrs:
				if attr == 'href':
					url = urlparse(value)
					# domain in case its an absolute url thats probably still fine
					if not url.scheme or url.scheme == 'http://fring.ccs.neu.edu/':
						if value not in LinksVisitted and value not in LinksToVisit:
							LinksToVisit.append(value)

	def handle_data(self, data):
            # <h2 class='secret_flag' style="color:red">FLAG: 64-characters-of-random-alphanumerics</h2>
            if 'FLAG:' in data:
                FLAGS.append(data.split("FLAG: ",1)[1])
            # it may be better to only do the check in an h2 tag but handle_starttag doesnt have any data in it so idk

#Parse out the cookies from the HTTP response
def recvall(length_left, my_socket):
	length_left = length_left
	response = ""
	while True:
		if length_left > 0:
			new_response = my_socket.recv(length_left)
			length_left = length_left - len(new_response)
			print str(len(new_response)) + ' new length'
			print str(length_left) + 'length left'
			response += new_response
		else:
			return response

def compile_response(response, s):
	if response.find('chunked') > 0:
		print response
		current_response = response
		reassembled_response = ""
		while True:
			#is this the first packet?
			if current_response.find('Content-Type') > 0:
				m = re.search(r"(?<=\r\n\r\n)[0-9A-Fa-f]*(?=\r\n)", current_response)
			else:
				print repr(current_response)
				m = re.search(r"[0-9A-Fa-f]*(?=\r\n)", current_response)
			if int(m.group(0), 16) == 0:
				return reassembled_response
			#add 2 because of the final carriage return and line return on chunk
			chunk_length = int(m.group(0), 16) + 2
			#split on the clrf number
			body_response = response.split(m.group(0) + '\r\n')[1]
			length_left = chunk_length - len(body_response)
			new_response = recvall(length_left, s)
			body_response += new_response

			reassembled_response += body_response
			current_response = s.recv(4096)
	else:
		response = response
		total_length = re.search(r"(?<=Content-Length: )\d+", response)
		body_response = re.search(r"(?<=\r\n\r\n).*", response, re.DOTALL)
		length_left = int(total_length.group(0)) - int(len(body_response.group(0)))
		response += recvall(length_left, s)
		return response
		

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

	return cookie_dictionary

def make_login_string(cookie_string, csrfmiddlewaretoken):
	# Isaac's credentials 
	# UN: 001939560
	# PW: 66H5YT05

	username = "001968841"
	password = "LG56YYQK"
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

	login_string = login_string.format(cookie_string, username, password, csrfmiddlewaretoken)
	return textwrap.dedent(login_string)


def make_cookie_string(cookie_dictionary):
	myCS = ""
	for key, value in cookie_dictionary.iteritems():
		current_str = "%s=%s; "
		current_str = current_str % (key, value)
		myCS += current_str

	return myCS[:-1]


def make_get_request(url_to_get, cookie_string, sock):
	request_string = """
					GET {} HTTP/1.1
					Host: fring.ccs.neu.edu
					Pragma: no-cache
					Cache-Control: no-cache
					Cookie: {}

					"""
	request_string = textwrap.dedent(request_string.format(url_to_get, cookie_string))
	sock.sendall(request_string)

	response = sock.recv(4096)
	return response


def main():
	parser = linkParser()
	s = socket.socket()
	s.connect(("fring.ccs.neu.edu", 80))

	home_page = "GET /accounts/login/?next=/fakebook/ HTTP/1.1\r\nHost: fring.ccs.neu.edu\r\n\r\n"
	s.send(home_page)
	response = s.recv(4096)
	response = compile_response(response, s)
	cookies = parse_cookies(response)
	cookie_string = make_cookie_string(cookies)
	login_string = make_login_string(cookie_string, cookies['csrftoken'])
	s.send(login_string)
	response = s.recv(4096)
	compile_response(response, s)
	cookies = parse_cookies(response)
	cookie_string = make_cookie_string(cookies)
	resp = make_get_request(url_to_get='/fakebook/', cookie_string=cookie_string, sock=s)
	resp = compile_response(resp, s)
	parser.feed(resp)



	if not LinksToVisit:
		print 'NO LINKS AT START COULD NOT CRAWL'

	while LinksToVisit:
		NextUrl = LinksToVisit[0]
		print NextUrl
        # s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  
        # s.connect((domain, 80))
        # s.sendall("GET {} HTTP/1.1\r\nHost: {} \r\n\r\n".format(NextUrl, domain))

        #cookie string shouldnt change except maybe the csrf will but idk if thats neccesary
		http_response = make_get_request(url_to_get=NextUrl, cookie_string=cookie_string, sock=s);
		http_response = compile_response(http_response, s)
		# print http_response
		LinksVisitted.append(NextUrl)

		parser.feed(http_response)
		LinksToVisit.pop(0)

	if FLAGS:
		print "FLAGS:"
		for flag in FLAGS:
			print flag
	else:
		print 'NO FLAGS FOUND'


if __name__ == "__main__":
	main()