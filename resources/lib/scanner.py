# -*- coding: utf-8 -*-
#
# Advanced Kodi Launcher: Steam library scanner implementation
#
# Copyright (c) Chrisism <crizizz@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# --- Python standard library ---
from __future__ import unicode_literals
from __future__ import division

import logging
import typing
import collections
import json

# --- AKL packages ---
from akl import report, settings, api
from akl.utils import kodi, net, io
from akl.utils.net import ContentType

from akl.scanners import RomScannerStrategy, ROMCandidateABC


class SteamCandidate(ROMCandidateABC):
    
    def __init__(self, json_data):
        self.json_data = json_data
        super(SteamCandidate, self).__init__()
        
    def get_ROM(self) -> api.ROMObj:
        rom = api.ROMObj()
        rom.set_name(self.get_name())
        scanned_data = {
            'identifier': self.get_app_id(),
            'steamid': self.get_app_id(),
            'steam_name': self.get_name(),
            'steam_data': json.dumps(self.json_data),
            'scanner': kodi.get_addon_id(),
            'scanner_version': kodi.get_addon_version()
        }
        rom.set_scanned_data(scanned_data)
        return rom
        
    def get_sort_value(self):
        return self.json_data['name']
    
    def get_app_id(self):
        return self.json_data['appid']
    
    def get_name(self):
        return self.json_data['name']


class SteamScanner(RomScannerStrategy):

    def __init__(self,
                 reports_dir: io.FileName,
                 source_id: str,
                 webservice_host: str,
                 webservice_port: int,
                 progress_dialog: kodi.ProgressDialog):
        self.logger = logging.getLogger(__name__)
        super(SteamScanner, self).__init__(reports_dir, source_id,
                                           webservice_host, webservice_port,
                                           progress_dialog)
    
    # --------------------------------------------------------------------------------------------
    # Core methods
    # --------------------------------------------------------------------------------------------
    def get_name(self) -> str:
        return 'Steam Library scanner'
    
    def get_scanner_addon_id(self) -> str:
        addon_id = kodi.get_addon_id()
        return addon_id
    
    def get_steam_id(self) -> str:
        return self.scanner_settings['steamid'] if 'steamid' in self.scanner_settings else None
    
    def _configure_get_wizard(self, wizard) -> kodi.WizardDialog:
        wizard = kodi.WizardDialog_Keyboard(wizard, 'steamid', 'Steam account ID')
        return wizard
      
    def _configure_post_wizard_hook(self):
        return True
            
    def _configure_get_edit_options(self) -> dict:
        options = collections.OrderedDict()
        options[self._change_steam_id] = "Change Steam account ID: '{}'".format(self.scanner_settings['steamid'])
        return options

    def _change_steam_id(self):
        steamid = self.scanner_settings['steamid']
        steamid = kodi.dialog_keyboard('Edit Steam account ID', text=steamid)
        if steamid is None:
            return
        self.scanner_settings['steamid'] = steamid

    # ---------------------------------------------------------------------------------------------
    # Execution methods
    # ---------------------------------------------------------------------------------------------
    # ~~~ Scan for new files (*.*) and put them in a list ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def _getCandidates(self, launcher_report: report.Reporter) -> typing.List[ROMCandidateABC]:
        self.progress_dialog.startProgress('Reading Steam account...')
        launcher_report.write('Reading Steam account id {}'.format(self.get_steam_id()))
     
        apikey = settings.getSetting('steam-api-key')
        steamid = self.get_steam_id()
        url = 'http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?key={}&steamid={}&include_appinfo=1'.format(apikey, steamid)
        
        self.progress_dialog.updateProgress(70)
        json_body, http_code = net.get_URL(url, content_type=ContentType.JSON)
        self.progress_dialog.updateProgress(80)
        
        if http_code != 200:
            self.logger.warning("Failure while retrieving json web data")
            kodi.notify_warn("Failure retrieving web data")
            return []

        games = json_body['response']['games']
        num_games = len(games)
        launcher_report.write(f'  Library scanner found {num_games} games')
        
        self.progress_dialog.endProgress()
        return [*(SteamCandidate(g) for g in games)]
    
    # --- Get dead entries -----------------------------------------------------------------
    def _getDeadRoms(self, candidates: typing.List[ROMCandidateABC], roms: typing.List[api.ROMObj]) -> typing.List[api.ROMObj]:
        dead_roms = []
        num_roms = len(roms)
        if num_roms == 0:
            self.logger.info('Source is empty. No dead ROM check.')
            return dead_roms
        
        self.logger.info('Starting dead items scan')
        i = 0
            
        self.progress_dialog.startProgress('Checking for dead ROMs ...', num_roms)
        
        candidate_steam_ids = set(c.get_app_id() for c in candidates)
        for rom in reversed(roms):
            steam_id = rom.get_scanned_data_element('steamid')
            self.logger.info('Searching ID#{}'.format(steam_id))
            self.progress_dialog.updateProgress(i)
            
            if steam_id not in candidate_steam_ids:
                self.logger.info('Not found. Marking as dead: #{} {}'.format(steam_id, rom.get_name()))
                roms.remove(rom)
                dead_roms.append(rom)
            i += 1
            
        self.progress_dialog.endProgress()
        return dead_roms

    # ~~~ Now go processing item by item ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def _processFoundItems(self,
                           candidates: typing.List[ROMCandidateABC],
                           roms: typing.List[api.ROMObj],
                           launcher_report: report.Reporter) -> typing.List[api.ROMObj]:

        num_items = len(candidates)
        new_roms: typing.List[api.ROMObj] = []

        self.progress_dialog.startProgress('Scanning found items', num_items)
        self.logger.debug('============================== Processing Steam Games ==============================')
        launcher_report.write('Processing games ...')
        num_items_checked = 0
        
        steamIdsAlreadyInSource = set(rom.get_scanned_data_element('steamid') for rom in roms)

        for candidate in sorted(candidates, key=lambda c: c.get_sort_value()):
            
            steam_candidate: SteamCandidate = candidate
            steamId = steam_candidate.get_app_id()
            
            self.logger.debug('Searching {} with #{}'.format(steam_candidate.get_name(), steamId))
            self.progress_dialog.updateProgress(num_items_checked, steam_candidate.get_name())
            
            if steamId in steamIdsAlreadyInSource:
                self.logger.debug('  ID#{} already in source. Skipping'.format(steamId))
                num_items_checked += 1
                continue
            
            self.logger.debug('========== Processing Steam game ==========')
            launcher_report.write('>>> title: {}'.format(steam_candidate.get_name()))
            launcher_report.write('>>> ID: {}'.format(steam_candidate.get_app_id()))
        
            self.logger.debug(f'Not found. Item {steam_candidate.get_name()} is new')

            # ~~~~~ Process new ROM and add to the list ~~~~~
            new_rom = steam_candidate.get_ROM()
            new_roms.append(new_rom)
            
            # ~~~ Check if user pressed the cancel button ~~~
            if self.progress_dialog.isCanceled():
                self.progress_dialog.endProgress()
                kodi.dialog_OK('Stopping ROM scanning. No changes have been made.')
                self.logger.info('User pressed Cancel button when scanning ROMs. ROM scanning stopped.')
                return None
            
            num_items_checked += 1
           
        self.progress_dialog.endProgress()
        return new_roms
