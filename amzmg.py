#!/usr/bin/env python
from __future__ import print_function
import sys
import argparse
import requests
import json
import os.path
import time
import signal
from amzmgutil import config
from lxml import etree
from getpass import getpass
from pprint import pprint
from datetime import tzinfo, timedelta, datetime

def handler(sigNum, stackFrame):
	pass


parser = argparse.ArgumentParser(description='amzmg: Amazon MP3 getter for Linux')
parser.add_argument('-c', '--config-file', help='Path to alternate configuration file (default ~/.amzmg)')
parser.add_argument('--no-daemonize', action='store_const', const=1, default=0, help='Remain in the foreground and never daemonize')
opts = parser.parse_args()

configuration = config.load_configuration(opts.config_file)

auth_form_url = """https://www.amazon.com/gp/dmusic/cloud/mp3/webapp"""
authn_endpoint = """https://www.amazon.com/ap/signin"""

session = requests.Session()
session.headers = {'User-Agent': "amzmg/0.6"}

response = session.get(auth_form_url)

if response.status_code == 200:
	dom = etree.HTML(response.content)
	inputs = dom.xpath("//form[@action='" + authn_endpoint + "']//input")
	postfields = {}
	for elem in inputs:
		postfields[elem.attrib.get('name')] = elem.attrib.get('value')

	if not ("email" in postfields and "password" in postfields):
		print("Signin POST form not understood. Cannot log in.")
	else:
		authn_status = 0
		while authn_status != 302:
			postfields['email'] = config.prompt("Username", configuration['username'])
			postfields['password'] = getpass("Password: ")

			authn_response = session.post(authn_endpoint, data=postfields, allow_redirects=False)
			authn_status = authn_response.status_code
			if authn_status != 302:
				print ("Authentication failed, try again")

		app_data_response = session.get('https://www.amazon.com/gp/dmusic/mp3/player?ie=UTF8&ref_=dm_cp_m_redirect', headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.3; WOW64; Trident/7.0; Touch; rv:11.0) like Gecko'})
		dom = etree.HTML(app_data_response.content)
		scripts = dom.xpath("//script[not(@src)]")
		app_data = None
		for elem in scripts:
			script_code = elem.text
			config_pos = script_code.find('amznMusic.appConfig =')
			if config_pos != -1:
				#print(script_code)
				jparser = json.JSONDecoder()
				app_data = jparser.raw_decode(script_code[config_pos + 22:])
				app_data = app_data[0]

		if app_data is None:
			print("Failed to mine amznMusic.appConfig")
			sys.exit(0)

		#pprint(app_data)
		csrf_config = app_data['CSRFTokenConfig']
		csrf_headers = {'csrf-token': csrf_config['csrf_token'], 'csrf-rnd': csrf_config['csrf_rnd'], 'csrf-ts': csrf_config['csrf_ts']}

		# The main loop
		while True:
			new_purchase_params = {
				'customerInfo.customerId': app_data['customerId'],
				'customerInfo.deviceId': app_data['deviceId'],
				'customerInfo.deviceType': app_data['deviceType'],
				'ContentType': 'JSON',
				'countOnly': 'false',
				'maxResults': '500',
				'nextResultsToken': '0',
				'Operation': 'selectTracks',
				'columns.member.1': 'asin',
				'columns.member.2': 'albumAsin',
				'columns.member.3': 'contributors',
				'columns.member.4': 'title',
				'columns.member.5': 'albumName',
				'columns.member.6': 'albumArtistName',
				'columns.member.7': 'artistName',
				'columns.member.8': 'trackNum',
				'columns.member.9': 'discNum',
				'columns.member.10': 'creationDate',
				'columns.member.11': 'lastUpdatedDate',
				'columns.member.12': 'extension',
				'columns.member.13': 'size',
				'columns.member.14': 'duration',
				'columns.member.15': 'version',
				'columns.member.16': 'objectId',
				'columns.member.17': 'orderId',
				'columns.member.18': 'sortTitle',
				'columns.member.19': 'sortArtistName',
				'columns.member.20': 'sortAlbumArtistName',
				'columns.member.21': 'sortAlbumName',
				'columns.member.22': 'primaryGenre',
				'columns.member.23': 'assetType',
				'columns.member.24': 'albumReleaseDate',
				'columns.member.25': 'purchased',
				'getDirectAlbumArtDownloadUrls': 'false',
				'columns.member.26': 'albumCoverImageFull',
				'selectCriteriaList.member.1.attributeName': 'status',
				'selectCriteriaList.member.1.comparisonType': 'NOT_EQUALS',
				'selectCriteriaList.member.1.attributeValue': 'RECYCLED',
				'selectCriteriaList.member.2.attributeName': 'purchaseDate',
				'selectCriteriaList.member.2.comparisonType': 'GREATER_THAN',
				'selectCriteriaList.member.2.attributeValue': configuration['lastDownloadedPurchase'],
				'selectCriteriaList.member.3.attributeName': 'purchased',
				'selectCriteriaList.member.3.comparisonType': 'EQUALS',
				'selectCriteriaList.member.3.attributeValue': 'true',
				'sortCriteriaList.member.1.sortColumn': 'purchaseDate',
				'sortCriteriaList.member.1.sortType': 'ASC',
				'sortCriteriaList.member.2.sortColumn': 'sortAlbumName',
				'sortCriteriaList.member.2.sortType': 'ASC',
				'sortCriteriaList.member.3.sortColumn': 'discNum',
				'sortCriteriaList.member.3.sortType': 'ASC',
				'sortCriteriaList.member.4.sortColumn': 'trackNum',
				'sortCriteriaList.member.4.sortType': 'ASC'
			}


			cirrus_response = session.post('https://www.amazon.com/cirrus/2011-06-01/', data=new_purchase_params, headers=csrf_headers)
			select_tracks_response = json.loads(cirrus_response.content)
			
			#pprint(select_tracks_response)
			new_songs = select_tracks_response['selectTracksResponse']['selectTracksResult']['selectItemList']
			num_songs = len(new_songs)
			print  ("%d files to download." %num_songs)

			if(num_songs > 0):
				get_song_url_fields = {'customerInfo.customerId': app_data['customerId'],
						       'customerInfo.deviceId': app_data['deviceId'],
						       'customerInfo.deviceType': app_data['deviceType'],
						       'ContentType': 'JSON',
						       'https': 'true',
						       'Operation': 'getStreamUrls'
						       }

				filenames = {}
				purchaseDates = {}
				listNum = 1

				for song_meta in new_songs:
					get_song_url_fields['trackIdList.member.%d' % listNum] = song_meta['metadata']['objectId']
					filenames[song_meta['metadata']['objectId']] = song_meta['metadata']['artistName'] + " - " + song_meta['metadata']['title'] + "." + song_meta['metadata']['extension']
					purchaseDates[song_meta['metadata']['objectId']] = song_meta['metadata']['creationDate']
					listNum += 1

				# find mp3 urls
				cirrus_response = session.post('https://www.amazon.com/cirrus/2011-06-01/', data=get_song_url_fields, headers=csrf_headers)
				#print(cirrus_response.status_code)
				#print(cirrus_response.headers)
				#print(cirrus_response.content)
		
				urls_struct = json.loads(cirrus_response.content)
				# TODO: error handler when stream limit is exceeded
				error = urls_struct.get('Error', None)
				if not error == None:
					print("Failed to obtain url: {} {}".format(error['Code'], error['Message']), file=sys.stderr)
				urls_list = urls_struct['getStreamUrlsResponse']['getStreamUrlsResult']['trackStreamUrlList']

				fileNum = 1
				for song in urls_list:
					name = filenames[song['objectId']]
					print ("Downloading " + name + "...")
					# needs newer version of requests
					#r = session.get(song['url'], stream=True)
					#with open(name, 'wb') as fd:
					#	for chunk in r.iter_content(65536):
					#		fd.write(chunk)

					# TODO much more error handling is needed here with retries etc
					# The purchase-time system for finding new downloads is not robust to an album purchase that partially downloads,
					# but perfection can come with time...
					r = session.get(song['url'])
					fullpath = os.path.abspath(configuration['download_root']) + "/" + name
					with open(fullpath, 'wb') as fd:
						fd.write(r.content)
					configuration['lastDownloadedPurchase'] = purchaseDates[song['objectId']]
					config.save_configuration(opts.config_file, configuration)
			else:
				signal.signal(signal.SIGUSR1, handler)
				time.sleep(max(10, configuration['newFilePollSeconds']))
				signal.signal(signal.SIGUSR1, signal.SIG_IGN)
else:
	print ("%s: GET response not 200" %auth_form_url)


