from charms.reactive import when, when_all, when_not, set_flag, clear_flag
from charmhelpers.core import hookenv
from subprocess import check_call


#
#
# Configure collabora docker image => https://www.collaboraoffice.com/code/docker/
#
#

## Installation

@when('docker.available')
@when_not('collabora.installed')
def install_collabora():
    hookenv.status_set('maintenance', 'Pulling collabora/code docker image')
    check_call(['docker', 'pull', 'collabora/code'])
    set_flag('collabora.installed')

## Starting
@when_all('collabora.installed', 'docker.available')
@when_not('collabora.started')
def run_container():
    '''
    Wrapper method to launch a docker container under the direction of Juju,
    and provide feedback/notifications to the end user.
    https://www.collaboraoffice.com/code/apache-reverse-proxy/
    '''

    run_command = [
        'docker',
        'run',
        '-t',
        '-d',
        '-p',
        '{}:9980:9980'.format(hookenv.unit_public_ip()),
        '-e',
        'domain={}'.format(hookenv.config('domain')),
        '-e',
        'extra_params=--o:ssl.enable=false',
        '-e',
        'extra_params=--o:ssl.termination=true',
        '-e',
        'server_name={}'.format(hookenv.config('domain')),
        '--restart',
        'always',
        '--cap-add',
        'MKNOD',
        'collabora/code'
    ]
    check_call(run_command)
    hookenv.open_port(9980)
    clear_flag('collabora.stopped')
    set_flag('collabora.started')
    hookenv.status_set('active', 'Collabora container started')

@when('collabora.stop', 'docker.available')
@when_not('collabora.stopped')
def stop_container():
    '''
    Stop the collabora application container, remove it, and prepare for launching
    of another application container so long as all the config values are
    appropriately set.
    '''
    hookenv.status_set('maintenance', 'Stopping collabora/code container')
    # make this cleaner
    try:
        check_call(['docker', 'kill', 'collabora/code'])
    except:
        pass
    try:
        check_call(['docker', 'rm', 'collabora/code'])
    except:
        pass
    clear_flag('collabora.started')
    clear_flag('collabora.stop')
    set_flag('collabora.stopped')
    hookenv.status_set('waiting', 'Collabora container stopped')

@when('website.available')
def configure_website(website):
    website.configure(port=hookenv.config('port'))