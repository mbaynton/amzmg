from __future__ import print_function
import sys
import time
import logging
import signal
import json
import requests
import os.path
from amzmgutil import config

from datetime import timedelta, datetime

def backoff_wait(regular_poll_interval):
    if(backoff_wait.currWaitTime == 0):
        backoff_wait.currWaitTime = regular_poll_interval
    timeSinceLastWait = datetime.utcnow() - backoff_wait.lastEnteredWait
    if(timeSinceLastWait.total_seconds() >= backoff_wait.currWaitTime * 1.4):
        backoff_wait.currWaitTime = regular_poll_interval
    else:
        backoff_wait.currWaitTime = min(720, backoff_wait.currWaitTime * 2)

    backoff_wait.lastEnteredWait = datetime.utcnow()
    signal.signal(signal.SIGUSR1, passive_signal_handler)
    time.sleep(backoff_wait.currWaitTime)
    signal.signal(signal.SIGUSR1, signal.SIG_IGN)
    backoff_wait.lastEnteredWait = datetime(1900, 1, 1)
    backoff_wait.currWaitTime = 0

def passive_signal_handler(sigNum, stackFrame):
    pass

def main_dl_loop(configuration, app_data, opts, session, pollInterval, logger):
    csrf_config = app_data['CSRFTokenConfig']
    csrf_headers = {'csrf-token': csrf_config['csrf_token'], 'csrf-rnd': csrf_config['csrf_rnd'],
                    'csrf-ts': csrf_config['csrf_ts']}

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

        try:
            cirrus_response = session.post('https://www.amazon.com/cirrus/2011-06-01/',
                                           data=new_purchase_params, headers=csrf_headers)
            select_tracks_response = json.loads(cirrus_response.content)

            #pprint(select_tracks_response)
            new_songs = select_tracks_response['selectTracksResponse']['selectTracksResult']['selectItemList']
        except requests.exceptions.ConnectionError as ex:
            print("Connection error, using increased poll rate...")
            logger.warn('Connection error, new purchase poll unsuccessful. Applying backoff...')
            backoff_wait(pollInterval)
            continue
        except Exception as ex:
            x = 1

        num_songs = len(new_songs)
        print("%d files to download." % num_songs)
        logger.info("%d files to download." % num_songs)

        if (num_songs > 0):
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
                filenames[song_meta['metadata']['objectId']] = song_meta['metadata']['artistName'] + " - " + \
                                                               song_meta['metadata']['title'] + "." + \
                                                               song_meta['metadata']['extension']
                purchaseDates[song_meta['metadata']['objectId']] = song_meta['metadata']['creationDate']
                listNum += 1

            # find mp3 urls
            cirrus_response = session.post('https://www.amazon.com/cirrus/2011-06-01/',
                                           data=get_song_url_fields, headers=csrf_headers)
            #print(cirrus_response.status_code)
            #print(cirrus_response.headers)
            #print(cirrus_response.content)

            urls_struct = json.loads(cirrus_response.content)
            # TODO: error handler when stream limit is exceeded
            error = urls_struct.get('Error', None)
            if not error == None:
                print("Failed to obtain url: {} {}".format(error['Code'], error['Message']), file=sys.stderr)
                logger.error("Failed to obtain url: {} {}".format(error['Code'], error['Message']))
            urls_list = urls_struct['getStreamUrlsResponse']['getStreamUrlsResult']['trackStreamUrlList']

            fileNum = 1
            for song in urls_list:
                name = filenames[song['objectId']]
                print("Downloading " + name + "...")
                logger.info("Downloading " + name + "...")
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
                logger.warn("Downloaded \"" + name + "\" to " + configuration['download_root'])
        else:
            signal.signal(signal.SIGUSR1, passive_signal_handler)
            time.sleep(pollInterval)
            signal.signal(signal.SIGUSR1, signal.SIG_IGN)
