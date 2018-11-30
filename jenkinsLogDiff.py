#!/usr/bin/env python3

import requests # pip install requests
import pprint
import subprocess
pp = pprint.pprint
import json
import jenkinsLogDiffConfig as conf

# Turn off https warnings & verification
if not conf.httpsWarnings:
  from requests.packages.urllib3.exceptions import InsecureRequestWarning
  requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
httpsVerification=conf.httpsVerification
# Import conf variables
jenkinsUrl=conf.jenkinsUrl
jenkinsJob=conf.jenkinsJob
diffTool=conf.diffTool
diffOptArgs=conf.diffOptArgs

# Jenkins protects against CSRF so this crumb has to be passed with all requests
crumbResponse = json.loads(
  requests.get(
    jenkinsUrl + "/crumbIssuer/api/json", 
    verify=httpsVerification
  ).text
)
headers = {crumbResponse['crumbRequestField'] : crumbResponse['crumb']}


def ask(q):
  r = ''
  while r not in {'y', 'n'}:
    r = input(q + " (y/n)").lower().strip()
    if len(r): r = r[0]
  return r == 'y'

def getBuilds():
  builds = json.loads(
    requests.get(
      jenkinsUrl + jenkinsJob + '/api/json?tree=builds[number]',
      headers=headers,
      verify=httpsVerification
    ).text
  )['builds']
  print("Found " +str(len(builds)) +" builds")
  return builds

allBuilds = getBuilds()

def findLatestFailure():
  builds = allBuilds
  # Yeah, I know there's a more correct way to do this
  latestNum = str(builds[0]['number'])
  print("Latest build: " + str(latestNum))
  build = getBuildByNumber(latestNum)
  while not build['result'] == "FAILURE":
    build = getBuildByNumber(build['previousBuild']['number'])
  if build == None:
    print("Couldn't find any failed builds, just gonna pretend there's something wrong with the latest")
    build=getBuildByNumber(latestNum)
  return build

def getBuildByNumber(num):
  build = json.loads(
    requests.get(
      jenkinsUrl + jenkinsJob + str(num) + '/api/json?tree=number,result,previousBuild[number]',
      headers=headers,
      verify=httpsVerification
    ).text
  )
  return build

def findFirstPassAfterBuild(build):
  start = build['previousBuild']['number']
  print("Looking for passes starting at build: " + str(start))
  build = getBuildByNumber(start)
  while build['result'] == "FAILURE":
    build = getBuildByNumber(build['previousBuild']['number'])
  if build == None:
    print("Couldn't find any passing builds, just gonna pretend there's nothing wrong with " + str(start))
    build=getBuildByNumber(start)
  return build

def diffBuilds(buildNumTuple):
  fileNameList = []
  for buildNum in buildNumTuple:
    fn = '/tmp/jenkinsBuildDiff_build_' + str(buildNum)
    fileNameList.append(fn)
    f = open(fn, 'w')
    f.write(
      requests.get(
        jenkinsUrl + jenkinsJob + str(buildNum) +'/consoleText',
        headers=headers,
        verify=httpsVerification
      ).text
    )
    f.close()
  subprocess.run([diffTool] + diffOptArgs + fileNameList)
  return

latestFailure=findLatestFailure()
print("Latest failure: " + str(latestFailure['number']))
firstPassAfterFail=findFirstPassAfterBuild(latestFailure)
print("First pass after " + str(latestFailure['number']) + " : " + str(firstPassAfterFail['number']))
buildsToDiff = (latestFailure['number'], firstPassAfterFail['number'])
if not ask("Do you want to diff " + str(buildsToDiff) + " ?"):
  print("Alright... I see... you think you're so smart? Fine, you tell me what to diff. Here are all the builds Einstein:")
  print(list(map(lambda x: x['number'], allBuilds)))
  buildsToDiff = tuple(map(lambda x: int(input("Enter the " + x + " build number: ")), ["first", "second"]))
diffBuilds(buildsToDiff)

