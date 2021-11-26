#
# Advanced Kodi Launcher: Steam library launcher implementation
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

# --- AEL packages ---
from ael.utils import kodi
from ael.launchers import LauncherABC

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------------------------------------
# Launcher to use with a local Steam application and account.
# -------------------------------------------------------------------------------------------------
class SteamLauncher(LauncherABC):

    # --------------------------------------------------------------------------------------------
    # Core methods
    # --------------------------------------------------------------------------------------------
    def get_name(self) -> str: return 'Steam Launcher'
     
    def get_launcher_addon_id(self) -> str: 
        addon_id = kodi.get_addon_id()
        return addon_id

    # --------------------------------------------------------------------------------------------
    # Launcher build wizard methods
    # --------------------------------------------------------------------------------------------
    #
    # Creates a new launcher using a wizard of dialogs. Called by parent build() method.
    #
    def _builder_get_wizard(self, wizard):    
        wizard = kodi.WizardDialog_Dummy(wizard, 'application', 'Steam')
        return wizard
    
    def _editor_get_wizard(self, wizard):
        wizard = kodi.WizardDialog_Dummy(wizard, 'application', 'Steam')   
        return wizard
            
    def _build_post_wizard_hook(self):
        return True

    def _builder_get_edit_options(self):
        return None
         
    # ---------------------------------------------------------------------------------------------
    # Execution methods
    # ---------------------------------------------------------------------------------------------
    def get_application(self) -> str:
        return 'steam://rungameid/'
        
    def get_arguments(self) -> str:
        arguments =  '$steamid$'    
        original_arguments = self.launcher_settings['args'] if 'args' in self.launcher_settings else ''
        self.launcher_settings['args'] = '{} {}'.format(arguments, original_arguments)
        return super(SteamLauncher, self).get_arguments()
    
