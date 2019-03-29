# -*- coding: utf-8 -*-

import click
import json
import os
import re
import distutils.core
from glob import glob

from utilities.myyaml import load_yaml_file
from utilities.logs import get_logger

log = get_logger('check_versions.py')


@click.command()
@click.option('--skip-angular', is_flag=True, default=False)
def check_versions(skip_angular):

    dependencies = {}

    backend = load_yaml_file("confs/backend.yml")
    services = backend.get("services", {})
    for service in services:
        definition = services.get(service)
        image = definition.get('image')

        if image.startswith("rapydo/"):
            continue
        # print("%s service = %s" % (service, image))
        if service not in dependencies:
            dependencies[service] = {}

        dependencies[service]['compose'] = image

    for d in glob("../build-templates/*/Dockerfile"):
        if 'not_used_anymore_' in d:
            continue
        with open(d) as f:
            for line in f:
                if 'FROM' in line:
                    if line.startswith("#"):
                        continue
                    line = line.replace("FROM", "").strip()
                    # print("%s -> %s" % (d, line))
                    service = d.replace("../build-templates/", "")
                    service = service.replace("/Dockerfile", "")

                    if service not in dependencies:
                        dependencies[service] = {}

                    dependencies[service]['Dockerfile'] = line

    for d in glob("../build-templates/*/requirements.txt"):

        with open(d) as f:
            service = d.replace("../build-templates/", "")
            service = service.replace("/requirements.txt", "")
            for line in f:
                line = line.strip()

                if service not in dependencies:
                    dependencies[service] = {}

                if "pip" not in dependencies[service]:
                    dependencies[service]["pip"] = []

                dependencies[service]["pip"].append(line)

    if not skip_angular:
        package_json = None

        if os.path.exists('../frontend/package.json'):
            package_json = '../frontend/package.json'
        elif os.path.exists('../rapydo-angular/package.json'):
            package_json = '../rapydo-angular/package.json'

        if package_json is not None:
            with open(package_json) as f:
                package = json.load(f)
                package_dependencies = package.get('dependencies', {})
                package_devDependencies = package.get('devDependencies', {})

                if 'angular' not in dependencies:
                    dependencies['angular'] = {}

                if "package.json" not in dependencies['angular']:
                    dependencies['angular']["package.json"] = []

                for dep in package_dependencies:
                    ver = package_dependencies[dep]
                    lib = "%s:%s" % (dep, ver)
                    dependencies['angular']["package.json"].append(lib)
                for dep in package_devDependencies:
                    ver = package_devDependencies[dep]
                    lib = "%s:%s" % (dep, ver)
                    dependencies['angular']["package.json"].append(lib)

    utilities = distutils.core.run_setup("../utils/setup.py")
    controller = distutils.core.run_setup("../do/setup.py")
    http_api = distutils.core.run_setup("../http-api/setup.py")

    dependencies['utilities'] = utilities.install_requires
    dependencies['controller'] = controller.install_requires
    dependencies['http-api'] = http_api.install_requires

    filtered_dependencies = {}

    for service in dependencies:
        if service in ['talib', 'restclient', 'jq', 'react']:
            continue

        service_dependencies = dependencies[service]

        if isinstance(service_dependencies, list):
            filtered_dependencies[service] = []

            for d in service_dependencies:

                skipped = False
                if d.startswith('rapydo-utils=='):
                    skipped = True
                elif '==' in d:
                    filtered_dependencies[service].append(d)
                else:
                    skipped = True

                if skipped:
                    log.info("Filtering out %s", d)

            if len(filtered_dependencies[service]) == 0:
                log.warning("Removing empty list: %s", service)
                del filtered_dependencies[service]

        elif isinstance(service_dependencies, dict):
            for category in service_dependencies:
                if service not in filtered_dependencies:
                    filtered_dependencies[service] = {}
                deps = service_dependencies[category]

                was_str = False
                if isinstance(deps, str):
                    deps = [deps]
                    was_str = True
                else:
                    filtered_dependencies[service][category] = []

                for d in deps:

                    skipped = False
                    if d == 'b2safe/server:icat':
                        skipped = True
                    elif d == 'node:carbon':
                        skipped = True
                    elif re.match(r'^git\+https://github\.com.*@master$', d):
                        skipped = True
                    elif d == 'docker:dind':
                        skipped = True
                    elif d.endswith(':latest'):
                        skipped = True
                    elif d.startswith('rapydo-utils=='):
                        skipped = True
                    elif '==' in d or ':' in d:

                        if was_str:
                            filtered_dependencies[service][category] = d
                            log.critical(filtered_dependencies[service][category])
                        else:
                            filtered_dependencies[service][category].append(d)
                    else:
                        skipped = True

                    if skipped:
                        log.info("Filtering out %s", d)
            if category in filtered_dependencies[service]:
                if len(filtered_dependencies[service][category]) == 0:
                    log.warning("Removing empty list: %s.%s", service, category)
                    del filtered_dependencies[service][category]
            if len(filtered_dependencies[service]) == 0:
                log.warning("Removing empty list: %s", service)
                del filtered_dependencies[service]
        else:
            log.critical("Unknown dependencies type: %s", type(service_dependencies))

        # print(service)

    log.app(filtered_dependencies)


if __name__ == '__main__':
    check_versions()
