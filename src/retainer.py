#!/usr/bin/env python3
import argparse, base64, os, requests


class Portainer:
    base_url = None

    registry_data = None

    session = None

    def __init__(self, base_url) -> None:
        self.base_url = base_url
        self.registry_data = []
        self.session = requests.Session()

        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Origin': base_url,
            'User-Agent': 'Retainer 0.1.0',
        })

    def api_request(self, path: str, method: str='GET', token: str=None, data: dict=None, **kwargs):
        if token:
            kwargs['Authorization'] = 'Bearer %s' % token

        result = self.session.request(
            method,
            '%s/%s' % (self.base_url, path),
            headers=kwargs,
            json=data,
        )

        result.raise_for_status()
        return result

    def docker_pull(self, endpoint: int, image: str, node: str=None, registry_id:int=0, token: str=None) -> None:
        headers = {}

        if node:
            headers['X-PortainerAgent-Target'] = node

        if registry_id > 0:
            headers['X-Registry-Auth'] = str(base64.b64encode(b'{"registryId":%d}' % registry_id), 'utf-8')
        else:
            for registry in self.registry_data:
                if registry['URL'] in image and registry['Name'] in image:
                     headers['X-Registry-Auth'] = str(base64.b64encode(b'{"registryId":%d}' % registry['Id']), 'utf-8')

        request = self.api_request(
            'api/endpoints/%d/docker/images/create?fromImage=%s' % (endpoint, image.replace('/', '%2F'), ),
            'POST',
            token,
            None,
            **headers
        )

        for line in request.iter_lines(decode_unicode=True):
            print(line)

    def get_first_endpoint(self, token: str=None) -> int:
        response = self.api_request('api/endpoints', token=token)
        endpoints = response.json()

        if len(endpoints) < 1:
            raise Exception('No endpoints available')

        return endpoints[0]['Id']

    def get_nodes(self, endpoint: int, token: str=None) -> list:
        result = []
        response = self.api_request('api/endpoints/%s/docker/nodes' % endpoint, token=token)

        for data in response.json():
            result.append(data['Description']['Hostname'])

        return result

    def get_registries(self, token: str=None) -> list:
        response = self.api_request('api/registries', token=token)
        return response.json()

    def login(self, username: str, password: str, update_headers: bool=True) -> str:
        response = self.api_request(
            'api/auth',
            'POST',
            data={
                'username': username,
                'password': password,
            },
        )

        result = response.json()['jwt']

        if update_headers:
            self.session.headers.update({
                'Authorization': 'Bearer %s' % result
            })

        return result

    def restart_service(self, endpoint: int, payload: dict, pull_latest=True, token: str=None) -> dict:
        print('Restarting service %s (%s)...' % (
            payload['Spec']['Name'],
            payload['ID'],
        ))

        if pull_latest:
            payload['Spec']['TaskTemplate']['ForceUpdate'] += 1

        response = self.api_request(
            'api/endpoints/%d/docker/services/%s/update?version=%d' % (
                endpoint,
                payload['ID'],
                payload['Version']['Index'],
            ),
            'POST',
            token,
            payload['Spec'],
        )

        return response.json()

    def update_registries(self, token: str=None) -> list:
        self.registry_data = self.get_registries(token)
        return self.registry_data

    def update_services_from_tag(self, endpoint: int, image: str, token: str=None) -> list:
        result = []
        response = self.api_request('api/endpoints/%d/docker/services' % endpoint, token=token)

        for service in response.json():
            if image == service['Spec']['TaskTemplate']['ContainerSpec']['Image']:
                result.append(service)

                self.restart_service(
                    endpoint,
                    service,
                    token=token,
                )

        return result


def start():
    config = {
        'docker_image': os.getenv('DOCKER_IMAGE'),
        'portainer_endpoint': int(os.getenv('PORTAINER_ENDPOINT', '-1')),
        'portainer_nodes': os.getenv('PORTAINER_NODES'),
        'portainer_password': os.getenv('PORTAINER_PASSWORD'),
        'portainer_url': os.getenv('PORTAINER_URL'),
        'portainer_username': os.getenv('PORTAINER_USERNAME'),
    }

    parser = argparse.ArgumentParser(
        description='A simple script designed for CI with Portainer',
        prog='retainer',
    )

    parser.add_argument(
        '--endpoint',
        '-e',
        default=config['portainer_endpoint'],
        help='Portainer endpoint (replaces "PORTAINER_ENDPOINT" environment, can be blank to use the first endpoint available)',
        required=False,
        type=int,
    )

    parser.add_argument(
        '--image',
        '-i',
        help='Docker image (replaces "DOCKER_IMAGE" environment)',
        required=False,
    )

    parser.add_argument(
        '--nodes',
        '-n',
        help='Comma-separated Portainer nodes (replaces "PORTAINER_NODES" environment, can be blank to use the default Portainer node, or can be "*" to use all available nodes)',
        required=False,
    )

    parser.add_argument(
        '--password',
        '-p',
        help='Portainer password (replaces "PORTAINER_PASSWORD" environment)',
        required=False,
    )

    parser.add_argument(
        '--restart',
        '-r',
        help='Restart services after pull (only for Swarm clusters)',
        action=argparse.BooleanOptionalAction,
        default=True,
    )

    parser.add_argument(
        '--url',
        '-U',
        help='Portainer URL address (replaces "PORTAINER_URL" environment)',
        required=False,
    )

    parser.add_argument(
        '--username',
        '-u',
        help='Portainer user name (replaces "PORTAINER_USERNAME" environment)',
        required=False,
    )

    args = parser.parse_args()

    if args.endpoint:
        config['portainer_endpoint'] = args.endpoint

    if args.image:
        config['docker_image'] = args.image

    if args.nodes:
        config['portainer_nodes'] = args.nodes

    if args.password:
        config['portainer_password'] = args.password

    if args.url:
        config['portainer_url'] = args.url

    if args.username:
        config['portainer_username'] = args.username

    print('Trying to authenticate in %s with username "%s"...' % (
        config['portainer_url'],
        config['portainer_username'],
    ))

    portainer = Portainer(config['portainer_url'])
    portainer.login(config['portainer_username'], config['portainer_password'])
    portainer.update_registries()
    endpoint = config['portainer_endpoint'] if config['portainer_endpoint'] > 0 else portainer.get_first_endpoint()
    nodes = []

    if config['portainer_nodes']:
        if config['portainer_nodes'] == '*':
            nodes = portainer.get_nodes(endpoint)
        else:
            nodes = config['portainer_nodes'].split(',')

        for node in nodes:
            print('Pulling image "%s" on %s...' % (
                config['docker_image'],
                node,
            ))

            portainer.docker_pull(endpoint, config['docker_image'], node)
    else:
        print('Pulling image "%s" on default node...' % config['docker_image'])
        portainer.docker_pull(endpoint, config['docker_image'])

    if args.restart:
        print('Restarting Swarm services using the image "%s"...' % config['docker_image'])
        portainer.update_services_from_tag(endpoint, config['docker_image'])

    print('Operation complete!')


if __name__ == '__main__':
    start()
