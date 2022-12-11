import unittest, os
import unittest.mock
from unittest.mock import MagicMock, patch

import json
import logging

from tests.fakes import FakeProgressDialog, FakeFile, random_string

logging.basicConfig(format = '%(asctime)s %(module)s %(levelname)s: %(message)s',
                datefmt = '%m/%d/%Y %I:%M:%S %p', level = logging.DEBUG)
logger = logging.getLogger(__name__)

from resources.lib.scraper import SteamScraper
from akl.scrapers import ScrapeStrategy, ScraperSettings

from akl.api import ROMObj
from akl import constants
from akl.utils import net
        
def read_file(path):
    with open(path, 'r') as f:
        return f.read()
    
def read_file_as_json(path):
    file_data = read_file(path)
    return json.loads(file_data)

def mocked_steam(url, url_log=None, content_type=None):
    TEST_DIR = os.path.dirname(os.path.abspath(__file__))
    TEST_ASSETS_DIR = os.path.abspath(os.path.join(TEST_DIR,'assets/'))

    if 'SearchApps' in url:
        mocked_json_file = TEST_ASSETS_DIR + "/steam_list_responses.json"
        return read_file_as_json(mocked_json_file), 200

    if 'appdetails' in url:
        mocked_json_file = TEST_ASSETS_DIR + "/steamscraperesponse.json"
        return read_file_as_json(mocked_json_file), 200

    if 'https://cdn.akamai.steamstatic.com/' in url:
        return None, 200
    
    return net.get_URL(url)

class Test_steam_scraper(unittest.TestCase):

    @patch('resources.lib.scraper.net.get_URL', side_effect = mocked_steam)
    @patch('akl.scrapers.settings.getSettingAsFilePath', autospec=True, return_value=FakeFile("/test"))
    @patch('resources.lib.scraper.settings.getSetting', autospec=True, return_value=random_string(12))
    @patch('akl.api.client_get_rom')
    def test_scraping_metadata_for_game(self, 
        api_rom_mock: MagicMock, settings_mock, settings_file_mock, mock_get):    
        # arrange
        settings = ScraperSettings()
        settings.scrape_metadata_policy = constants.SCRAPE_POLICY_SCRAPE_ONLY
        settings.scrape_assets_policy = constants.SCRAPE_ACTION_NONE
        
        rom_id = random_string(5)
        rom = ROMObj({
            'id': rom_id,
            'm_name': 'Call of Duty: WWII',
            'scanned_data': { },
            'platform': 'Microsoft Windows'
        })
        api_rom_mock.return_value = rom
        
        target = ScrapeStrategy(None, 0, settings, SteamScraper(), FakeProgressDialog())

        # act
        actual = target.process_single_rom(rom_id)
        
        # assert
        self.assertTrue(actual)
        self.assertEqual('Call of Duty®: WWII', actual.get_name())
        logging.info(actual.get_data_dic())
                
    @patch('resources.lib.scraper.net.get_URL', side_effect = mocked_steam)
    @patch('resources.lib.scraper.net.download_img', autospec=True)
    @patch('resources.lib.scraper.io.FileName.scanFilesInPath', autospec=True)
    @patch('resources.lib.scraper.settings.getSettingAsFilePath', autospec=True, return_value=FakeFile("/test"))
    @patch('resources.lib.scraper.settings.getSetting', autospec=True, return_value=random_string(12))
    @patch('akl.api.client_get_rom')
    def test_scraping_assets_for_game(self, 
        api_rom_mock: MagicMock, settings_mock, settings_file_mock, scan_mock, mock_imgs, mock_get):
        # arrange
        settings = ScraperSettings()
        settings.scrape_metadata_policy = constants.SCRAPE_ACTION_NONE
        settings.scrape_assets_policy = constants.SCRAPE_POLICY_SCRAPE_ONLY
        settings.asset_IDs_to_scrape = [constants.ASSET_BANNER_ID, constants.ASSET_FANART_ID, constants.ASSET_SNAP_ID, constants.ASSET_TRAILER_ID]
        
        rom_id = random_string(5)
        rom = ROMObj({
            'id': rom_id,
            'scanned_data': { },
            'm_name': 'Call of Duty: WWII',
            'platform': 'Microsoft Windows',
            'assets': {key: '' for key in constants.ROM_ASSET_ID_LIST},
            'asset_paths': {
                constants.ASSET_BANNER_ID: '/banner/',
                constants.ASSET_FANART_ID: '/fanart/',
                constants.ASSET_SNAP_ID: '/snaps/',
                constants.ASSET_TRAILER_ID: '/trailer/'
            }
        })
        api_rom_mock.return_value = rom
        
        target = ScrapeStrategy(None, 0, settings, SteamScraper(), FakeProgressDialog())

        # act
        actual = target.process_single_rom(rom_id)

        # assert
        self.assertTrue(actual) 
        logger.info(actual.get_data_dic()) 
        
        self.assertTrue(actual.entity_data['assets'][constants.ASSET_SNAP_ID], 'No snap defined')      