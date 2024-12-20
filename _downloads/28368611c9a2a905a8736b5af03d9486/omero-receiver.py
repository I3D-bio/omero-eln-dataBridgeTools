#! /usr/bin/env python

# The omero-receiver performs all steps required for registering the information coming from OMERO.
# Expected as input an *.eln format (see specification at doc/schema.md (TODO))
# Represents transfered values as table in an ENTRY object as child of the object for which the PERMID is specified. 

# Copyright (C) <2024>  <Susanne Kunis>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.



import os
import pprint
import json

import subprocess
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders


try:  # to enable local tests
    from ch.systemsx.cisd.openbis.dss.generic.shared import ServiceProvider
    from ch.ethz.sis.openbis.generic.asapi.v3.dto.sample.search import SampleSearchCriteria
    from ch.ethz.sis.openbis.generic.asapi.v3.dto.experiment.search import ExperimentSearchCriteria
    from ch.ethz.sis.openbis.generic.asapi.v3.dto.experiment.fetchoptions import ExperimentFetchOptions
    from ch.ethz.sis.openbis.generic.asapi.v3.dto.sample.fetchoptions import SampleFetchOptions
except ImportError:
    print("No  openbis imports")

try:
    import rocrate

    PARSE_BY_ROCRATE = True
except ImportError:
    PARSE_BY_ROCRATE = False

ERROR_CODE="<h2>Transmitted data from OMERO could not be read!</h2> <br> Please contact your <b>system administrator</b> if the problem persists.<br> <textarea rows='7' cols='40' >%s</textarea>"
EMAIL_FROM="openbis-system@institute.de"
EMAIL_TO="responsible_person@insitute.de"

OMERO_AUTHOR = "OMERO Web Server OS"
# ------------------------------------------------------------
# property keys to map openbis ELN format (see doc/schema.md (TODO))
PROP_ID = "identifier" # Dataset::identifier
PROP_TYPE = "additionalType" # Dataset::additionalType
PROP_VALUE = "text"  # Dataset::text, property name for the value
PROP_DATASET_NAME = "name" # Dataset::name
PROP_SOFTWARE_ITEM = "instrument"  # CreateAction::instrument; property name where the software is linked
PROP_SOFTWARE = "name" # CreateAction::name
PROP_DATASET_ITEM = "hasPart"  # property name of the data link
PROP_USER_ITEM = "creator" # Dataset::creator
PROP_USER_NAME = "alternateName" # Person::alternateName


def load_json(filename):
    with open(filename, 'r') as file:
        return json.load(file)


# Function to find object by @id and return whole item
def find_object_by_id(data, target_id):
    for item in data.get('@graph', []):
        if item.get('@id') == target_id:
            return item
    return None


def find_object_by_type(data, target_type):
    results = []
    for item in data.get('@graph', []):
        if item.get('@type') == target_type:
            results.append(item)
    return results



def printout(message, transaction=None):
    if transaction:
        transaction.getLogger().info(message)
    else:
        pprint.pprint(message)

# ------------------------------------------------------------
# classes to parse the rocrate as json file if rocrate module is not available
# ------------------------------------------------------------
class ROCrateJSONReader:
    def __init__(self, json_file):
        self.json_file = json_file
        self.err =""
        self.rocrate = self.load_rocrate()
        self.content = self.parse_profile('openbis')

    def load_json(filename):
        with open(filename, 'r') as file:
            return json.load(file)

    def load_rocrate(self):

        try:
            with open(self.json_file, 'r') as file:
                return json.load(file)
        except (IOError, ValueError)as e:
            self.err ="Parse json file failed"
            raise e
            #raise Exception("Error loading ROCrate file")

    def parse_profile(self, profile):
        """Parse the ROCrate for a specific profile and return dict"""
        if self.rocrate is None:
            raise Exception("No ROCrate loaded")

        # parsed_data={}

        if profile == 'basic':
            pass
        if profile == 'openbis':
            result= ContentWrapper(self.rocrate)
	    self.err = result.err
            return result
        else:
            self.err="Unknown profile"

        # return parsed_data
        return None


class ContentWrapper:
    def __init__(self, json_data):
        self.json_data = json_data
        self.err=""
        self.root_obj = self.parseRoot()
        self.root_data = self.getRootItem()  # root item

        self.softwareName = self.parse_SoftwareName()

        if self.root_obj:
            self.root_type = self.root_obj.type
            self.root_id = self.root_obj.identifier
        else:
            self.root_type = None
            self.root_id = None

        self.dataset_obj = self.parseData()

        if self.dataset_obj:
            self.user = self.dataset_obj.creatorName
            self.objType = self.dataset_obj.type
            self.value = self.dataset_obj.text
            self.objName = self.dataset_obj.name
        else:
            self.user = None
            self.objType = None
            self.value = None
            self.objName = None

    def getRootItem(self):
        if self.root_obj:
            return self.root_obj.root
        self.err="No Root entry"
        return None

    def parseRoot(self):
        return self.Root_data(self.json_data)

    def parseData(self):
        if self.root_obj:
            hasPart = self.root_obj.hasPart
            if hasPart and '@id' in hasPart:
                return self.DataEntry(self.json_data, hasPart['@id'])
        self.err="No Data entry"
        return None

    def getDataItem(self):
        if self.dataset_obj:
            return self.dataset_obj.dataset
        self.err="No Dataset entry"
        return None

    def parse_SoftwareName(self):
        obj = self.CreateAction(self.json_data)
        if obj:
            createAction = obj.item
            if not createAction:
                self.err = "Can't parse CreateAction item: "+obj.err
                return None
            linkedSoftware = createAction.get(PROP_SOFTWARE_ITEM)
            if linkedSoftware and '@id' in linkedSoftware:
                softwareApplication = find_object_by_id(self.json_data, linkedSoftware['@id'])
                if softwareApplication:
                    return softwareApplication.get(PROP_SOFTWARE)
                else:
                    self.err="Error pasring SoftwareApplication"
        else:
            self.err="Error parsing CreateAction"
        return None

    class Root_data:
        def __init__(self, json_data):
            self.root = self.parse(json_data)  # root_item
            self.type = self.root.get(PROP_TYPE)
            self.identifier = self.root.get(PROP_ID)
            self.hasPart = self.root.get(PROP_DATASET_ITEM)

        def parse(self, json_data):
            return find_object_by_id(json_data, "./")

    class DataEntry:
        def __init__(self, json_data, id):
            self.dataset = self.parse(json_data, id)
            self.creatorName = self.parseCreator(json_data)
            self.type = self.dataset.get(PROP_TYPE)
            self.text = self.dataset.get(PROP_VALUE)
            self.name = self.dataset.get(PROP_DATASET_NAME)

        def parse(self, json_data, id):
            return find_object_by_id(json_data, id)

        def parseCreator(self, json_data):
            if self.dataset:
                creatorLink = self.dataset.get(PROP_USER_ITEM)
                if creatorLink and '@id' in creatorLink:
                    creator = find_object_by_id(json_data, creatorLink['@id'])
                    if creator:
                        return creator.get(PROP_USER_NAME)
            return None

    class CreateAction:
        def __init__(self, json_data):
            self.err=""
            self.item = self.parse(json_data, './')
            

        def parse(self, json_data, objectID):
            objects = find_object_by_type(json_data, "CreateAction")
            for o in objects:
                self.err=self.err+"Search for './', Check "+o.get("object")['@id']
                if o.get("object")['@id'] == objectID:
                    self.err=self.err+"-- found"
                    return o
            return None


# ------------------------------------------------------------
# load experiment specified by PermID from openBIS
# ------------------------------------------------------------
def getExistingExperiment(expPermID, transaction):
    printout("Query Experiment: " + expPermID, transaction)
    service = ServiceProvider.getV3ApplicationService()
    sessionToken = transaction.getOpenBisServiceSessionToken()

    searchCriteria = ExperimentSearchCriteria()
    searchCriteria.withPermId().thatEquals(expPermID)

    fetchOptions = ExperimentFetchOptions()
    fetchOptions.sortBy().registrationDate().asc()
    experimentList = service.searchExperiments(sessionToken, searchCriteria, fetchOptions).getObjects()
    exp = None
    id = None
    if len(experimentList) > 0:
        exp = transaction.getExperiment(experimentList[0].getIdentifier().getIdentifier())
        if exp is not None:
            id = exp.getExperimentIdentifier()
            printout(id, transaction)
    else:
        printout("Can't fetch EXPERIMENT with given permID", transaction)

    return id, exp

# ------------------------------------------------------------
# load sample specified by PermID from openBIS
# ------------------------------------------------------------
def getExistingSample(id, transaction, type):
    printout("Query Sample: " + id, transaction)
    service = ServiceProvider.getV3ApplicationService()
    sessionToken = transaction.getOpenBisServiceSessionToken()

    searchCriteria = SampleSearchCriteria()
    if type == "PERM_ID":
        searchCriteria.withPermId().thatEquals(id)
    elif type == "CODE":
        searchCriteria.withCode().thatEquals(id)
    elif type == "IDENTIFIER":
        searchCriteria.withIdentifier().thatEquals(id)

    fetchOptions = SampleFetchOptions()
    fetchOptions.sortBy().registrationDate().asc()
    objectList = service.searchSamples(sessionToken, searchCriteria, fetchOptions).getObjects()
    obj = None
    id = None
    if len(objectList) > 0:
        obj = transaction.getSampleForUpdate(objectList[0].getIdentifier().getIdentifier())
        if obj is not None:
            id = obj.getSampleIdentifier()
            printout(id, transaction)
    else:
        printout("Can't fetch SAMPLE with given permID", transaction)

    return id, obj




# ------------------------------------------------------------
# fetch parent object from openBIS to add the ENTRY as child
# ------------------------------------------------------------
def fetchParent(permID, type, transaction):
    id = None
    parentObj = None
    
    printout("Fetch parent object",transaction)

    # try to fetch parent as EXPERIMENT object
    if type is None or type == "" or type == "Experiment":
        id, parentObj = getExistingExperiment(permID, transaction)
        if parentObj is not None and id is not None:
            printout("Parent EXPERIMENT object: "+id, transaction)
            return id, parentObj,None

    # can't fetch EXPERIMENT: try to fetch a SAMPLE
    id, object = getExistingSample(permID, transaction,"PERM_ID")
    if object is None or id is None:
        printout("ERROR: Can't find any parent with permID: "+permID, transaction)
        return None, None, None
    space = object.getSpace()
    parentObj = object.getExperiment()

    printout("Fetch parent object successfully",transaction)

    return id, parentObj,space



# ------------------------------------------------------------
# create new object ENTRY with provided information from OMERO 
# and link it to the given parent object
# ------------------------------------------------------------
def addEntryObj(content, transaction):
    err_message=""

    permID = content.root_id
    publisher = content.softwareName
    userName = content.user

    if not userName:
        err_message = "ERROR parsing userName"
        return False,err_message
    if not permID:
        err_message="ERROR parsing permID"
        return False,err_message

    printout("Parsed Infos: permID= " + permID, transaction)
    printout("Parsed Infos: uName= " + userName, transaction)
    printout("Parsed Infos: publisher= "+publisher, transaction)

    # todo usercheck
    # transaction.getAuthorizationService().doesUserHaveRole(userName,ROLE,SPACENAME)

    # only read in information coming from OMERO
    if publisher != OMERO_AUTHOR:
        printout("Incoming file is not a valid OMERO *.eln",transaction)
        err_message="Incoming file is not a valid OMERO *.eln."
        return False,err_message
        
    else:
        htmlString = content.value
        name = content.objName
        type_childObj = content.objType
        type_parentObj = content.root_type

        printout("Parsed Infos: name= "+name, transaction)
        printout("Parsed Infos: typeChild= "+type_childObj, transaction)
        printout("Parsed Infos: typeParent= "+type_parentObj, transaction)
        printout("Parsed Infos: html= "+htmlString, transaction)

        # get parent obj handle in eln database
        parentID, parentObj, space = fetchParent(permID, type_parentObj, transaction)
        if parentID is None or parentObj is None:
            # TODO: error handling for no parent could be fetched
            # write email to openbis-admin?
            return False, "Can't fetch parent obj of given permID: %s"%permID

        printout("Parent identifier: "+parentID, transaction)

        if htmlString is "NOTHING":
            htmlString = ERROR_CODE%("Failed to integrate OMERO data for:\nIdentifier: %s,\nPermID: %s,\nContent Incoming File:\n%s"%(parentID,permID,content) )
        
        sample = transaction.createNewSampleWithGeneratedCode(space, type_childObj)
        printout("Create new SAMPLE PermID: "+sample.getPermId(), transaction)
            
        sample.setPropertyValue("$NAME", name)
        sample.setPropertyValue("$DOCUMENT", htmlString)
        # sample.setPropertyValue("$SHOW_IN_PROJECT_OVERVIEW",True)
        sample.setExperiment(parentObj)  
        # create parent link
        sample.setParentSampleIdentifiers([parentID])

    return True,None

# ------------------------------------------------------------
# unzip and parse incoming file
# ------------------------------------------------------------
def parseFile(path, transaction=None):
    
    err_message="" 
    # only process *.eln files
    # get file extension
    _,extension=os.path.splitext(path)
    if extension.lower()!=".eln":
        printout("No *.eln format",transaction)
        err_message= "No valid file format for this dropbox (required: *.eln)."
        return err_message,None
    try:
        import zipfile
        import shutil
        import tempfile

        extract_path = tempfile.mkdtemp(prefix="incoming-omero",dir="/tmp")  # jython 2.7 compatible
    except ImportError:
        err_message="Can't import required python modules (req: zipfile,shutil,tempfile)"
        return err_message,None
    

    try:
        # unzip input
        with zipfile.ZipFile(path, "r") as zObj:
            zObj.extractall(path=extract_path)

        filename_without_extension = os.path.splitext(os.path.basename(path))[0]
        roCrateDir=extract_path
        exists = os.path.exists(roCrateDir)

        if not exists:
            err_message="Error while unzipping file"
            return err_message,None

        if PARSE_BY_ROCRATE:
            # TODO: delete or add
            printout("parse by ro-crate Reader",transaction)
            reader = ROCrate(roCrateDir)
        else:
            printout("parse by JSON Reader",transaction)
            reader = ROCrateJSONReader(os.path.join(roCrateDir, "ro-crate-metadata.json"))
            
    finally:
        shutil.rmtree(extract_path)

    return reader.err,reader.content




def send_email(message_body, transaction):
    # Create the email
    msg = MIMEMultipart()
    msg['From'] = EMAIL_FROM  # Sender's email address
    msg['To'] = EMAIL_TO
    msg['Subject'] = "Dropbox OMERO Error Report"

    attachment_file=transaction.getIncoming().getAbsolutePath()

    # Attach the message body
    msg.attach(MIMEText(message_body, 'plain'))

    # Prepare the attachment
    if attachment_file and os.path.exists(attachment_file):
        part = MIMEBase('application', 'octet-stream')
        with open(attachment_file, 'rb') as attachment:
            part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="%s"'%os.path.basename(attachment_file))

        # Attach the file to the message
        msg.attach(part)

    # Convert message to string format
    email_message = msg.as_string()

    # Send the email
    try:
        process = subprocess.Popen(
            ["/usr/sbin/sendmail", "-t"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Send the email through the process's stdin
        stdout, stderr = process.communicate(input=email_message.encode())

        if process.returncode == 0:
            printout("ERROR report email sent successfully out.",transaction)
        else:
            printout("Failed to send ERROR report email.",transaction)
            
    except Exception as e:
        printout("An error occurred while sending ERROR Report mail",transaction)



# ------------------------------------------------------------
# process incoming file
# ------------------------------------------------------------
def process(transaction):
    transaction.getLogger().info("Incoming data at %s" % transaction.getIncoming().getName())
    
    err,content = parseFile(transaction.getIncoming().getAbsolutePath(), transaction)
    printout("Errors while parsing eln content: "+err,transaction)
    if content:
        printout("JSON content from file successfully parsed",transaction)
        success,message=addEntryObj(content, transaction)
        
        if not success:
           # TODO: delete *.eln file because something went wrong: replace MOVE_TO_ERROR by DELETE in plugin.properties
           send_email(message,transaction)
            
    else:
        send_email("Can't parse file content",transaction)
        raise Exception(err)

