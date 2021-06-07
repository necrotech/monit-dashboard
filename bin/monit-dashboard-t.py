#!/usr/bin/env python

import web
import requests
import xmltodict
import json
import os
import sys
import datetime
from collections import OrderedDict
from operator import itemgetter
import utils
from threading import Thread
from queue import Queue

urls = ('/', 'index',
        '/help', 'help',
        '/download', 'download'
        )

app = web.application(urls, globals())
render = web.template.render('templates/', base="layout")

# Uncomment to turn debug off
web.config.debug = False

# Variables
output = []

# Functions


def calculate_count(data):
    count = {}
    ls = data.values()
    z, nz = 0, 0
    for v in ls:
        if v == 0:
            z += 1
        else:
            nz += 1
    count['green'] = z
    count['red'] = nz
    return count


def assembleOutput():
    output = []

    with open('{0}/conf/servers.json'.format(os.path.expanduser('.'))) as f:
        cf = json.loads(f.read())
        threads = []
        thread_queue = Queue()

        for site in cf:
            t = Thread(target=getMonit, args=(cf, site, thread_queue))
            threads.append(t)

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        while True:
            if not thread_queue.empty():
                output.append(thread_queue.get())
            else:
                break

    print(datetime.datetime.now())

    output = sorted(output, key=lambda k: k['name'])
    return output


def getMonit(cf, site, q):
    xmlQuery = "/_status?format=xml"

    try:
        s = cf[site]
        r = requests.get(s['url'] + xmlQuery,
                         auth=(s['user'], s['passwd']))

        allstat = json.loads(json.dumps(
            xmltodict.parse(r.text)['monit']))

        services = allstat['service']
        status = {}
        server = {}
        checks = OrderedDict()

        for service in services:
            name = service['name']
            status[name] = int(service['status'])
            checks[name] = status[name]

        sorted_checks = OrderedDict()
        sorted_checks = OrderedDict(sorted(checks.items(),
                                           key=itemgetter(1), reverse=True))
        count = calculate_count(sorted_checks)
        server = dict(name=site, url=s['url'],
                      result=sorted_checks, s_rate=count)

        q.put(server)

    except Exception as e:
        print("Error contacting " + site + ": " + str(e))

    return


# Classes


class monitDashboard(web.application):
    def run(self, port=8080, *middleware):
        func = self.wsgifunc(*middleware)
        return web.httpserver.runsimple(func, ('0.0.0.0', port))


class index(object):
    def GET(self):
        return render.index(output=assembleOutput(),
                            now=datetime.datetime.now())


class help(object):
    def GET(self):
        return render.help()


class download(object):
    def GET(self):
        filename = 'health_report.xlsx'
        output = assembleOutput()
        utils.generate_report_excel(output, filename)
        web.header('Content-Disposition',
                   'attachment; filename="health_report.xlsx"')
        web.header('Content-type', 'application/octet-stream')
        web.header('Cache-Control', 'no-cache')
        return open(filename, 'rb').read()


# Main
if __name__ == "__main__":
    app = monitDashboard(urls, globals())
    app.run(port=8080)
