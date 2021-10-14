import unittest, os
import unittest.mock
from unittest.mock import MagicMock, patch

import logging

logging.basicConfig(format = '%(asctime)s %(module)s %(levelname)s: %(message)s',
                datefmt = '%m/%d/%Y %I:%M:%S %p', level = logging.DEBUG)
logger = logging.getLogger(__name__)

from resources.lib.scanner import SteamScanner

from ael.api import ROMObj
from ael import constants

class Test_romscannerstests(unittest.TestCase):
    
    ROOT_DIR = ''
    TEST_DIR = ''
    TEST_ASSETS_DIR = ''

    @classmethod
    def setUpClass(cls):        
        cls.TEST_DIR = os.path.dirname(os.path.abspath(__file__))
        cls.ROOT_DIR = os.path.abspath(os.path.join(cls.TEST_DIR, os.pardir))
        cls.TEST_ASSETS_DIR = os.path.abspath(os.path.join(cls.TEST_DIR,'assets/'))
                
        print('ROOT DIR: {}'.format(cls.ROOT_DIR))
        print('TEST DIR: {}'.format(cls.TEST_DIR))
        print('TEST ASSETS DIR: {}'.format(cls.TEST_ASSETS_DIR))
        print('---------------------------------------------------------------------------')
        
    @patch('resources.utils.xbmcgui.DialogProgress.iscanceled')
    @patch('resources.objects.net_get_URL_original')
    def test_when_scanning_your_steam_account_not_existing_dead_roms_will_be_correctly_removed(self, mock_urlopen, progress_canceled_mock):

        # arrange
        mock_urlopen.return_value = self.read_file(self.TEST_ASSETS_DIR + "\\steamresponse.json")
        
        progress_canceled_mock.return_value = False

        settings = self._getFakeSettings()
        settings['steam-api-key'] = 'ABC123' #'BA1B6D6926F84920F8035F95B9B3E824'
        
        report_dir = FakeFile('//fake_reports/')
        addon_dir = FakeFile('//fake_addon/')

        roms = {}
        roms['1']= ROM({'id': '1', 'm_name': 'this-one-will-be-deleted', 'steamid': 99999})
        roms['2']= ROM({'id': '2', 'm_name': 'this-one-will-be-deleted-too', 'steamid': 777888444})
        roms['3']= ROM({'id': '3', 'm_name': 'Rocket League', 'steamid': 252950})
        roms['4']= ROM({'id': '4', 'm_name': 'this-one-will-be-deleted-again', 'steamid': 663434})        
        roms_repo = FakeRomSetRepository(roms)

        launcher_data = self._getFakeLauncherMetaData(OBJ_LAUNCHER_STEAM, 'Microsoft Windows', '')
        launcher_data['nointro_xml_file'] = None
        launcher_data['steamid'] = '09090909' #'76561198405030123' 
        launcher = SteamLauncher(launcher_data, settings, None, roms_repo, None)
        
        scraped_rom = {}
        scraped_rom['m_name'] = 'FakeScrapedRom'
        scrapers = [FakeScraper(settings, launcher, scraped_rom)]

        target = SteamScanner(report_dir, addon_dir, launcher, settings, scrapers)
        expectedRomCount = 5

        # act
        actualRoms = target.scan()

        # assert
        self.assertIsNotNone(actualRoms)
        actualRomCount = len(actualRoms)

        self.assertEqual(expectedRomCount, actualRomCount)

if __name__ == '__main__':    
    unittest.main()
