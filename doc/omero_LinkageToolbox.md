<a id="readme-top"></a>
<!-- GETTING STARTED -->
# omero_LinkageToolbox: Linking with OMERO via drag and drop

To link your ELN object with OMERO, simply drag and drop or paste the URL of your ELN object onto the selected elements in OMERO (such as Datasets or Images). This action prompts OMERO to send a [*.eln](schema.md) file containing the metadata of all associated images to your ELN, creating a new ELN entry linked to your chosen ELN object.

To incorporate data bridging into your infrastructure, please follow the steps outlined below. 

### Supported ELN platforms
- openBIS version >=20.10.8

## Prerequisites

Check your Python installation on **omero-server**:
* Python version >=3.9;
* make sure the following Python modules are installed on your **omero-server**:
  ```
  omero-py (tested with v5.19.5)
  rocrate (tested with v0.11.0)
  ```


## Installation
**Definitions:**
- **`$ELN_INSTANCE_DIR`** is the path on the e.g. eln-server where your eln is installed (e.g. ***/home/openbis/openbis/***).
- **`$ELN_SHARE`** is the watch folder on your eln-server (e.g. ***/home/openbis/dataBridge_omero***)


The **omero_LinkageToolbox** allows you to combine your OMERO instance with any of the supported ELN platforms. Follow the steps for both OMERO and your chosen ELN platform

 
### Steps for OMERO:

1. Mount ELN share **`$ELN_SHARE`** as **`$DROPBOX_MNT`**
2. Download the **[ELN_Writer.py](../src/omero_LinkageToolbox/ELN_writer.py)** script and edit its configuration section:
    ```sh
    # the output path for building the .eln file 
    OUTPUT_PATH = "/tmp"
    # the ELN Share receiving the .eln files
    ELN_SHARE = §DROPBOX_MNT
    # the url of your ELN instance
    ELN_URI = "https://myELN.de"
    # the url of your OMERO instance
    OMERO_URI = "https://omero.institute.de"
    ```
    
3. Upload the script **`ELN_Writer.py`** to your omero instance (see the "[HowTo upload a server-side script in OMERO](https://omero-guides.readthedocs.io/en/latest/scripts/docs/write_scripts.html)" guide) in order to run it as a server-side script.
4. On **`omero-server`** check if all Python modules listed in [required modules](../src/omero_LinkageToolbox/requirements_omero.txt) are installed


### Steps for openBIS:
1. To create a dropbox, navigate first to **`$ELN_INSTANCE_DIR/servers/core-plugins`** and create a directory structure for your dropbox (for example, creating the directory structure ***dataBridge/1/dss/drop-boxes/omero-dropbox***)
    ```sh
    cd $ELN_INSTANCE_DIR/servers/core-plugins/
    mkdir -p dataBridge/1/dss/drop-boxes/omero-dropbox
    ```

2. Copy **[omero-receiver.py](../src/omero_LinkageToolbox/omero-receiver.py)** to the **`omero-dropbox`** folder and specify **`EMAIL_FROM`** and **`EMAIL_TO`** to send a notification mail to the dropbox administrator if any issues arise during operation.

3. In the **`omero-dropbox`** directory, create and configure the **`plugin.properties`** file (see [plugin.properties](../src/omero_LinkageToolbox/plugin.properties) for details)

4. Add your core-plugin (e.g. ***dataBridge***) to the list of `enabled-modules` in **`$ELN_INSTANCE_DIR/servers/core-plugins/core-plugins.properties`**

5. Don't forget to create the watch folder **`$ELN_SHARE`** on your openBIS-server 
    ```sh
    cd /home/openbis/
    mkdir dataBridge_omero
    ```
6. Configure **`$ELN_SHARE`** as SHARE and grant **omero-server** write access to that folder
7. Restart DSS server

   After the restart the dropbox should be listed in the eln-lims GUI under `Dropbox Monitor`.


<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- USAGE EXAMPLES -->
## Usage

1. Click on /select the dataset or images you want to link with the **omero_LinkageToolbox**.
2. Click on OMEROs script button and choose the script **ELN_writer**.

  <img src="./images/Screenshot 2024-12-04 102417.png" alt="OMERO.web" style="width:70%; height:auto;">

3. The **ELN_writer** will open in a new window.
If pre-chosen, the dataset or image IDs and their data type are already written to the "IDs" and "Data Type" field. Otherwise type in all IDs you want to link and select the corresponding data type.
If you choose Dataset: Pay attention to the ELN link option, which defines if you want a link to the ELN experiment on all images in the dataset or solely on the dataset itself.
Choose which metadata to include in the linkage.
Don´t forget to paste or drag and drop the ELN url!
Finally "Run script".

  <img src="/blob/main/doc/images/Screenshot 2024-12-03 182723.png" alt="ELN_writter script GUI" style="width:50%; height:auto;">


**If your ELN is openBIS:**

An entry with the name „OMERO data“ will be created and linked to your pasted /drag&drop object.

<img src="./images/Screenshot 2024-12-04 125501.png" alt="openBIS Collection listing" style="width:50%; height:auto;">

Results in preview mode:

<img src="./images/Screenshot 2024-12-04 140037.png" alt="openBIS Entry preview" style="width:50%; height:auto;">

<p align="right">(<a href="#readme-top">back to top</a>)</p>


