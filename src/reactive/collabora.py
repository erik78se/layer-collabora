from charms.reactive import (
    when,
    when_any,
    when_all,
    when_not,
    set_flag,
    clear_flag,
    hook,
)
from charmhelpers.core import hookenv
from charmhelpers.core.templating import render
from charmhelpers.core.hookenv import (
    status_set,
    log,
)
from subprocess import check_call
from requests.exceptions import ConnectionError
import requests

#
#
# This charm configures the collabora docker image =>
# https://www.collaboraoffice.com/code/docker/
#
# * It defaults to listen to port:80
# * It is intended to run behind a ssl-terminiation-fqdn charm

# Installation


@when('docker.available')
@when_not('collabora.installed')
def install_collabora():
    hookenv.status_set('maintenance', 'Pulling collabora/code docker image')
    check_call(['docker', 'pull', 'collabora/code'])
    set_flag('collabora.installed')


# Starting
@when_all('collabora.installed', 'docker.available')
@when_not('collabora.started')
def run_container():
    '''
    Wrapper method to launch a docker container under the direction of Juju,
    and provide feedback/notifications to the end user.
    https://www.collaboraoffice.com/code/apache-reverse-proxy/

    The collabora takes some time to start.
    Test that it works: curl -Ivk http://<collabora>:<port>
    -> OK
    '''

    # Collabora wants dots escaped in the domain name.
    # nextcloud_domain should be that of "nextcloud"
    d = hookenv.config('nextcloud_domain').replace('.', '\.')

    p = hookenv.config('port')

    hookenv.open_port(p)

    run_command = ["docker", "run", "-t", "-d",
                   "--name", hookenv.application_name(),
                   "-p", ":{}:9980".format(p),
                   "-e", "domain={}".format(d),
                   "--restart",
                   "always",
                   "--cap-add", "MKNOD", "collabora/code"]
    check_call(run_command)

    clear_flag('collabora.stopped')

    set_flag('collabora.started')

    hookenv.status_set('waiting', 'Collabora container starting up.')


@when('collabora.started')
@when_not('collabora.configured')
def write_collabora_config():
    """Configure the docker container when collabora isn't configured"""

    ctxt = {'domain': hookenv.config('nextcloud_domain'),
            'ssl_enable': str(hookenv.config('ssl_enable')).lower(),
            'ssl_termination': str(hookenv.config('ssl_termination')).lower()}

    render('loolwsd.xml', '/srv/loolwsd.xml', context=ctxt, perms=0o777)

    check_call(["docker", "cp",
                "/srv/loolwsd.xml",
                "{}:/etc/loolwsd/loolwsd.xml".format(
                    hookenv.application_name())])

    check_call(["docker", "restart", hookenv.application_name()])

    # Remove temporary config file
    check_call(["rm", "/srv/loolwsd.xml"])

    set_flag('collabora.configured')



@when_any('config.changed.nextcloud_domain',
          'config.changed.ssl_enable',
          'config.changed.ssl_termination')
def collabora_reconfigured():
    """Let it be known that collabora no longer is configured."""

    log("collabora detected a config changed and thus is condidered unconfigured.")

    clear_flag('collabora.configured')



@when('collabora.stop', 'docker.available')
@when_not('collabora.stopped')
def stop_container():
    '''
    Stop the collabora application container, remove it, and prepare for
    launching of another application container so long as all the config values
    are appropriately set.
    '''
    hookenv.status_set('maintenance', 'Stopping collabora/code container')
    # make this cleaner
    try:
        check_call(['docker', 'kill', 'collabora/code'])
    except Exception:
        pass
    try:
        check_call(['docker', 'rm', 'collabora/code'])
    except Exception:
        pass
    clear_flag('collabora.started')
    clear_flag('collabora.stop')
    set_flag('collabora.stopped')
    hookenv.status_set('waiting', 'Collabora container stopped')


@when('website.available')
def configure_website(website):
    website.configure(port=hookenv.config('port'))


@hook('update-status')
def statusupdate():
    '''
    Check status of collabora every now and then (update-status).
    curl -Ivk <url>
    :return:
    '''
    p = hookenv.config('port')
    url = "http://127.0.0.1:{}".format(p)
    try:
        response = requests.get(url)
        if response.ok:
            status_set('active', "Collabora is OK.")
        else:
            status_set('active', "Collabora Not OK")
    except ConnectionError as err:
        status_set('waiting', "Connections failed for collabora status")
        log(err)
