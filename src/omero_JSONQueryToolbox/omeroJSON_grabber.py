# coding=utf-8
from __future__ import print_function
# for JSON API
#from __future__ import print_function must be at beginning of file
import argparse
import os.path
import re
import requests
import json
import markdown

#####################################################################################################
# This script returns the OMERO core metadata of given ID's of images (receive via OMERO JSON-API) or 
# datasets stored in OMERO as a python dictionary and optionally writes them to a file (JSON, HTML, Markdown).

# Core-metadata are:
# - Image name
# - Image ID
# - Image description
# - Image owner
# - Size X
# - Size Y
# - Pixels type
# - Size C
# - Size T
#
# Input:
# - Username in OMERO who owns the data
# - Output file type (possible values: JSON, HTML, MD; optional)
# - Number to identify created output file (e.g. timestamp or ELN-Object permId)
# - Space separated list of OMERO IDs (e.g. 1 2 45), min. number of IDs = 1
# - Type of the OMERO IDs (Possible values: IMAGES, DATASET)
#
# Output:
# html, json or markdown file.
#
# For details see manual at: .
#
# Copyright:
# Copyright (C) <2023> University of Osnabrueck.
# All rights reserved.
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @author Julia Dohle
# Contact: judohle@uos.de

#####################################################################################################
# Configuration:
#####################################################################################################
# user in OMERO with restricted admin rights to read the info for images and dataset for different users
SUDO_USERNAME = ''
PASSWORD = ''
# OMERO HOST address
OMERO_WEB_HOST = 'https://my.omero.de'
# flag to save output in a file
SAVE_OUTPUT = True
# location for output file
OUTPUT_PATH = "/path/to/output/dir"
#####################################################################################################
#####################################################################################################
# name of session server
SERVER_NAME = 'omero'
#####################################################################################################

def markdown_table(metadata_dict, headers, mdfname):
    rows = []
    # specify width of column
    col_w = 20
    # build markdown table
    # header
    rows.append('|'.join(s.center(col_w) for s in headers))
    # separator
    rows.append('|'.join('-' * col_w for x in range(len(headers))))
    # build body
    for i in metadata_dict.values():
        # put line break in string if longer than 18 chars
        rows.append('|'.join('<br>'.join(str(v)[i:i+col_w-2] for i in range(0, len(str(v)), col_w-2)).center(col_w)
                             for k, v in i.items() if k in headers))
    with open(mdfname, 'w') as f:
        for row in rows:
            print("|"+row+"|", file=f)


def check_dir_permissions():
    if os.access(OUTPUT_PATH, os.R_OK | os.X_OK):
        return
    else:
        raise FileNotFoundError("Error: no such file or directory" + OUTPUT_PATH)


def save_output(metadata, headers, ident, ftypeList):
    # check permissions of directory OUTPUT_PATH
    check_dir_permissions()
    # save metadata dictionary as json, markdown or html file
    fName = os.path.join(OUTPUT_PATH, f"omero_{ident}")
    for i in ftypeList:
        if re.search('json', i, re.IGNORECASE):
            json_metadata = json.dumps(metadata)
            jsonfile = f"{fName}.json"
            with open(jsonfile, "w") as f:
                json.dump(metadata, f, indent=4)
        if re.search('md', i, re.IGNORECASE):
            mdfile = f"{fName}.md"
            markdown_table(metadata, headers, mdfile)
        if re.search('html', i, re.IGNORECASE):
            mdfile = f"{fName}.md"
            markdown_table(metadata, headers, mdfile)
            with open(mdfile, 'r') as f:
                markdown_string = f.read()
            html_table = markdown.markdown(markdown_string)
            htmlfile = f"{fName}.html"
            with open(htmlfile, 'w') as f:
                f.write(html_table)
            if os.path.isfile(mdfile):
                os.remove(mdfile)
            else:
                print("Error: %s file not found" % mdfile)
        else:
            # if none of the types is selected, choose json
            json_metadata = json.dumps(metadata)
            jsonfile = f"{fName}.json"
            with open(jsonfile, "w") as f:
                json.dump(metadata, f, indent=4)


def get_headers(metadata):
    #print("get_headers()")
    keys = []
    for i in metadata:
        keys = metadata[i].keys()
    headrs = []
    for j in keys:
        headrs.append(j)

    return headrs


def fill_dict(mdict, id, key, val):
    try:
        mdict["%s" % id][key] = val
    except Exception:
        mdict["%s" % id][key] = "-"
    return mdict


def fill_dict_default(mdict,ID):
    fill_dict(mdict, ID, 'Name', "-")
    fill_dict(mdict, ID, 'ID', "-") 
    fill_dict(mdict, ID, 'Username', "-")
    fill_dict(mdict, ID, 'Description', "-")
    fill_dict(mdict, ID, 'SizeX', "-")
    fill_dict(mdict, ID, 'SizeY', "-")
    fill_dict(mdict, ID, 'Pixel Type', "-")
    fill_dict(mdict, ID, 'SizeZ', "-")
    fill_dict(mdict, ID, 'SizeC', "-")
    fill_dict(mdict, ID, 'SizeT', "-")


def get_core_metadata(openBISUser, IdList, idtype, metadata, images_url, datasets_url, session):
    # finale image ID Liste:
    imageIDsList = []
    # if dataset: get ImageIds, put them in image ID list
    if re.match(idtype, "Dataset", re.IGNORECASE):
        for datasetId in IdList:
            dsUrl = datasets_url + datasetId + "/images/"
            try:
                dsjson = session.get(dsUrl).json()
                # check if there are images in dataset = dataset exists
                imgCount = dsjson['meta']['totalCount']
                if imgCount == 0:
                    imageIDsList.append(-2)
                else:
                    # get number of images in dataset
                    i = 0
                    while i < imgCount:
                        # get ID, put in imageIDsList
                        iID = dsjson['data'][i]['@id']
                        imageIDsList.append(iID)
                        i += 1
            except Exception as e:
                # dataset does not exist
                imageIDsList.append(-2)
    # else: idtype == 'Images' 
    else:
        imageIDsList = IdList

    if not len(imageIDsList):
        print("Error: there are no images in images_List")
        return

    # for every image in list get json core metadata via JSON API
    for ID in imageIDsList:
        # create sub-dictionary and build image_url
        metadata["%s" % ID] = {}
        imgUrl = images_url + str(ID) + '/'
        # handle not existing dataset
        if ID == -2:
           fill_dict_default(metadata,ID)
           fill_dict(metadata, ID, 'ID', -1)
           fill_dict(metadata, ID, 'Description', "One given ID does not correspond to an existing OMERO dataset")
        # dataset exists or instead image IDs were given
        else:
            try:
                imgjson = session.get(imgUrl).json()
                # if image exists in OMERO database
                try:
                    imgjson['data']['@id']
                    # if the ELN user is the image owner & allowed to get the image metadata
                    if imgjson['data']['omero:details']['owner']['UserName'] == openBISUser:
                        # parse information from json to our metadata dict
                            fill_dict(metadata, ID, 'Name', imgjson['data']['Name'])                      
                            fill_dict(metadata, ID, 'ID', imgjson['data']['@id'])                       
                            fill_dict(metadata, ID, 'Username', imgjson['data']['omero:details']['owner']['UserName'])                       
                            fill_dict(metadata, ID, 'Description', imgjson['data']['Description'])                        
                            fill_dict(metadata, ID, 'SizeX', imgjson['data']['Pixels']['SizeX'])                        
                            fill_dict(metadata, ID, 'SizeY', imgjson['data']['Pixels']['SizeY'])                        
                            fill_dict(metadata, ID, 'Pixel Type', imgjson['data']['Pixels']['Type']['value'])                       
                            fill_dict(metadata, ID, 'SizeZ', imgjson['data']['Pixels']['SizeZ'])                        
                            fill_dict(metadata, ID, 'SizeC', imgjson['data']['Pixels']['SizeC'])                        
                            fill_dict(metadata, ID, 'SizeT', imgjson['data']['Pixels']['SizeT'])
                    else:
                        # if the ELN user is not the image owner & not allowed to get the image metadata,
                        # give this info as descr and the ID of the image
                        fill_dict_default(metadata,ID)                      
                        fill_dict(metadata, ID, 'ID', imgjson['data']['@id'])                        
                        fill_dict(metadata, ID, 'Description', "This ELN User is not the image owner: metadata access denied")
                        
                except Exception as e:
                    # cannot get image json for image ID
                    #print("Error: cannot get imgjson for ID %s: %s " % (str(ID), str(e)))
                    fill_dict_default(metadata,ID) 
                    fill_dict(metadata, ID, 'ID', ID)
                    fill_dict(metadata, ID, 'Description', "Error: cannot get imgjson for ID %s: %s " % (str(ID), str(e)))
            except Exception as e:
                # this image does not exist in the OMERO database
                #print("This image does not exists in the OMERO database")
                fill_dict_default(metadata,ID) 
                fill_dict(metadata, ID, 'ID', ID)
                fill_dict(metadata, ID, 'Description', "This image does not exist in the OMERO database")

    return metadata


def get_omero_session():
    # request a session for login to Omero Server via  SUDO_USERNAME User created for this purpose
    # (Admin with read only access)
    # how to use JSON-API of OMERO see: https://docs.openmicroscopy.org/omero/5.6.0/developers/json-api.html
    session = requests.Session()
    # Start by getting supported versions from the base url...
    api_url = '%s/api/' % OMERO_WEB_HOST
    r = session.get(api_url)
    # we get a list of versions
    versions = r.json()['data']
    # use most recent version...
    version = versions[-1]
    # get the 'base' url
    base_url = version['url:base']
    r = session.get(base_url)
    # which lists a bunch of urls as starting points
    urls = r.json()
    servers_url = urls['url:servers']
    login_url = urls['url:login']
    images_url = urls['url:images']
    datasets_url = urls['url:datasets']
    # To login, we need to get CSRF token
    token_url = urls['url:token']
    token = session.get(token_url).json()['data']
    # We add this to our session header
    # Needed for all POST, PUT, DELETE requests
    session.headers.update({'X-CSRFToken': token,
                            'Referer': login_url})
    # List the servers available to connect
    servers = session.get(servers_url).json()['data']
    # find one called SERVER_NAME
    servers = [s for s in servers if s['server'] == SERVER_NAME]
    if len(servers) < 1:
        raise Exception("Found no server called '%s'" % SERVER_NAME)
    server = servers[0]
    # Login with username, password and token
    payload = {'username': SUDO_USERNAME,
               'password': PASSWORD,
               # 'csrfmiddlewaretoken': token,  # Using CSRFToken in header instead
               'server': server['id']}
    r = session.post(login_url, data=payload)
    login_rsp = r.json()
    assert r.status_code == 200
    assert login_rsp['success']
    eventContext = login_rsp['eventContext']
    # With successful login, request.session will contain
    # OMERO session details and reconnect to OMERO on each subsequent call...

    return images_url, datasets_url, session


def run_script():
    # needs to be run with python3 and the following arguments:
    parser = argparse.ArgumentParser(prog="Argparse")
    parser.add_argument('--filetype', '-f',
                        help='choose output format: JSON or HTML or Markdown. Possible values: JSON, HTML, MD',
                        nargs='?', default='json')
    parser.add_argument('--ids', '-i',
                        help="space separated list of OMERO IDs (e.g. 1 2 45), min. number of IDs = 1",
                        nargs='+')
    parser.add_argument('--owner', '-o',
                        help='username in OMERO who owns the data',
                        action="store")
    parser.add_argument('--number', '-n',
                        help='number to identify created file (e.g. timestamp or ELN-Object permId)',
                        action="store")
    parser.add_argument('--dtype', '-d',
                        help='specify the type of the OMERO IDs (Possible values: IMAGES, DATASET)',
                        action="store")
    args = parser.parse_args()

    # openBIS user calling the script
    omeroUsername = args.owner 

    # Type of given IDs: Dataset or Images 
    idtype = args.dtype

    # ID List of all Images or Datasets we want to get metadata from
    idList = args.ids

    # Number to label output file with
    ident = args.number

    # List of output files wanted
    ftypeList = args.filetype

    # dictionary to store metadata
    metadata = {}
    try:
        # get omero session via JSON-API
        images_url, datasets_url, session = get_omero_session()
    except Exception as e:
        print("Error in get_omero_session: ", str(e))
    try:
        # get core metadata for all IDs in idList, save first ID of dict
        metadata = get_core_metadata(omeroUsername, idList, idtype, metadata, images_url, datasets_url, session)
        headers = get_headers(metadata)
    except Exception as e:
        print("Error in get_core_metadata or get_headers(): ", str(e))
        metadata = {}

    # if output should be saved and metadata is not empty
    if SAVE_OUTPUT == True and bool(metadata) != False:
        try:
            save_output(metadata, headers, ident, ftypeList)
        except Exception as e:
            print("Error in save_output(): ", str(e))
    # output should not be saved and/or metadata is empty
    else:
        pass

    # print errors first, then metadata
    print(metadata)

if __name__ == "__main__":
    run_script()
