# -*- coding: utf-8 -*-
#
# Copyright (C) 2007 Andrew Resch <andrewresch@gmail.com>
# Copyright (C) 2010 Pedro Algarvio <pedro@algarvio.me>
#
# This file is part of Deluge and is licensed under GNU General Public License 3.0, or later, with
# the additional special exception to link portions of this program with the OpenSSL library.
# See LICENSE for more details.
#
from __future__ import print_function, unicode_literals

import os
import sys
from logging import DEBUG, FileHandler, getLogger

from twisted.internet.error import CannotListenError

from deluge.common import run_profiled, windows_check
from deluge.configmanager import get_config_dir
from deluge.ui.baseargparser import BaseArgParser
from deluge.ui.translations_util import set_dummy_trans


def add_daemon_options(parser):
    group = parser.add_argument_group(_('Daemon Options'))

    if not windows_check():
        group.add_argument('--ui-unix-socket', metavar='<path>', action='store',
                           help=_('Path to UNIX domain socket'))
    group.add_argument('-u', '--ui-interface', metavar='<ip-addr>', action='store',
                       help=_('IP address to listen for UI connections'))
    group.add_argument('-p', '--port', metavar='<port>', action='store', type=int,
                       help=_('Port to listen for UI connections on'))
    group.add_argument('-i', '--interface', metavar='<ip-addr>', dest='listen_interface', action='store',
                       help=_('IP address to listen for BitTorrent connections'))
    group.add_argument('--read-only-config-keys', metavar='<comma-separated-keys>', action='store',
                       help=_('Config keys to be unmodified by `set_config` RPC'), type=str, default='')
    parser.add_process_arg_group()


def start_daemon(skip_start=False):
    """
    Entry point for daemon script

    Args:
        skip_start (bool): If starting daemon should be skipped.

    Returns:
        deluge.core.daemon.Daemon: A new daemon object

    """
    set_dummy_trans(warn_msg=True)

    # Setup the argument parser
    parser = BaseArgParser()
    add_daemon_options(parser)

    options = parser.parse_args()

    # Check for any daemons running with this same config
    from deluge.core.daemon import is_daemon_running
    pid_file = get_config_dir('deluged.pid')
    if is_daemon_running(pid_file):
        print('Cannot run multiple daemons with same config directory.\n'
              'If you believe this is an error, force starting by deleting: %s' % pid_file)
        sys.exit(1)

    log = getLogger(__name__)

    # If no logfile specified add logging to default location (as well as stdout)
    if not options.logfile:
        options.logfile = get_config_dir('deluged.log')
        file_handler = FileHandler(options.logfile)
        log.addHandler(file_handler)

    def run_daemon(options):
        try:
            from deluge.core.daemon import Daemon
            from deluge.core.rpcserver import ListenSSL, ListenUNIX

            if options.ui_unix_socket is not None:
                listener = ListenUNIX(path=options.ui_unix_socket)
            else:
                listener = ListenSSL(interface=options.ui_interface,
                                     port=options.port)

            daemon = Daemon(listener=listener,
                            listen_interface=options.listen_interface,
                            read_only_config_keys=options.read_only_config_keys.split(','))
            if skip_start:
                return daemon
            else:
                daemon.start()
        except CannotListenError as ex:
            log.error('Cannot start deluged, listen port in use.\n'
                      ' Check for other running daemons or services using this port: %s:%s',
                      ex.interface, ex.port)
            sys.exit(1)
        except Exception as ex:
            log.error('Unable to start deluged: %s', ex)
            if log.isEnabledFor(DEBUG):
                log.exception(ex)
            sys.exit(1)
        finally:
            log.info('Exiting...')
            if options.pidfile:
                os.remove(options.pidfile)

    return run_profiled(run_daemon, options, output_file=options.profile, do_profile=options.profile)
