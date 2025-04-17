import re
import os.path
import omero
import omero.api
import omero.scripts as scripts
from omero.rtypes import rstring, rlong, robject, unwrap
from omero.gateway import BlitzGateway
from omero.util.tiles import *
from omero.model import *
from datetime import datetime
import csv
import shutil
import urllib
try:
    import rocrate
    from rocrate.utils import iso_now
    from rocrate.rocrate import ROCrate
    from rocrate.model import Person, SoftwareApplication
    PARSE_BY_ROCRATE = True
except ImportError:
    PARSE_BY_ROCRATE = False
import json
try:
    import pathlib
    import zipfile
except ImportError:
    print("could not import zip modules")


#######################################################################
#           Configuration
#######################################################################

# path where .eln file is build
OUTPUT_PATH = # eg.: '/tmp'
# type of ELN you are using
ELN_TYPE = # Currently supported: "OPENBIS", "ELABFTW"
# the ELN Share receiving the .eln files
ELN_SHARE = '/my/share'  # if your ELN_TYPE is OPENBIS put the path to the dropbox (e.g. '/openbis-dropbox')
# url of your eln instance
ELN_URI = "https://my.eln.de"
# url of your omero instance
OMERO_URI = "https://my.omero.de"

#######################################################################

# GUI param names
PARAM_DATATYPE = "Data_Type"
PARAM_IDS = "IDs"
PARAM_OBISOBJ = "Drag and drop /paste ELN object url here"
PARAM_LINK = "If the data type is 'Dataset', attach the ELN-link to"
PARAM_TAG = "Include tags"
PARAM_KV = "Include key-value pairs"
PARAM_ATT = "Include attachments"
PARAM_COM = "Include comments"
PARAM_RAT = "Include rating"

######################################################################

def link_ELN(conn, obj, link):
    print("link_ELN()")
    comm_ann = omero.gateway.CommentAnnotationWrapper(conn)
    comm_ann.setValue(rstring(link))
    comm_ann.setDescription("ELN link set by ELN_writer (OMERO-linkage-toolbox)")
    comm_ann.save()
    obj.linkAnnotation(comm_ann)


def zip_crate(rsltfldr):
    print("zip_crate()")
    # zip rocrate
    tozip = pathlib.Path(rsltfldr)
    #print("tozip: ", tozip)
    with zipfile.ZipFile("%s.zip" % rsltfldr, mode="w") as archive:
        for filepath in tozip.iterdir():
            #print("filepath: ", filepath)
            archive.write(filepath, arcname=filepath.name)
    print("zipped rocrate")
    # change .zip to .eln
    os.rename(f"{rsltfldr}.zip", f"{rsltfldr}.eln" )
    print("renamed .zip to .eln")


def root_dict(conn, permID):
    print("root_dict()")
    # root entitie dict
    # get OMERO user info
    try:
        username = conn.getUser().getName()
        if not username:
            raise ValueError('OMERO username is empty')
    except ValueError as e:
        raise e
    rootdict = {}
    rootdict["@id"] = "./"
    rootdict["@type"] = "Dataset"
    rootdict["name"] = "parent dataset"
    rootdict["identifier"] = "%s" % permID
    rootdict["additionalType"] = ""
    rootdict["creator"] = {"@id": "#%s" % username} 
    rootdict["author"] = {"@id": "#%s" % username}
    rootdict["dateCreated"] = datetime.now()
    rootdict["dateModified"] = datetime.now()
    rootdict["datePublished"] = datetime.now()
    
    rootdict["hasPart"] = {"@id": "#%s" % OMERO_URI}

    return rootdict


def creativework_dict():
    print("creativework_dict()")
    # CreativeWork dict
    creativeworkdict = {}
    creativeworkdict["@id"] = "ro-crate-metadata.json"
    creativeworkdict["@type"] = "CreativeWork"
    creativeworkdict["about"] = {"@id": "./"}
    creativeworkdict["conformsTo"] = {"@id": "https://w3id.org/ro/crate/1.1"}

    return creativeworkdict
    

def person_dict(conn):
    print("person_dict()")
    # get OMERO user info
    try:
        username = conn.getUser().getName()
        if not username:
            raise ValueError('Error: OMERO username is empty')
    except ValueError as e:
        raise e
    try:
        name_parts = re.split(r"\s+", conn.getUser().getFullName())
        if not name_parts:
            raise ParseError('Error while parsing OMERO full name')
    except Exception as e:
        raise e
    # Person dict
    persondict = {}
    persondict["@id"] = "#%s" % username
    persondict["@type"] = "Person"
    persondict["alternateName"] = username
    persondict["familyName"] = name_parts[1] if len(name_parts)>1 else '' # TODO: is it really required
    persondict["givenName"] = name_parts[0] # TODO: is it really required
    
    return persondict["@id"], persondict


def softwareappl_dict():
    print("softwareappl_dict()")
    # SoftwareApplication dict
    softwareappldict = {}
    softwareappldict["@id"] = "#OMERO"
    softwareappldict["@type"] = "SoftwareApplication"
    softwareappldict["name"] = "OMERO Web Server OS"
    softwareappldict["installUrl"] = {"@id": OMERO_URI}
    softwareappldict["softwareVersion"] = "0.1.0"

    return softwareappldict["@id"], softwareappldict


def createact_dict():
    print("createact_dict()")
    # CreateAction dict
    createactdict = {}
    createactdict["@id"] = "#OMERO"
    createactdict["@type"] = "CreateAction"
    createactdict["name"] = "RO-Crate created"
    createactdict["description"] = "provenance of entity"
    createactdict["object"] = {"@id": "./"}
    createactdict["instrument"] = {"@id": "#OMERO", "description": "Software that was used to produce this file"}
    createactdict["actionStatus"] = {"@id": "http://schema.org/CompletedActionStatus"}
    createactdict["endtime"] = datetime.now()

    return createactdict


def metadata_dict(permID, persondictid, htmltable):
    print("metadata_dict()")
    # OMERO metadata dict 
    metadatadict = {}
    metadatadict["@id"] = "#%s" % OMERO_URI
    metadatadict["@type"] = "Dataset"
    metadatadict["additionalType"] = "ENTRY"
    metadatadict["name"] = "OMERO data"
    metadatadict["identifier"] = permID
    metadatadict["text"] = htmltable
    metadatadict["creator"] = {"@id": "%s" % persondictid}
    metadatadict["dateCreated"] = datetime.now()
    metadatadict["dateModified"] = datetime.now()

    return metadatadict


def serialize_datetime(obj):
    print("serialize_datetime()")
    if isinstance(obj, datetime): 
        return obj.isoformat() 
    raise TypeError("Type not serializable") 


def save_to_json(conn, permID, rsltfldr, htmltable):
    print("save_to_json()")
    # create rocrate as dict
    rocratedict = {}
    rocratedict["@context"] = "https://w3id.org/ro/crate/1.1/context"
    # list with all dicts to be in ro-crate-metadata.json
    dictsinrocrate = []
    # first dict gives rocrate basic information
    dictsinrocrate.append(creativework_dict())
    # append more dicts
    try:
        dictsinrocrate.append(root_dict(conn, permID))
        persondictid, persondict = person_dict(conn)
    except Exception as e:
        print(e)
        return
    dictsinrocrate.append(persondict)
    softwareappldictid, softwareappldict = softwareappl_dict()
    dictsinrocrate.append(softwareappldict)
    dictsinrocrate.append(createact_dict())
    dictsinrocrate.append(metadata_dict(permID, persondictid, htmltable))
    # put all dicts from list in rocratedict
    rocratedict["@graph"] = dictsinrocrate
    # write json rocrate to file
    try:
        # Serializing json
        json_object = json.dumps(rocratedict,default=serialize_datetime ,indent=4)
        # Writing to rsltfolder
        jsonpath = rsltfldr + "/ro-crate-metadata"
        with open("%s.json" % jsonpath, "w") as outfile:
            outfile.write(json_object)
    except Exception as e:
        print("Error while writing json rocrate")


def save_to_rocrate(conn, permID, rsltfldr, htmltable):
    print("save_to_rocrate()")
    crate = ROCrate()
    crate.name = permID

    # creation info
    current_time = iso_now()
    crate.root_dataset["dateCreated"] = "%s " % current_time
    crate.root_dataset["dateModified"] = "%s " % current_time
    
    # author: get OMERO user info
    try:
        user = conn.getUser()
        userName = user.getFullName()
        name_parts = re.split(r"\s+", userName)
        author = crate.add(Person(crate, user.getName(), 
            properties={"alternateName": user.getName(), 
                "familyName": name_parts[1] if len(name_parts)>1 else '',
                "givenName": name_parts[0]
                }))
    except Exception as e:
        print("Error when getting OMERO user info")
        raise e
    crate.root_dataset["author"] = author
    crate.root_dataset["creator"] = author

    # CreateAction 
    # not available in current RO-Crate but in specification (check next version) therefore added manually in json (see below)
    #createaction = crate.add_action(CreateAction(crate, identifier="#ro-crate_created", 
    #    properties={"name": "RO-Crate created","description": "provenance of entity", "object": {"@id": "./"}, "endTime": "tiiime", "instrument": {"@id": "#OMERO", "description": "Software that was used to produce this file"}, "actionStatus": {"@id": "http://schema.org/CompletedActionStatus"}}))

    # SoftwareApplication 
    software = crate.add(SoftwareApplication(crate, identifier="#OMERO", 
        properties={"name": "OMERO Web Server OS", "installUrl": {"@id": OMERO_URI}, "softwareVersion": "0.1.0"}))
    #crate.root_dataset["isBasedOn"] = software

    # add ELN parent object info
    crate.root_dataset["name"] = "parent dataset"
    crate.root_dataset["identifier"] = permID
    crate.root_dataset["additionalType"] = ""

    # add OMERO metadata as dataset
    name = "OMERO data"
    dataset = crate.add_dataset("%s" % OMERO_URI, 
        properties={"name": name, "author": "", "creator": "", "identifier": "", "dateCreated": "%s" %current_time, "dateModified": "%s" %current_time, "additionalType": "ENTRY"})
    crate.root_dataset["hasPart"] = dataset
    dataset["author"] = author
    dataset["creator"] = author
    # html table as text
    dataset["text"] = htmltable

    # Serialize crate
    try:
        crate.write(rsltfldr)
    except PermissionError as e:
        print("Cannot write rocrate to file to %s" % rsltfldr)
        return

    # Add CreateAction in json
    try:
        jsonpath = rsltfldr + "/ro-crate-metadata.json"
        with open(jsonpath,'r+') as file:
            # load existing data into a dict
            file_data = json.load(file)
            # Join new_data with file_data inside
            crateAction = {"@id": "#ro-crate_created", "@type": "CreateAction", "identifier": "#ro-crate_created", "name": "RO-Crate created", "description": "provenance of entity", "object": {"@id": "./"}, "endTime": "%s" %current_time, "instrument": {"@id": "#OMERO", "description": "Software that was used to produce this file"}, "actionStatus": {"@id": "http://schema.org/CompletedActionStatus"}}
            file_data["@graph"].append(crateAction)
            # Sets file's current position at offset
            file.seek(0)
            # convert back to json
            json.dump(file_data, file, indent=4)
            print("json added to rocrate")
    except Exception as e:
        print("Error while adding CreateAction in json")
        return

    '''# print rocrate
    try:
        with open(jsonpath, "r") as read_file:
            obj = json.load(read_file)
            pretty_json = json.dumps(obj, indent=4)
            print(pretty_json)
    except Exception as e:
        print("Error in printing ro-crate-metadata.json")'''


def csvToHTMLTable(path):
    print("csvToHTMLTable()")
    with open(path) as csvfile:
        csv_reader = csv.reader(csvfile)
        headers = next(csv_reader)
        # get index of 'Name' to convert the img name into an html link
        indexName = headers.index("Name")
        # get index of 'ID' to build the OMERO link
        indexID = headers.index("ID")
        htmlheader = "<h2>OMERO data</h2>"
        html_table = "<figure class='table' style='width:1000px;'><table border='1'>"

        # insert header
        html_table +="<thead><tr>"
        for header in headers:
            html_table+=f"<th>{header}</th>"
        html_table+="</tr></thead>"
        clean_data=[]

        # Consume the rows for both tags and key-value pairs in a single loop
        tag_index = headers.index("Tags") if "Tags" in headers else None
        kv_index = headers.index("Key-Value Pairs") if "Key-Value Pairs" in headers else None
        
        for row in csv_reader:
            if tag_index is not None: 
                # clean up tags      
                cleanupVal_tag=""
                #TODO: replace eval() by ast.literal_eval() to Safely evaluate an expression node or a string containing a Python literal (import ast necessary)
                for t in eval(row[tag_index]):
                    cleanupVal_tag=cleanupVal_tag+t.get('Name')+","
                row[tag_index]=cleanupVal_tag
            if kv_index is not None:    
                # clean up key-value pairs
                cleanupVal_kv=""
                for k in eval(row[kv_index]):
                    cleanupVal_kv=cleanupVal_kv+k.get('Key')+":"+k.get('Value')+";"
                row[kv_index]=cleanupVal_kv
            clean_data.append(row)

        #create table body    
        html_table += "<tbody>"
        for row in clean_data:
            html_table += "<tr>"
            # convert values at index to html link
            row[indexName] = "<a href=" + OMERO_URI + "/webclient/?show=image-%s" % row[indexID] + ">%s</a>" % row[indexName]
            for col in row:
                html_table += f"<td>{col}</td>"
            html_table += "</tr>"
        html_table += "</tbody></table></figure>"

    return htmlheader+html_table


def save_to_csv(metadataDict, rsltfldr):
    print("save_to_csv()")
    fieldNames = list(metadataDict[list(metadataDict.keys())[0]].keys())
    #print("csv headers: ", fieldNames)
    # nicht statische namen -> sonst ueberschreiben moeglich
    csvPath = os.path.join(rsltfldr, 'metadata_table.csv')
    try:
        with open(csvPath, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldNames)
            writer.writeheader()
            for dicts in list(metadataDict.values()):
                writer.writerow(dicts)
    except IOError:
        print("I/O Error: could not write csv file to rsltfldr")
        return None

    return csvPath


def get_img_metadata(params, image):
    print("get_metadata()")
    # get img name
    imgName = image.getName()
    # get img ID
    imgID = image.getId()
    # get username
    imgOwner = image.getOwnerOmeName()
    # get description
    imgDescr = image.getDescription()
    # get size x
    imgSizex = image.getSizeX()
    # get size y
    imgSizey = image.getSizeY()
    # pixels type
    imgPixel = image.getPrimaryPixels().getPlane(0,0,0).dtype.name
    # get size z
    imgSizez = image.getSizeZ()
    # get size c
    imgSizec = image.getSizeC()
    # get size t
    imgSizet = image.getSizeT()
    infodict =  {'Name': imgName, 'ID': imgID,  'Username': imgOwner, 'Description': imgDescr, 'SizeX': imgSizex,
                 'SizeY': imgSizey, 'Pixel Type': imgPixel,  'SizeZ': imgSizez, 'SizeC': imgSizec, 'SizeT': imgSizet,}
    # tags
    if params.get(PARAM_TAG):
        tagdict = []
        for o in image.listAnnotations():
            # tags
            if o.OMERO_TYPE == omero.model.TagAnnotationI:
                tagdict.append({'Name': o.getValue(), 'Description': o.getDescription()})
        infodict['Tags'] = tagdict
    # key-value pairs
    if params.get(PARAM_KV):
        kvdict = []
        for o in image.listAnnotations():
            # key values
            if o.OMERO_TYPE == omero.model.MapAnnotationI:
                #print("KV Val: ", o.getValue()) # Ergebnis ist [('Channels', 'three')]
                kvdict.append({'Key': o.getValue()[0][0], 'Value': o.getValue()[0][1]})
        infodict['Key-Value Pairs'] = kvdict
    # attachments
    if params.get(PARAM_ATT):
        attlist = []
        for o in image.listAnnotations():
            # attachments
            if o.OMERO_TYPE == omero.model.FileAnnotationI:
                attlist.append(o.getFile().getName())
        infodict['Attachment'] = attlist
    # comments
    if params.get(PARAM_COM):
        commlist = []
        for o in image.listAnnotations():
            # comments
            if o.OMERO_TYPE == omero.model.CommentAnnotationI:
                commlist.append(o.getValue())
        infodict['Comments'] = commlist
    # rating
    if params.get(PARAM_RAT):
        ratlist = []
        for o in image.listAnnotations():
            # Rating
            if o.OMERO_TYPE == omero.model.LongAnnotationI:
                ratlist.append('%s/5' % o.getValue())
        infodict['Rating'] = ratlist

    return infodict


def parse_url(params):
    print("parse_url()")
    # get permID of openBIS Object Link
    obisUrl = params.get(PARAM_OBISOBJ)
    # check if url belongs to the connected ELN
    if re.search("^%s" % ELN_URI, obisUrl):
        # permId is 26 characters and at the end, followed by %22
        try:
            # openBIS object urls contain two permIDs, other openBIS urls only one
            permIDParent = re.findall("\d{17}-\d+", obisUrl)[0]
            permID = re.findall("\d{17}-\d+", obisUrl)[1]
        except IndexError as e:
            print(e, " The openBIS url given is not correct. Only object urls are accepted as input, not collection urls etc.")
            raise IndexError("The openBIS url given is not correct. Only object urls are accepted as input, not collection urls etc.")
    else:
        print("The given url does not belong to the connected ELN")
        raise IndexError(" The given url does not belong to the connected ELN")

    return permID
    

def do_things(conn, params):
    print("do_things()")
    images = []
    metadataDict = {}

    # get ELN object permID from url
    permID = parse_url(params)
        
    # get all ImageIds from Images or Dataset
    if params.get(PARAM_DATATYPE) == 'Image':
        print("Param Datatype = Image")
        imgs = conn.getObjects("Image", params[PARAM_IDS])
        if not imgs:
            return "No images found"
        images = list(imgs)
    else:
        for datasetID in params[PARAM_IDS]:
            print("Param Datatype = Dataset")
            dtset = conn.getObject("Dataset", datasetID)
            if dtset:
                for i in dtset.listChildren():
                    images.append(i)
            else:
                continue
    print("image IDs list: ", images)

    # get metadata dictionary of all images
    if not images:
        return "No images found", None
    err_message = ""
    for i in images:
        # get metadata information
        try:
            imgMetadata = get_img_metadata(params, i)
        except Exception as e:
            raise Exception("Error in reading OMERO img metadata")
        # put metadata information as sub dictionary
        metadataDict["%s" % i.getId()] = imgMetadata
        #print("metadataDict", metadataDict)
        if not metadataDict:
            raise ValueError("metadataDict is empty")

    # create results folder in OUTPUT_PATH
    timestamp = datetime.now().strftime("-%Y-%m-%d-%H-%M-%S")
    rsltfldr = os.path.join(OUTPUT_PATH, permID + timestamp)
    print("rsltfldr", rsltfldr)
    try:
        os.mkdir(rsltfldr)
    except OSError as error:
        print(error)
        raise OSError("Cannot create *.eln")

    # save metadataDict to csv and put that into the results folder in tmp
    csvPath = save_to_csv(metadataDict, rsltfldr)
    if not csvPath:
        raise Exception("Cannot create *.eln")
    # convert csv to html table
    htmltable = csvToHTMLTable(csvPath)

    # save metadata information to rocrate using the .eln file format specifications
    # ROCrate is available on the system
    if PARSE_BY_ROCRATE:
        print("ROCRATE is available")
        try:
            save_to_rocrate(conn, permID, rsltfldr, htmltable)
        except Exception as e:
            print("Error in saving metadata to rocrate")
            raise Exception("Cannot create *.eln")
    # ROCrate is not available on the system, we write a ROCrate with JSON
    else:
        print("ROCRATE is NOT installed")
        try:
            save_to_json(conn, permID, rsltfldr, htmltable)
        except Exception as e:
            print("Error in saving metadata to json")
            raise Exception("Cannot create *.eln")

    # zip rocrate and convert to eln file format (.eln)
    try:
        zip_crate(rsltfldr)
    except Exception as e:
        print(e)
        raise Exception("Error while writing ELN format")

    # move .eln from OUTPUT_PATH to ELN_SHARE
    try:
        shutil.move("%s.eln" % rsltfldr, ELN_SHARE)
    except Exception as e:
        print("could not move .eln: ", e)
        raise Exception("Cannot create *.eln")

    # finally set ELN url as comment
    # if link should be attached to dataset ID only
    if params.get(PARAM_DATATYPE) == 'Dataset' and params.get(PARAM_LINK) == 'only the dataset':
        for datasetID in params[PARAM_IDS]:
            dtset = conn.getObject("Dataset", datasetID)
            try:
                link_ELN(conn, dtset, params.get(PARAM_OBISOBJ))
            except Exception as e:
                print("Could not set ELN url as comment in ELN datasetID: %s)" % datasetID)
                err_message = "Could not set ELN url as comment in ELN for at least one dataset"
    # link should be attached to all images (in dataset)
    else:
        # we already have an image id list
        for i in images:
            try:
                if params.get(PARAM_DATATYPE) == 'Dataset' and params.get(PARAM_LINK) == "all Images (in Dataset)":
                    link_ELN(conn, i, params.get(PARAM_OBISOBJ))
                if params.get(PARAM_DATATYPE) == 'Image':
                    link_ELN(conn, i, params.get(PARAM_OBISOBJ))
            except Exception as e:
                print("Could not set ELN url as comment in ELN (imageID: %s)" % i)
                err_message = "Could not set ELN url as comment in ELN for at least one image"

    return err_message, rsltfldr


def run_as_script():
    """
    The main entry point of the script, as called by the client via the
    scripting service, passing the required parameters.
    """
    # pair of fields named 'Data_Type' (string) and 'IDs'(Long list) is recognized and populated by OMERO
    dataTypes = [rstring('Dataset'), rstring('Image')]
    linkOptions = [rstring('only the dataset'), rstring('all Images (in Dataset)')]

    client = scripts.client('ELN_writer.py',
                            """The ELN_writer.py connects OMERO image metadata and to your experimental metadata stored in an ELN.
                              
                            The script will collect image metadata of the selected images, store them in a *.eln file and send it to your ELN. There, a new entry is created which contains a table listing all images and their metadata including a direct link to the OMERO images. The new entry will be linked to the ELN object pasted. 
                            In OMERO, the selected images or dataset get a comment with a link to the new ELN entry.
                              
                            For Admins:
                            The ELN_writer.py is part of the omero-linkage-toolbox. Examples, a how to and all about configuration options can be found on the website: 
                            https://gitlab.uni-osnabrueck.de/i3dbio/omero-linkage-toolbox
                              
                            """, # noqa
                            scripts.String(PARAM_DATATYPE, optional=False, grouping="1",
                                           description="Select Images or Dataset.", values=dataTypes),
                            scripts.List(PARAM_IDS, optional=False, grouping="2",
                                         description="List Images of Image IDs to process."),
                            scripts.String(PARAM_LINK, optional=False, grouping="3",
                                           description="Attach link to all images or dataset", values=linkOptions),
                            scripts.String(PARAM_OBISOBJ, optional=False, grouping="4",
                                           description="Drag and Drop your ELN experiment here."),
                            scripts.Bool(PARAM_TAG, grouping="5", default=True),
                            scripts.Bool(PARAM_KV, grouping="6", default=True),
                            scripts.Bool(PARAM_ATT, grouping="7", default=True),
                            scripts.Bool(PARAM_COM, grouping="8", default=True),
                            scripts.Bool(PARAM_RAT, grouping="9", default=True),
                            namespaces=[omero.constants.namespaces.NSDYNAMIC],
                            version="1.0.0",
                            authors=["Julia Dohle", "I3D:bio (https://gerbi-gmb.de/i3dbio/)"],
                            institutions=["University of Osnabrueck"],
                            contact="judohle@uos.de",
                            )
    rsltfldr = None
    try:
        # Wrap client to use the Blitz Gateway
        conn = BlitzGateway(client_obj=client)
        conn.keepAlive()
        params = {}
        # Process the list of args above.
        for key in client.getInputKeys():
            if client.getInput(key):
                params[key] = client.getInput(key, unwrap=True)
        message, rsltfldr = do_things(conn, params)
        # Return the output, display message
        if not message:
            message = "*.eln is created and send to ELN"
        client.setOutput("Message", rstring(message))
    except Exception as e:
        print("Cannot create *.eln: ", str(e))
            
        client.setOutput("Message", rstring(e))
    finally:
        if rsltfldr is not None:
            try:
                shutil.rmtree(rsltfldr)
            except Exception as e:
                print("could not remove rsltfldr, error: ", str(e))
        client.closeSession()
    pass


if __name__ == "__main__":
    run_as_script()
