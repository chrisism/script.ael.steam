# -*- coding: utf-8 -*-
#
# Advanced Kodi Launcher scraping engine for Steam.
#
# Copyright (c) Chrisism <crizizz@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.

# --- Python standard library ---
from __future__ import unicode_literals
from __future__ import division

import logging
import json
import re

from urllib.parse import quote_plus

# --- AKL packages ---
from akl import constants, settings
from akl.utils import io, net, kodi
from akl.scrapers import Scraper
from akl.api import ROMObj


# ------------------------------------------------------------------------------------------------
# SteamScraper online scraper (metadata and assets).
#
# ------------------------------------------------------------------------------------------------
class SteamScraper(Scraper):
    # --- Class variables ------------------------------------------------------------------------
    supported_metadata_list = [
        constants.META_TITLE_ID,
        constants.META_YEAR_ID,
        constants.META_GENRE_ID,
        constants.META_DEVELOPER_ID,
        constants.META_RATING_ID,
        constants.META_PLOT_ID,
        constants.META_TAGS_ID
    ]
    supported_asset_list = [
        constants.ASSET_FANART_ID,
        constants.ASSET_BANNER_ID,
        constants.ASSET_SNAP_ID,
        constants.ASSET_TRAILER_ID
    ]

    URL_SearchAppByName = 'https://steamcommunity.com/actions/SearchApps/{}'
    URL_GameDetails = 'https://store.steampowered.com/api/appdetails?appids={}&cc=EE&l=english&v=1'

    # --- Constructor ----------------------------------------------------------------------------
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_key = settings.getSetting('steam-api-key')
            
        # --- Cached data ---
        self.cache_candidates = {}
        self.cache_metadata = {}
        self.cache_assets = {}
        self.all_asset_cache = {}

        cache_dir = settings.getSettingAsFilePath('scraper_cache_dir')
        self.call_count = 0
                
        super(SteamScraper, self).__init__(cache_dir)
    
    # --- Base class abstract methods ------------------------------------------------------------
    def get_name(self):
        return 'Steam Scraper'

    def get_filename(self):
        return 'steam'

    def supports_disk_cache(self):
        return True

    def supports_search_string(self):
        return True

    def supports_metadata_ID(self, metadata_ID):
        return True if metadata_ID in SteamScraper.supported_metadata_list else False

    def supports_metadata(self):
        return True

    def supports_asset_ID(self, asset_ID):
        return True if asset_ID in SteamScraper.supported_asset_list else False

    def supports_assets(self):
        return True

    def check_before_scraping(self, status_dic):
        if self.api_key:
            self.logger.debug('Steam API key looks OK.')
            return
        self.logger.error('Steam API key not configured.')
        self.logger.error('Disabling Steam scraper.')
        self.scraper_disabled = True
        status_dic['status'] = False
        status_dic['dialog'] = kodi.KODI_MESSAGE_DIALOG
        status_dic['msg'] = (
            'AKL requires your Steam API key. '
            'Visit https://steamcommunity.com/dev/apikey for directions about how to get your key '
            'and introduce the API key in AKL addon settings.'
        )

    def get_candidates(self, search_term, rom: ROMObj, platform, status_dic):
        # If the scraper is disabled return None and do not mark error in status_dic.
        # Candidate will not be introduced in the disk cache and will be scraped again.
        if self.scraper_disabled:
            self.logger.debug('Scraper disabled. Returning empty data for candidates.')
            return None

        # Prepare data for scraping.
        # --- Get candidates ---
        self.logger.debug(f'search_term         "{search_term}"')
        self.logger.debug(f'rom identifier      "{rom.get_identifier()}"')
        candidate_list = self._search_candidates(search_term, status_dic)
        if not status_dic['status']:
            return None

        return candidate_list
    
    # This function may be called many times in the ROM Scanner. All calls to this function
    # must be cached. See comments for this function in the Scraper abstract class.
    def get_metadata(self, status_dic):
        # --- If scraper is disabled return immediately and silently ---
        if self.scraper_disabled:
            self.logger.debug('Scraper disabled. Returning empty data.')
            return self._new_gamedata_dic()

        # --- Check if search term is in the cache ---
        if self._check_disk_cache(Scraper.CACHE_METADATA, self.cache_key):
            self.logger.debug(f'Metadata cache hit "{self.cache_key}"')
            json_data = self._retrieve_from_disk_cache(Scraper.CACHE_METADATA, self.cache_key)
        else:
            # --- Request is not cached. Get online data and introduce in the cache ---
            self.logger.debug(f'Metadata cache miss "{self.cache_key}"')
            id = self.candidate['id']
            url = SteamScraper.URL_GameDetails.format(id)
            json_data = self._retrieve_URL_as_JSON(url, status_dic)
            if not status_dic['status']:
                return None
            self._dump_json_debug('Steam_get_metadata.json', json_data)
            # --- Put metadata in the cache ---
            self.logger.debug(f'Adding to metadata cache "{self.cache_key}"')
            self._update_disk_cache(Scraper.CACHE_METADATA, self.cache_key, json_data)

        # --- Parse game page data ---
        self.logger.debug('Parsing game metadata...')
        online_data = json_data[id]['data']
        gamedata = self._new_gamedata_dic()
        gamedata['title'] = self._parse_metadata_title(online_data)
        gamedata['year'] = self._parse_metadata_year(online_data)
        gamedata['genre'] = self._parse_metadata_genres(online_data)
        gamedata['developer'] = self._parse_metadata_developer(online_data)
        gamedata['plot'] = self._parse_metadata_plot(online_data)
        gamedata['rating'] = self._parse_metadata_rating(online_data)
        gamedata['tags'] = self._parse_metadata_tags(online_data)

        self.logger.debug(f"Available metadata for the current scraped title: {json.dumps(gamedata)}")
        return gamedata
 
    # This function may be called many times in the ROM Scanner. All calls to this function
    # must be cached. See comments for this function in the Scraper abstract class.
    def get_assets(self, asset_info_id: str, status_dic):
        # --- If scraper is disabled return immediately and silently ---
        if self.scraper_disabled:
            self.logger.debug('Scraper disabled. Returning empty data.')
            return []

        candidate_id = self.candidate['id']
        self.logger.debug(f'Getting assets {asset_info_id} for candidate ID "{candidate_id}"')

        # --- Check if search term is in the cache ---
        if self._check_disk_cache(Scraper.CACHE_METADATA, self.cache_key):
            self.logger.debug(f'Metadata cache hit "{self.cache_key}"')
            json_data = self._retrieve_from_disk_cache(Scraper.CACHE_METADATA, self.cache_key)
        else:
            # --- Request is not cached. Get online data and introduce in the cache ---
            self.logger.debug(f'Metadata cache miss "{self.cache_key}"')
            url = SteamScraper.URL_GameDetails.format(candidate_id)
            json_data = self._retrieve_URL_as_JSON(url, status_dic)
            if not status_dic['status']:
                return None
            self._dump_json_debug('Steam_get_metadata.json', json_data)
            # --- Put metadata in the cache ---
            self.logger.debug(f'Adding to metadata cache "{self.cache_key}"')
            self._update_disk_cache(Scraper.CACHE_METADATA, self.cache_key, json_data)

        online_data = json_data[candidate_id]['data']
        assets_list = []
        if asset_info_id == constants.ASSET_TRAILER_ID:
            if 'movies' not in online_data:
                return assets_list        
            if len(online_data['movies']) == 0:
                return assets_list

            for movie in online_data['movies']:
                url = ''   
                if 'mp4' in movie:
                    url = movie['mp4']['max']
                elif 'webm' in movie: 
                    url = movie['webm']['max']

                asset_data = self._new_assetdata_dic()
                asset_data['asset_ID'] = asset_info_id
                asset_data['display_name'] = movie['name']
                asset_data['url_thumb'] = self._clean_url_slashes(movie['thumbnail'])
                asset_data['url'] = self._clean_url_slashes(url)
                assets_list.append(asset_data)

        if asset_info_id == constants.ASSET_SNAP_ID:
            if 'screenshots' not in online_data:
                return assets_list        
            if len(online_data['screenshots']) == 0:
                return assets_list

            for screenshot in online_data['screenshots']:
                asset_data = self._new_assetdata_dic()
                asset_data['asset_ID'] = asset_info_id
                asset_data['display_name'] = f"screenshot #{screenshot['id']}"
                asset_data['url_thumb'] = self._clean_url_slashes(screenshot['path_thumbnail'])
                asset_data['url'] = self._clean_url_slashes(screenshot['path_full'])
                assets_list.append(asset_data)

        if asset_info_id == constants.ASSET_BANNER_ID:
            if 'header_image' not in online_data:
                return assets_list        
            asset_data = self._new_assetdata_dic()
            asset_data['asset_ID'] = asset_info_id
            asset_data['display_name'] = "Header image"
            asset_data['url_thumb'] = self._clean_url_slashes(online_data["header_image"])
            asset_data['url'] = self._clean_url_slashes(online_data["header_image"])
            assets_list.append(asset_data)

        if asset_info_id == constants.ASSET_FANART_ID:
            if 'background_raw' not in online_data:
                return assets_list        
            asset_data = self._new_assetdata_dic()
            asset_data['asset_ID'] = asset_info_id
            asset_data['display_name'] = "Background image"
            asset_data['url_thumb'] = self._clean_url_slashes(online_data["background_raw"])
            asset_data['url'] = self._clean_url_slashes(online_data["background_raw"])
            assets_list.append(asset_data)

        self.logger.debug(f"Total assets found {len(assets_list)} for type {asset_info_id}")
        return assets_list

    def resolve_asset_URL(self, selected_asset, status_dic):
        url = selected_asset['url']
        url_log = self._clean_URL_for_log(url)

        return url, url_log

    def resolve_asset_URL_extension(self, selected_asset, image_url, status_dic):
        if selected_asset['asset_ID'] == constants.ASSET_TRAILER_ID:
            return "strm"
        return io.get_URL_extension(image_url)

    def download_image(self, image_url, image_local_path: io.FileName):
        if ".mp4" in image_url or ".webm" in image_url:
            image_local_path.saveStrToFile(image_url)
            return image_local_path
        return super(SteamScraper, self).download_image(image_url, image_local_path)

    # --- Retrieve list of games ---
    def _search_candidates(self, search_term: str, status_dic):
        search_string_encoded = quote_plus(search_term)
        url = SteamScraper.URL_SearchAppByName.format(search_string_encoded)

        # --- Get URL data as JSON ---
        json_data = self._retrieve_URL_as_JSON(url, status_dic)
        # If status_dic mark an error there was an exception. Return None.
        if not status_dic['status']:
            return None
        
        # If no games were found status_dic['status'] is True and json_data is None.
        # Return empty list of candidates.
        self._dump_json_debug('Steam_get_candidates.json', json_data)

        # --- Parse game list ---
        candidate_list = []
        for item in json_data:
            title = item['name']

            candidate = self._new_candidate_dic()
            candidate['id'] = item['appid']
            candidate['display_name'] = title
            candidate['order'] = 1
            # Increase search score based on our own search.
            if title.lower() == search_term.lower():
                candidate['order'] += 2
            if title.lower().find(search_term.lower()) != -1:
                candidate['order'] += 1
            candidate_list.append(candidate)

        self.logger.debug(f'Found {len(candidate_list)} titles with last request')
        # --- Sort game list based on the score. High scored candidates go first ---
        candidate_list.sort(key=lambda result: result['order'], reverse=True)

        return candidate_list

    def _parse_metadata_title(self, game_dic):
        if 'name' in game_dic and game_dic['name'] is not None:
            title_str = game_dic['name']
        else:
            title_str = constants.DEFAULT_META_TITLE

        return title_str

    def _parse_metadata_year(self, online_data):
        if 'release_date' in online_data and \
            'date' in online_data['release_date'] and \
            online_data['release_date']['date'] is not None:
            year_str = online_data['release_date']['date'][-4]
        else:
            year_str = constants.DEFAULT_META_YEAR
        return year_str

    def _parse_metadata_genres(self, online_data):
        if 'genres' not in online_data:
            return ''
        
        genres = [g['description'] for g in online_data['genres']]
        if not genres:
            return constants.DEFAULT_META_GENRE
        return ', '.join(genres)

    def _parse_metadata_developer(self, online_data):
        if 'developers' not in online_data:
            return ''
        return ', '.join(online_data['developers'])

    def _parse_metadata_plot(self, online_data):
        if 'detailed_description' in online_data and online_data['detailed_description'] is not None:
            plot_str = self._clean_HTML_from_text(online_data['detailed_description'])
        else:
            plot_str = constants.DEFAULT_META_PLOT

        return plot_str

    def _parse_metadata_rating(self, online_data):
        if 'metacritic' in online_data and online_data['metacritic'] is not None:
            score = online_data['metacritic']['score']
            score = int(score) / 100
        else:
            score = constants.DEFAULT_META_RATING

        return score

    def _parse_metadata_tags(self, online_data: dict) -> list:
        tags = []
        if 'categories' not in online_data:
            return tags

        category_ids = [c['id'] for c in online_data['categories']]
        if 1 in category_ids:
            tags.append('multiplayer')
        if 2 in category_ids:
            tags.append('singleplayer')
        if 9 in category_ids:
            tags.append('co-op')
        if 38 in category_ids:
            tags.append('online-co-op')
        if 49 in category_ids:
            tags.append('pvp')
        if 36 in category_ids:
            tags.append('online-pvp')
        if 24 in category_ids or 37 in category_ids or 39 in category_ids:
            tags.append('splitscreen')
        if 18 in category_ids:
            tags.append('partial-controller-support')
        if 28 in category_ids:
            tags.append('controller-supported')
        if 9 in category_ids:
            tags.append('co-op')
        
        return tags

    # Steam URLs are safe for printing.
    # Clean URLs for safe logging.
    def _clean_URL_for_log(self, url):
        if not url:
            return url

        clean_url = url
        # apikey is followed by more arguments
        clean_url = re.sub('apikey=[^&]*&', 'apikey=***&', clean_url)
        # apikey is at the end of the string
        clean_url = re.sub('apikey=[^&]*$', 'apikey=***', clean_url)
        return clean_url

    def _clean_HTML_from_text(self, txt):
        cleaned = re.sub('<[^<]+?>', '', txt)
        return cleaned

    def _clean_url_slashes(self, url):
        return url.replace("\\", "")

    # Retrieve URL and decode JSON object.
    #
    # * When the URL is called too often, we apply a timeout
    def _retrieve_URL_as_JSON(self, url, status_dic, retry = 1):
        if self.call_count > 4:
            self._wait_for_API_request(1000)
            self.call_count = 0

        json_data, http_code = net.get_URL(url, self._clean_URL_for_log(url), content_type=net.ContentType.JSON)
        self.call_count += 1

        # --- Check HTTP error codes ---
        if http_code != 200:

            if http_code == 429:
                if retry > 4:
                    self.logger.error("Too many requests after 4 tries. Quiting")
                    self._handle_error(status_dic, (
                        'Steam has received too many requests. '
                        'Stop scraping for now and repeat at a later time.'
                    ))
                    return None

                self.logger.warning(f"Steam Too many requests: {json_data}")
                kodi.notify(f"Too many requests. Waiting {5*retry} seconds.")
                self._wait_for_API_request(5000*retry)
                retry += 1
                return self._retrieve_URL_as_JSON(url, status_dic, retry)

            self.logger.error(f'Steam HTTP error code "{http_code}"')
            self._handle_error(status_dic, f'HTTP code {http_code}')
            return None

        # If json_data is None at this point is because of an exception in net_get_URL()
        # which is not urllib2.HTTPError.
        if json_data is None:
            self._handle_error(status_dic, 'Steam: Network error in net_get_URL()')
            return None

        return json_data
        