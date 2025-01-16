##########
import asyncio
from js import document,alert,console,window
from pyodide.http import pyfetch
from pyscript import display
from pyweb import pydom
import json
import pandas as pd
from pyodide.ffi import create_proxy,to_js
###########
from pprint import pprint
from datetime import datetime as dt
####################################
from tempfile import NamedTemporaryFile
import webbrowser
import re
###############
step1_message = "STEP1: Login using your ICA credentials"
pydom["h1#step1-message"].html = step1_message
step2_message = "STEP2: Identify ICA project to get ICA project id. <br> Use search bar to query table <br> once project is found, below the table enter a project name and click on the 'Select Project' button"
pydom["h1#step2-message"].html = step2_message
step3_message = "STEP3: Identify analysis to get ICA analysis id. <br> Use search bar to query table <br> once project is found, below the table enter an analysis name, and click on the 'Select Analysis' button"
pydom["h1#step3-message"].html = step3_message

step4_message = "STEP4: Generate requeue template CLI or API"
pydom["h1#step4-message"].html = step4_message
#######################
### hide elements until we are ready
pydom["div#step2-selection-form"].style["display"] = "none"
pydom["div#step3-selection-form"].style["display"] = "none"
pydom["div#step4-selection-form"].style["display"] = "none"
pydom["div#requeue-template-download"].style["display"] = "none"
pydom["section#learn-the-steps"].style["display"] = "none"

################
ICA_BASE_URL = 'https://ica.illumina.com/ica'
import base64
#### info we'll collect from the html 
authorization_metadata = dict()
analysis_metadata = dict()
analysis_metadata['step4-api'] = []
##########################
async def curlify(method="GET",endpoint="FOOBAR",header={},body={}):
    curlified_command_components = []
    curlified_command_components.append(f"curl -X '{method}' \\")
    curlified_command_components.append(f" '{endpoint}' \\")
    for key in list(header.keys()):
        curlified_command_components.append(f"-H '{key}:" + f" {header[key]}' \\")
    if len(body) > 0:
        rest_of_command = json.dumps(body, indent = 4)
        curlified_command_components.append(f"-d '{rest_of_command}'")
    # strip out any trailing slashes
    curlified_command_components[len(curlified_command_components)-1].strip('\\')
    curlified_command = "\n".join(curlified_command_components)
    print(f"{curlified_command}")
    return curlified_command

### helper functons to paginate pandas tables

def df_html(df):
    """HTML table """
    df_html = df.to_html()
    return df_html

##################    
async def get_jwt(username,password,tenant = None):
    #######
    encoded_key = base64.b64encode(bytes(f"{username}:{password}", "utf-8")).decode()
    ################ Get JWT
    api_base_url = ICA_BASE_URL + "/rest"
    if tenant is not None:
        TENANT_NAME = tenant
        token_endpoint = f"/api/tokens?tenant={TENANT_NAME}"
    else:
        token_endpoint = f"/api/tokens"
    init_headers = dict()
    init_headers['accept'] = 'application/vnd.illumina.v3+json'
    #init_headers['Content-Type'] = 'application/vnd.illumina.v3+json'
    init_headers['Authorization'] = f"Basic {encoded_key}"
    token_url = api_base_url + token_endpoint
    ##############
    #display(token_url)
    #display(init_headers)
    response = await pyfetch(url=token_url,method = 'POST',headers=init_headers)
    curl_command = await curlify(method="POST",endpoint=token_url,header=init_headers)
    analysis_metadata['step1-api'] = curl_command
    status = f"Request status: {response.status}"
    #display(status)
    jwt = await response.json()
    #display(jwt)
    if 'token' not in jwt.keys():
        pprint(jwt,indent = 4)
        raise ValueError(f"Could not get JWT for user: {username}\nPlease double-check username and password.\nYou also may need to enter a domain name")
    return jwt['token']
#########################################
async def list_projects(jwt_token,max_retries=20):
    # List all analyses in a project
    pageOffset = 0
    pageSize = 1000
    page_number = 0
    number_of_rows_to_skip = 0
    api_base_url = ICA_BASE_URL + "/rest"
    endpoint = f"/api/projects?pageOffset={pageOffset}&pageSize={pageSize}&includeHiddenProjects=true"
    projects_metadata = []
    full_url = api_base_url + endpoint  ############ create header
    headers = dict()
    headers['accept'] = 'application/vnd.illumina.v3+json'
    headers['Content-Type'] = 'application/vnd.illumina.v3+json'
    headers['Authorization'] =  'Bearer ' + jwt_token
    try:
        #display(full_url)
        projectPagedList = await pyfetch(full_url,method = 'GET',headers=headers)
        ##########################
        curl_command = await curlify(method="GET",endpoint=full_url,header=headers)
        analysis_metadata['step2-api'] = curl_command
        ################################
        projectPagedListResponse = await projectPagedList.json()
        totalRecords = projectPagedListResponse['totalItemCount']
        response_code = projectPagedList.status
        while page_number * pageSize < totalRecords:
            endpoint = f"/api/projects/?pageOffset={number_of_rows_to_skip}&pageSize={pageSize}&includeHiddenProjects=true"
            full_url = api_base_url + endpoint  ############ create header
            projectPagedList = await pyfetch(full_url,method = 'GET',headers=headers)
            projectPagedListResponse = await projectPagedList.json()
            for project in projectPagedListResponse['items']:
                #display(str(project))
                projects_metadata.append([project['name'], project['id']])
            page_number += 1
            number_of_rows_to_skip = page_number * pageSize
    except:
        raise ValueError(f"Could not get projects")
    return projects_metadata
##########################################
async def get_project_id(jwt_token, project_name):
    projects = []
    pageOffset = 0
    pageSize = 30
    page_number = 0
    number_of_rows_to_skip = 0
    api_base_url = ICA_BASE_URL + "/rest"
    endpoint = f"/api/projects?search={project_name}&includeHiddenProjects=true&pageOffset={pageOffset}&pageSize={pageSize}"
    full_url = api_base_url + endpoint  ############ create header
    headers = dict()
    headers['accept'] = 'application/vnd.illumina.v3+json'
    headers['Content-Type'] = 'application/vnd.illumina.v3+json'
    headers['Authorization'] =  'Bearer ' + jwt_token
    try:
        projectPagedList = await pyfetch(full_url,method = 'GET',headers=headers)
        projectPagedListResponse = await projectPagedList.json()
        totalRecords = projectPagedListResponse['totalItemCount']
        while page_number * pageSize < totalRecords:
            projectPagedList = await pyfetch(full_url,method = 'GET',headers=headers)
            for project in projectPagedListResponse['items']:
                projects.append({"name": project['name'], "id": project['id']})
            page_number += 1
            number_of_rows_to_skip = page_number * pageSize
    except:
        raise ValueError(f"Could not get project_id for project: {project_name}")
    if len(projects) > 1:
        raise ValueError(f"There are multiple projects that match {project_name}")
    else:
        return projects[0]['id']

#########

############
async def list_project_analyses(jwt_token,project_id,max_retries=20):
    # List all analyses in a project
    pageOffset = 0
    pageSize = 1000
    page_number = 0
    number_of_rows_to_skip = 0
    api_base_url = ICA_BASE_URL + "/rest"
    endpoint = f"/api/projects/{project_id}/analyses?pageOffset={pageOffset}&pageSize={pageSize}"
    analyses_metadata = []
    full_url = api_base_url + endpoint  ############ create header
    headers = dict()
    headers['accept'] = 'application/vnd.illumina.v3+json'
    headers['Content-Type'] = 'application/vnd.illumina.v3+json'
    headers['Authorization'] =  'Bearer ' + jwt_token
    analysis_metadata['metadata_by_analysis_id'] = dict()
    analysis_metadata['metadata_by_analysis_name'] = dict()
    try:
        projectAnalysisPagedList = None
        response_code = 404
        num_tries = 0
        while response_code != 200 and num_tries  < max_retries:
            num_tries += 1
            if num_tries > 1:
                print(f"NUM_TRIES:\t{num_tries}\tTrying to get analyses  for project {project_id}")
            projectAnalysisPagedList = await pyfetch(full_url,method = 'GET',headers=headers)
            ##############
            curl_command = await curlify(method="GET",endpoint=full_url,header=headers)
            analysis_metadata['step3-api'] = curl_command
            ###################
            projectAnalysisPagedList_response = await projectAnalysisPagedList.json()
            totalRecords = projectAnalysisPagedList_response['totalItemCount']
            response_code = projectAnalysisPagedList.status
            while page_number * pageSize < totalRecords:
                endpoint = f"/api/projects/{project_id}/analyses?pageOffset={number_of_rows_to_skip}&pageSize={pageSize}"
                full_url = api_base_url + endpoint  ############ create header
                projectAnalysisPagedList = await pyfetch(full_url,method = 'GET',headers=headers)
                projectAnalysisPagedList_response = await projectAnalysisPagedList.json()
                my_count = 0
                for analysis in projectAnalysisPagedList_response['items']:   
                    ### add lookup dict objects for faster querying later .... 
                    analysis_metadata['metadata_by_analysis_id'][analysis['id']]  = analysis  
                    analysis_metadata['metadata_by_analysis_name'][analysis['userReference']]  = analysis   
                    ### store list of analyses metadata
                    analyses_metadata.append(analysis)
                page_number += 1
                number_of_rows_to_skip = page_number * pageSize
    except:
        raise ValueError(f"Could not get analyses for project: {project_id}")
    return analyses_metadata
################
def subset_analysis_metadata_list(analysis_metadata_list):
    subset_metadata = []
    for analysis in analysis_metadata_list:
        my_subset = []
        if 'startDate' in analysis.keys():
            my_subset = [analysis['userReference'],analysis['id'],analysis['startDate'],analysis['status'],analysis['pipeline']['code']]
        else:
            my_subset = [analysis['userReference'],analysis['id'],'1970-01-01T01:00:00Z',analysis['status'],analysis['pipeline']['code']]                            
        subset_metadata.append(my_subset)
    return subset_metadata

##################
async def get_project_analysis_id(jwt_token,project_id,analysis_name):
    desired_analyses_status = ["REQUESTED","INPROGRESS","SUCCEEDED","FAILED"]
    analysis_id  = None
    analyses_list = await list_project_analyses(jwt_token,project_id)
    if analysis_name is not None:
        for aidx,project_analysis in enumerate(analyses_list):
            name_check  = project_analysis['userReference'] == analysis_name 
            status_check = project_analysis['status'] in desired_analyses_status
            # and project_analysis['status'] in desired_analyses_status
            if project_analysis['userReference'] == analysis_name:
                analysis_id = project_analysis['id']
                return analysis_id
    else:
        idx_of_interest = 0
        status_of_interest = analyses_list[idx_of_interest]['status'] 
        current_analysis_id = analyses_list[idx_of_interest]['id'] 
        while status_of_interest not in desired_analyses_status:
            idx_of_interest = idx_of_interest + 1
            status_of_interest = analyses_list[idx_of_interest]['status'] 
            current_analysis_id = analyses_list[idx_of_interest]['id'] 
            print(f"analysis_id:{current_analysis_id} status:{status_of_interest}")
        default_analysis_name = analyses_list[idx_of_interest]['userReference']
        print(f"No user reference provided, will poll the logs for the analysis {default_analysis_name}")
        analysis_id = analyses_list[idx_of_interest]['id']
    return analysis_id

####################

#############################
async def get_pipeline_id(pipeline_code, jwt_token,project_name,project_id=None):
    pipelines = []
    pageOffset = 0
    pageSize = 1000
    page_number = 0
    number_of_rows_to_skip = 0
    # ICA project ID
    if project_id is None:
        project_id = await get_project_id(jwt_token,project_name)
    api_base_url = ICA_BASE_URL + "/rest"
    endpoint = f"/api/projects/{project_id}/pipelines?pageOffset={pageOffset}&pageSize={pageSize}"
    full_url = api_base_url + endpoint	############ create header
    headers = dict()
    headers['accept'] = 'application/vnd.illumina.v3+json'
    headers['Content-Type'] = 'application/vnd.illumina.v3+json'
    headers['Authorization'] =  'Bearer ' + jwt_token
    try:
        #print(f"FULL_URL: {full_url}")
        pipelinesPagedList =  await pyfetch(full_url, method='GET', headers=headers)
        #####
        curl_command = await curlify(method="GET",endpoint=full_url,header=headers)
        analysis_metadata['step4-api'].append("<h3>#Grab pipeline identifier</h3><br>This tells ICA what pipeline to run. Via the CLI you can just provide the [ PIPELINE_NAME ] in single quotes instead of the pipeline id<br>" + curl_command)
        #####     
        pipelinesPagedList_response = await pipelinesPagedList.json()
        if 'totalItemCount' in pipelinesPagedList_response.keys():
            totalRecords = pipelinesPagedList_response['totalItemCount']
            while page_number*pageSize <  totalRecords:
                endpoint = f"/api/projects/{project_id}/pipelines?pageOffset={number_of_rows_to_skip}&pageSize={pageSize}"
                full_url = api_base_url + endpoint  ############ create header
                #print(f"FULL_URL: {full_url}")
                pipelinesPagedList =  await pyfetch(full_url, method='GET', headers=headers)
                pipelinesPagedList_response = await pipelinesPagedList.json()
                for pipeline_idx,pipeline in enumerate(pipelinesPagedList_response['items']):
                    pipelines.append({"code":pipeline['pipeline']['code'],"id":pipeline['pipeline']['id']})
                page_number += 1
                number_of_rows_to_skip = page_number * pageSize
        else:
            for pipeline_idx,pipeline in enumerate(pipelinesPagedList_response['items']):
                pipelines.append({"code": pipeline['pipeline']['code'], "id": pipeline['pipeline']['id']})
    except:
        raise ValueError(f"Could not get pipeline_id for project: {project_name} and name {pipeline_code}\n")
    for pipeline_item, pipeline in enumerate(pipelines):
        # modify this line below to change the matching criteria ... currently the pipeline_code must exactly match
        if pipeline['code'] == pipeline_code:
             pipeline_id = pipeline['id']
    return pipeline_id


#######################


async def get_analysis_storage_id(jwt_token, storage_label=""):
    storage_id = None
    api_base_url = ICA_BASE_URL + "/rest"
    endpoint = f"/api/analysisStorages"
    full_url = api_base_url + endpoint	############ create header
    headers = dict()
    headers['accept'] = 'application/vnd.illumina.v3+json'
    headers['Content-Type'] = 'application/vnd.illumina.v3+json'
    headers['Authorization'] =  'Bearer ' + jwt_token
    try:
        # Retrieve the list of analysis storage options.
        api_response = await pyfetch(full_url, method = 'GET', headers=headers)
        #####
        curl_command = await curlify(method="GET",endpoint=full_url,header=headers)
        analysis_metadata['step4-api'].append("<h3>#Grab analysis storage identifier</h3><br>This sets the size of result data that can be sent back to ICA<br>" + curl_command)
        #####        
        api_responses = await api_response.json()
        #pprint(api_response, indent = 4)
        if storage_label not in ['Large', 'Medium', 'Small','XLarge','2XLarge','3XLarge']:
            print("Not a valid storage_label\n" + "storage_label:" + str(storage_label))
            raise ValueError
        else:
            for analysis_storage_item, analysis_storage in enumerate(api_responses['items']):
                if analysis_storage['name'] == storage_label:
                    storage_id = analysis_storage['id']
                    return storage_id
    except :
        raise ValueError(f"Could not find storage id based on {storage_label}")


#### Conversion functions
async def convert_data_inputs(data_inputs):
    converted_data_inputs = []
    for idx,item in enumerate(data_inputs):
        converted_data_input = {}
        converted_data_input['parameterCode'] = item['parameter_code']
        converted_data_input['dataIds'] = item['data_ids']
        converted_data_inputs.append(converted_data_input)
    return converted_data_inputs

async def get_activation_code(jwt_token,project_id,pipeline_id,data_inputs,input_parameters,workflow_language):
    api_base_url = ICA_BASE_URL + "/rest"
    endpoint = f"/api/activationCodes:findBestMatchingFor{workflow_language}"
    full_url = api_base_url + endpoint
    #print(full_url)
    ############ create header
    headers = dict()
    headers['accept'] = 'application/vnd.illumina.v3+json'
    headers['Content-Type'] = 'application/vnd.illumina.v3+json'
    headers['Authorization'] =  'Bearer ' + jwt_token
    ######## create body
    collected_parameters = {}
    collected_parameters["pipelineId"] = pipeline_id
    collected_parameters["projectId"] = project_id
    collected_parameters["analysisInput"] = {}
    collected_parameters["analysisInput"]["objectType"] = "STRUCTURED"
    collected_parameters["analysisInput"]["inputs"] = await convert_data_inputs(data_inputs)
    collected_parameters["analysisInput"]["parameters"] = input_parameters
    collected_parameters["analysisInput"]["referenceDataParameters"] = []
    #display(full_url)
    #display(collected_parameters)
    response = await pyfetch(full_url, method = 'POST', headers = headers, body = json.dumps(collected_parameters))
    #####
    curl_command = await curlify(method="POST",endpoint=full_url,header=headers, body = collected_parameters)
    analysis_metadata['step4-api'].append("<h3>#Grab activation code</h3><br>" + curl_command)
    #####
    #response = await pyfetch(full_url, method = 'POST', headers = headers, data = json.dumps(collected_parameters))
    #pprint(response.json())
    entitlement_details = await response.json()
    #display(entitlement_details)
    return entitlement_details['id']
###############################################
async def launch_pipeline_analysis_cwl(jwt_token,project_id,pipeline_id,data_inputs,input_parameters,user_tags,storage_analysis_id,user_pipeline_reference,workflow_language,make_template=False):
    api_base_url = ICA_BASE_URL + "/rest"
    endpoint = f"/api/projects/{project_id}/analysis:{workflow_language}"
    full_url = api_base_url + endpoint
    if workflow_language == "cwl":
        activation_details_code_id = await get_activation_code(jwt_token,project_id,pipeline_id,data_inputs,input_parameters,"Cwl")
    elif workflow_language == "nextflow":
        activation_details_code_id = await get_activation_code(jwt_token,project_id,pipeline_id,data_inputs,input_parameters,"Nextflow")
    #print(full_url)
    ############ create header
    headers = dict()
    headers['accept'] = 'application/vnd.illumina.v3+json'
    headers['Content-Type'] = 'application/vnd.illumina.v3+json'
    headers['Authorization'] =  'Bearer ' + jwt_token
    ######## create body
    collected_parameters = {}
    collected_parameters['userReference'] = user_pipeline_reference
    collected_parameters['activationCodeDetailId'] = activation_details_code_id
    collected_parameters['analysisStorageId'] = storage_analysis_id
    collected_parameters["tags"] = {}
    collected_parameters["tags"]["technicalTags"] = []
    collected_parameters["tags"]["userTags"] = user_tags
    collected_parameters["tags"]["referenceTags"] = []
    collected_parameters["pipelineId"] = pipeline_id
    collected_parameters["projectId"] = project_id
    collected_parameters["analysisInput"] = {}
    collected_parameters["analysisInput"]["objectType"] = "STRUCTURED"
    collected_parameters["analysisInput"]["inputs"] = await convert_data_inputs(data_inputs)
    collected_parameters["analysisInput"]["parameters"] = input_parameters
    collected_parameters["analysisInput"]["referenceDataParameters"] = []
    # Writing to job template to f"{user_pipeline_reference}.job_template.json"
    if make_template is True:
        user_pipeline_reference_alias = user_pipeline_reference.replace(" ","_")
        api_template = {}
        api_template['headers'] = dict(headers)
        api_template['data'] = collected_parameters
        #print(f"Writing your API job template out to {user_pipeline_reference_alias}.api_job_template.txt for future use.\n")
        curl_command = await curlify(method="POST",endpoint=full_url,header=api_template['headers'],body=api_template['data'])
        with open(f"{user_pipeline_reference_alias}.api_job_template.txt", "w") as outfile:
            outfile.write(f"{curl_command}")
        return(f"{user_pipeline_reference_alias}.api_job_template.txt")
    else:
        ##########################################
        response = await pyfetch(full_url, method = 'POST', headers = headers, data = json.dumps(collected_parameters))
        launch_details = await response.json()
        pprint(launch_details, indent=4)
        return launch_details


############
####
def flatten_list(nested_list):
    def flatten(lst):
        for item in lst:
            if isinstance(item, list):
                flatten(item)
            else:
                flat_list.append(item)

    flat_list = []
    flatten(nested_list)
    return flat_list

def prettify_cli_template(cli_args):
    idxs_of_interest = []
    deconstructed_template = []
    final_template_str = None
    ## pull out tokens of interest
    for idx,val in enumerate(cli_args):
        if re.search("^--",val) is not None:
            idxs_of_interest.append(idx-1)
    if len(idxs_of_interest) > 0:
        for idx,val in enumerate(cli_args):
            if idx not in idxs_of_interest:
                deconstructed_template.append(val)
            else:
                new_str = f"{val} \\\n"
                deconstructed_template.append(new_str)
        final_template_str = " ".join(deconstructed_template)
    ### go and add \\\n to tokens of interest
    return final_template_str

def get_pipeline_request_template(jwt_token, project_id, pipeline_name, data_inputs, params,tags, storage_size, pipeline_run_name,workflow_language):
    user_pipeline_reference_alias = pipeline_run_name.replace(" ","_")
    pipeline_run_name = user_pipeline_reference_alias
    cli_template_prefix = ["icav2","projectpipelines","start",f"{workflow_language}",f"'{pipeline_name}'","--user-reference",f"{pipeline_run_name}"]
    #### user tags for input
    cli_tags_template = []
    for k,v in enumerate(tags):
        cli_tags_template.append(["--user-tag",v])
    ### data inputs for the CLI command
    cli_inputs_template =[]
    for k in range(0,len(data_inputs)):
        # deal with data inputs with a single value
        if len(data_inputs[k]['data_ids']) < 2 and len(data_inputs[k]['data_ids']) > 0:
            cli_inputs_template.append(["--input",f"{data_inputs[k]['parameter_code']}:{data_inputs[k]['data_ids'][0]}"])
         # deal with data inputs with multiple values
        else:
            v_string = ','.join(data_inputs[k]['data_ids'])
            cli_inputs_template.append(["--input",f"{data_inputs[k]['parameter_code']}:{v_string}"])
    ### parameters for the CLI command        
    cli_parameters_template = []
    for k in range(0,len(params)):
        parameter_of_interest = 'value'
        if 'value' not in params[k].keys():
            parameter_of_interest = 'multiValue'
        # deal with parameters with a single value
        if isinstance(params[k][parameter_of_interest],list) is False:
            if params[k][parameter_of_interest] != "":
                cli_parameters_template.append(["--parameters",f"{params[k]['code']}:'{params[k][parameter_of_interest]}'"])
        else:
        # deal with parameters with multiple values
            if len(params[k][parameter_of_interest])  > 0:
                # remove single-quotes 
                simplified_string = [x.strip('\'') for x in params[k][parameter_of_interest]]
                # stylize multi-value parameters
                v_string = ','.join([f"'{x}'" for x in simplified_string])
                if len(simplified_string) > 1:
                    cli_parameters_template.append(["--parameters",f"{params[k]['code']}:\"{v_string}\""])
                elif len(simplified_string) > 0 and simplified_string[0] != '':
                    cli_parameters_template.append(["--parameters",f"{params[k]['code']}:{v_string}"])
    cli_metadata_template = ["--access-token",f"'{jwt_token}'","--project-id",f"{project_id}","--storage-size",f"{storage_size}"]
    if workflow_language == "cwl":
        cli_metadata_template.append("--type-input STRUCTURED")
    full_cli = [cli_template_prefix,cli_tags_template,cli_inputs_template,cli_parameters_template,cli_metadata_template]
    cli_template = ' '.join(flatten_list(full_cli))

    ## add newlines and create 'pretty' template
    new_cli_template = prettify_cli_template(flatten_list(full_cli))
    if new_cli_template is not None:
        cli_template = new_cli_template
    
    ######
    pipeline_run_name_alias = pipeline_run_name.replace(" ","_")
    #print(f"Writing your cli job template out to {pipeline_run_name_alias}.cli_job_template.txt for future use.\n")
    with open(f"{pipeline_run_name_alias}.cli_job_template.txt", "w") as outfile:
        outfile.write(f"{cli_template}")
    #print("Also printing out the CLI template to screen\n")
    return  f"{pipeline_run_name_alias}.cli_job_template.txt"
###################################################

def create_analysis_parameter_input_object_extended(parameter_template, params_to_keep):
    parameters = []
    for parameter_item, parameter in enumerate(parameter_template):
        param = {}
        param['code'] = parameter['name']
        if len(params_to_keep) > 0:
            if param['code'] in params_to_keep:
                if parameter['multiValue'] is False:
                    if len(parameter['values']) > 0:
                        param['value'] = parameter['values'][0]
                    else:
                        param['value'] = ""
                else:
                    param['multiValue'] = parameter['values']
            else:
                param['value']  = ""
        else:
            if parameter['multiValue'] is False:
                if len(parameter['values']) > 0:
                    param['value'] = parameter['values'][0]
                else:
                    param['value'] = ""
            else:
                param['multiValue'] = parameter['values']           
        parameters.append(param)
    return parameters

def parse_analysis_data_input_example(input_example, inputs_to_keep):
    input_data = []
    for input_item, input_obj in enumerate(input_example):
        input_metadata = {}
        input_metadata['parameter_code'] = input_obj['code']
        data_ids = []
        if len(inputs_to_keep) > 0:
            if input_obj['code'] in inputs_to_keep:
                for inputs_idx, inputs in enumerate(input_obj['analysisData']):
                    data_ids.append(inputs['dataId'])
        else:
            for inputs_idx, inputs in enumerate(input_obj['analysisData']):
                data_ids.append(inputs['dataId'])
        input_metadata['data_ids'] = data_ids
        input_data.append(input_metadata)
    return input_data

async def get_cwl_input_template(pipeline_code, jwt_token,project_name, fixed_input_data_fields,params_to_keep=[] , analysis_id=None,project_id=None):
    if project_id is None:
        project_id = await get_project_id(jwt_token, project_name)
    headers = dict()
    headers['Accept'] = 'application/vnd.illumina.v3+json'
    headers['Content-Type'] = 'application/vnd.illumina.v3+json'
    headers['Authorization'] =  'Bearer ' + jwt_token
    # users can define an analysis_id of interest
    if analysis_id is None:
        project_analyses = await list_project_analyses(jwt_token,project_id)
        # find most recent analysis_id for the pipeline_code that succeeeded
        for analysis_idx,analysis in enumerate(project_analyses):
            if analysis['pipeline']['code'] == pipeline_code and analysis['status'] == "SUCCEEDED":
                analysis_id = analysis['id']
                continue
    templates = {}  # a dict that returns the templates we'll use to launch an analysis
    api_base_url = ICA_BASE_URL + "/rest"
    # grab the input files for the given analysis_id
    input_endpoint = f"/api/projects/{project_id}/analyses/{analysis_id}/inputs"
    full_input_endpoint = api_base_url + input_endpoint
    #display(f"ANALYSIS_INPUTS_URL: {full_input_endpoint}")
    try:
        inputs_response = await pyfetch(full_input_endpoint, method='GET', headers=headers)
        #####
        curl_command = await curlify(method="GET",endpoint=full_input_endpoint,header=headers)
        analysis_metadata['step4-api'].append("<h3>#Grab dataInputs JSON from previous analysis</h3><br>" + curl_command)
        #####
        inputs_responses = await inputs_response.json()
        #display(inputs_responses)
        input_data_example = inputs_responses['items']
    except:
        raise ValueError(f"Could not get inputs for the project analysis {analysis_id}")
    # grab the parameters set for the given analysis_id
    parameters_endpoint = f"/api/projects/{project_id}/analyses/{analysis_id}/configurations"
    full_parameters_endpoint = api_base_url + parameters_endpoint
    #display(f"ANALYSIS_PARAMETERS_URL: {full_parameters_endpoint}")
    try:
        parameter_response = await pyfetch(full_parameters_endpoint, method = 'GET', headers=headers)
        #####
        curl_command = await curlify(method="GET",endpoint=full_parameters_endpoint,header=headers)
        analysis_metadata['step4-api'].append("<h3>#Grab parameters JSON from previous analysis</h3><br>" + curl_command)
        #####
        parameter_responses = await parameter_response.json()
        parameter_settings = parameter_responses['items']
    except:
        raise ValueError(f"Could not get parameters for the project analysis {analysis_id}")
    # return both the input data template and parameter settings for this pipeline
    input_data_template = parse_analysis_data_input_example(input_data_example, fixed_input_data_fields)
    parameter_settings_template = create_analysis_parameter_input_object_extended(parameter_settings,params_to_keep)
    templates['input_data'] = input_data_template
    templates['parameter_settings'] = parameter_settings_template
    return templates
#####################
##########################################
#### STEP 1 in HTML
async def load_login_info(event):
    display("STEP1: Authorizing login credentials",target="step1-output",append="False")
    USERNAME = document.getElementById('txt-uname').value
    #display('MY_USERNAME: ' + USERNAME)
    PASSWORD = document.getElementById('txt-pwd').value
    #display('MY_PASSWORD: ' + PASSWORD)
    PROJECT_NAME = None
    #display('MY_PROJECT_NAME: ' + PROJECT_NAME)
    DOMAIN_NAME = document.getElementById('txt-domain-name').value
    if DOMAIN_NAME == '':
        DOMAIN_NAME = None
    #display('MY_DOMAIN_NAME: ' + DOMAIN_NAME)
    ### get JWT token
    jwt_token = None
    try:
        jwt_token = await get_jwt(USERNAME,PASSWORD,tenant = DOMAIN_NAME)
    except:
        console.error('Please retry login.\nYou May need to refresh your webpage')
        alert('Please retry login.\nYou May need to refresh your webpage')
        raise ValueError(f"Could not get JWT for user: {USERNAME}\nPlease double-check username and password.\nYou also may need to enter a domain name\n")
    authorization_metadata['jwt_token'] = jwt_token 
    #### Step 2 get project ID
    PROJECT_ID = None
    #### select project if needed
    if PROJECT_NAME is None:
        project_table = await list_projects(jwt_token)
        df = pd.DataFrame(project_table, columns = ['ICA Project Name', 'ICA Project ID']) 

        pydom["div#project-output"].style["display"] = "block"

        ### show field and submit button for STEP2:
        pydom["div#step2-selection-form"].style["display"] = "block"

        #pydom["div#roject-output-inner"].innerHTML = df_window(df)
        #document.getElementById('project-output-inner').innerHTML = df.to_html()
        if document.getElementById('project-output-inner').innerHTML  == "":
            document.getElementById('project-output-inner').innerHTML = df_html(df)
    
            new_script = document.createElement('script')
            new_script.innerHTML  = """$(document).ready(function(){$('#project-output-inner').DataTable({
                "pageLength": 10
            });});"""
            document.getElementById('project-output').appendChild(new_script)
        else:
            document.getElementById('project-output-inner').innerHTML = df_html(df)

        #display(df.to_html(), target="project-output-inner", append="False")
        #display(df_window(df), target="project-output-inner", append="False")
    return display("You are logged in",target="step1-output",append="True")
#######
#### STEP 2 in HTML
async def load_project_selection_info(event):
    display("STEP2 starting",target ="step2-selection",append="False")
    # Create a Python proxy for the callback function
    PROJECT_NAME =  document.getElementById("txt-project-name").value 
    console.log(f"{PROJECT_NAME}")
    pydom["div#step2-selection"].html = PROJECT_NAME
    display(f'Selected project name is: {PROJECT_NAME}',target ="step2-selection",append="True")
    try:
        PROJECT_ID = await get_project_id(authorization_metadata['jwt_token'], PROJECT_NAME)
        display(f'project id is : {PROJECT_ID}',target ="step2-selection",append="True")
        analysis_metadata['project_name'] = PROJECT_NAME
        analysis_metadata['project_id'] = PROJECT_ID
    except:
        console.error('Please retry entering a project name')
        alert('Please retry entering a project name.')
        raise ValueError(f"Could not get project id for project: {PROJECT_NAME}\nPlease double-check project name exists.")    
    display(f"Fetching all analyses from {PROJECT_NAME}",target ="step2-selection",append="True")    
    analyses_list = await list_project_analyses(authorization_metadata['jwt_token'],analysis_metadata['project_id'])
    display(f"Fetching Completed\nCreating Table\n",target ="step2-selection",append="True")    
    analyses_table = subset_analysis_metadata_list(analyses_list)
    df = pd.DataFrame(analyses_table, columns = ['Analysis Name', 'Analysis ID','Analysis Start Date','Analysis Status','Pipeline']) 
    df['Analysis Start Date'] = pd.to_datetime(df['Analysis Start Date'], format='%Y-%m-%dT%H:%M:%SZ')

    #df.sort_values(by='Analysis Start Date',ascending=False,inplace = True)
    ### using slicing to invert dataframe to give ICA default sorting
    #df = df[::-1]
    pydom["div#analyses-output"].style["display"] = "block"
    #display(df, target="project-output-inner", append="False")
    if document.getElementById('analyses-output-inner').innerHTML == "":
        document.getElementById('analyses-output-inner').innerHTML = df_html(df)
    
        new_script = document.createElement('script')
        new_script.innerHTML  = """$(document).ready(function(){$('#analyses-output-inner').DataTable({
                "pageLength": 10
            });});"""
        document.getElementById('analyses-output').appendChild(new_script)
    else:
        document.getElementById('analyses-output-inner').innerHTML = df_html(df)
 
    ### show field and submit button for STEP3:
    pydom["div#step3-selection-form"].style["display"] = "block"

    return display("STEP2 complete",target ="step2-selection",append="True")
##################    
#### STEP 3 in HTML
async def load_analysis_selection_info(event):
    display("STEP3 starting",target ="step3-selection",append="False")
    ANALYSIS_NAME = document.getElementById("txt-analysis-name").value 
    analysis_metadata['analysis_name'] = ANALYSIS_NAME
    pydom["div#step3-selection"].html = ANALYSIS_NAME
    display(f'Selected analysis name is: {ANALYSIS_NAME}',target ="step3-selection",append="True")
    try:
        if ANALYSIS_NAME in analysis_metadata['metadata_by_analysis_id'].keys():
            analysis_metadata['analysis_id'] = ANALYSIS_NAME
            display(f'analysis id is : {ANALYSIS_NAME}',target ="step3-selection",append="True")
            #ANALYSIS_ID_LOOKUP = analysis_metadata['metadata_by_analysis_name'][ANALYSIS_NAME]
            #ANALYSIS_NAME = ANALYSIS_ID_LOOKUP['userReference']
            #analysis_metadata['analysis_name'] = ANALYSIS_NAME
            pydom["div#step4-selection-form"].style["display"] = "block"
        elif ANALYSIS_NAME in analysis_metadata['metadata_by_analysis_name'].keys():
            #ANALYSIS_ID = await get_project_analysis_id(authorization_metadata['jwt_token'],analysis_metadata['project_id'],analysis_metadata['analysis_name'])
            ANALYSIS_ID_LOOKUP = analysis_metadata['metadata_by_analysis_name'][ANALYSIS_NAME]
            ANALYSIS_ID = ANALYSIS_ID_LOOKUP['id']
            display(f'analysis id is : {ANALYSIS_ID}',target ="step3-selection",append="True")
            analysis_metadata['analysis_id'] = ANALYSIS_ID
            pydom["div#step4-selection-form"].style["display"] = "block"
        else:
            console.error('Please retry entering an analysis name')
            alert('Please retry entering an analysis name.')
            raise ValueError(f"Could not get analysis id for analysis: {ANALYSIS_NAME}\nPlease double-check analysis name exists.") 
    except:
        if ANALYSIS_NAME in analysis_metadata['metadata_by_analysis_id'].keys():
            analysis_metadata['analysis_id'] = ANALYSIS_NAME
            display(f'analysis id is : {ANALYSIS_NAME}',target ="step3-selection",append="True")
            pydom["div#step4-selection-form"].style["display"] = "block"
        else:
            console.error('Please retry entering an analysis name')
            alert('Please retry entering an analysis name.')
            raise ValueError(f"Could not get analysis id for analysis: {ANALYSIS_NAME}\nPlease double-check analysis name exists.") 
    return display("STEP3 complete",target ="step3-selection",append="True")
#####################
# create download button and serve templates as text files
from js import Uint8Array, File, URL, document
import io
from pyodide.ffi.wrappers import add_event_listener

def create_download_button(file_of_interest=None):
    if file_of_interest is not None:
        f1 = open(file_of_interest,"rb")
        data = f1.read()
        f1.close() 
        
        encoded_data = data
        my_stream = io.BytesIO(data)
    
        js_array = Uint8Array.new(len(encoded_data))
        js_array.assign(my_stream.getbuffer())
    
        file = File.new([js_array], file_of_interest, {type: "text/plain"})
        url = URL.createObjectURL(file)
        # hide download button if it exists
        #if document.getElementById("requeue-template-download") is not None:
        pydom["div#requeue-template-download"].style["display"] = "none"

        #downloadDoc = document.createElement('a')
        downloadDoc = document.getElementById('requeue-template-download-child')
        downloadDoc.href = window.URL.createObjectURL(file)

        ############## hard-coded in html to avoid creating mutliple buttons
        #downloadButton = document.createElement('button')
        #downloadButton.innerHTML = "Download Requeue Template"
        #downloadDoc.appendChild(downloadButton)
        ##############
        
        document.getElementById("requeue-template-download").appendChild(downloadDoc)
        downloadDoc.setAttribute("download", file_of_interest)
        pydom["div#requeue-template-download"].style["display"] = "block"
    else:
        print("Nothing to do")
    return 0 
#### STEP 4 in HTML
async def generate_requeue_template(event):
    display("STEP4 starting",target="requeue-template-logging",append="False")
    TEMPLATE_TYPE = document.getElementById("template-type-selection").value 
    if TEMPLATE_TYPE.lower() == "cli":
        display('Collecting info to generate CLI template',target="requeue-template-logging",append="True")
    elif TEMPLATE_TYPE.lower() == "api":
        display('Collecting info to generate API template',target="requeue-template-logging",append="True")
    else:
        console.error('Please retry entering a requeue template type [API or CLI]')
        alert('Please retry entering a requeue template type [API or CLI]')
        raise ValueError(f"Please retry entering a requeue template type [API or CLI]. You entered the following as a requeue template type [ {TEMPLATE_TYPE} ]") 
   ###########################
    display('Grabbing more info about the previously run analysis',target="requeue-template-logging",append="True")
    analyses_list =[ analysis_metadata['metadata_by_analysis_id'][analysis_metadata['analysis_id']] ]
    #analyses_list = await list_project_analyses(authorization_metadata['jwt_token'],analysis_metadata['project_id'])
    for aidx,project_analysis in enumerate(analyses_list):
        if project_analysis['userReference'] == analysis_metadata['analysis_name'] or project_analysis['id'] == analysis_metadata['analysis_name']:
            analysis_id = project_analysis['id']
            display(f"Found Analysis with name {analysis_metadata['analysis_name']} with id : {analysis_id}\n",target="requeue-template-logging",append="True")
            pipeline_id = project_analysis['pipeline']['id']
            pipeline_name = project_analysis['pipeline']['code']
            workflow_language = project_analysis['pipeline']['language'].lower()
            if 'analysisStorage' in project_analysis.keys():
                storage_size = project_analysis['analysisStorage']['name']
            else:
                storage_size = 'Large'
    ##### crafting job template
    input_data_fields_to_keep  = []
    param_fields_to_keep = []
    display('Getting data input and paramters from analysis',target="requeue-template-logging",append="True")
    job_templates = await get_cwl_input_template(pipeline_name, authorization_metadata['jwt_token'],analysis_metadata['project_name'],input_data_fields_to_keep, param_fields_to_keep,analysis_id = analysis_id,project_id=analysis_metadata['project_id'])
    ########################################
    #### now let's set up pipeline analysis by updating the template
    dateTimeObj = dt.now()
    timestampStr = dateTimeObj.strftime("%Y%b%d_%H_%M_%S_%f")
    pipeline_run_name = analysis_metadata['analysis_name'] + "_requeue_" + timestampStr 
    pipeline_run_name = pipeline_run_name.replace(" ","_")
    #print(f"Setting up pipeline analysis for {pipeline_run_name}")
    my_params = job_templates['parameter_settings']
    #display(my_params)
    my_data_inputs = job_templates['input_data']
    #display(my_data_inputs)
    pipeline_id = await get_pipeline_id(pipeline_name, authorization_metadata['jwt_token'],analysis_metadata['project_name'],project_id = analysis_metadata['project_id'])
    my_tags = [pipeline_run_name]
    my_storage_analysis_id = await get_analysis_storage_id(authorization_metadata['jwt_token'], storage_size)
    ### add sleep to avoid pipeline getting stuck in AWAITINGINPUT state? 
    #print (f"my workflow_language {workflow_language}")
    #print(f"{time_now} Launching pipeline analysis for {pipeline_run_name}")
    if TEMPLATE_TYPE.lower() == "cli":
        display('Generating CLI template',target="requeue-template-logging",append="True")
        cli_template = get_pipeline_request_template(authorization_metadata['jwt_token'], analysis_metadata['project_id'], pipeline_name, my_data_inputs, my_params,my_tags, storage_size, pipeline_run_name,workflow_language)
        #create_download_button(cli_template)
        pydom["script#my_template"].style["display"] = "block"
        document.getElementById('my_template').innerHTML = cli_template
        create_download_button(file_of_interest=cli_template)
        display(f"Download button will download file locally, named: {cli_template}",target="requeue-template-logging",append="True")

        #create_download_button(cli_template)
        #display(cli_template,target="my_template",append="False")
    elif TEMPLATE_TYPE.lower() == "api":
        ####################################
        display('Generating API template',target="requeue-template-logging",append="True")
        test_launch = await launch_pipeline_analysis_cwl(authorization_metadata['jwt_token'], analysis_metadata['project_id'], pipeline_id, my_data_inputs, my_params,my_tags, my_storage_analysis_id, pipeline_run_name,workflow_language,make_template = True)
        #create_download_button(test_launch)
        pydom["script#my_template"].style["display"] = "block"
        #display(test_launch,target="my_template",append="False")
        document.getElementById('my_template').innerHTML = test_launch
        create_download_button(file_of_interest=test_launch)
        display(f"Download button will download file locally, named: {test_launch}",target="requeue-template-logging",append="True")
        #create_download_button(test_launch)
        #display(test_launch,target="my_template",append="False")
    else:
        console.error('Please retry entering a requeue template type [API or CLI]')
        alert('Please retry entering a requeue template type [API or CLI]')
        raise ValueError(f"Please retry entering a requeue template type [API or CLI]. You entered the following as a requeue template type [ {TEMPLATE_TYPE} ]") 
    # show learn more section    
    pydom["section#learn-the-steps"].style["display"] = "block"
    return display("STEP4 complete",target="requeue-template-logging",append="True")
#########################  
### adding brief text and full fledged API/CLI steps to generate template based on user input
async def learn_api_cli(event):
    # STEP1
    new_element = document.getElementById('step1-cli-content')
    new_element.innerHTML =  "icav2 tokens create"
    #document.getElementById('step1-cli').appendChild(new_element)
    new_element = document.getElementById('step1-api-content')
    new_element.innerHTML = analysis_metadata['step1-api']
    #document.getElementById('step1-api').appendChild(new_element)
    # STEP2
    new_element = document.getElementById('step2-cli-content')
    new_element.innerHTML = f"icav2 projects list --access-token '{authorization_metadata['jwt_token']}'"
    #document.getElementById('step2-cli').appendChild(new_element) 
    new_element = document.getElementById('step2-api-content')
    new_element.innerHTML = analysis_metadata['step2-api']
    #document.getElementById('step2-api').appendChild(new_element)
    # STEP3
    new_element = document.getElementById('step3-cli-content')
    #new_element.innerHTML = "hello"
    new_element.innerHTML = f"icav2 projectanalyses list --project-id {analysis_metadata['project_id']}  --access-token '{authorization_metadata['jwt_token']}'"
    #document.getElementById('step3-cli').appendChild(new_element)
    new_element = document.getElementById('step3-api-content')
    new_element.innerHTML = analysis_metadata['step3-api']
    #document.getElementById('step3-api').appendChild(new_element)
    # STEP4
    new_element = document.getElementById('step4-cli-content')
    new_element.innerHTML = f"#Grab dataInputs<br><br>icav2 projectanalyses input {analysis_metadata['analysis_id']} --project-id {analysis_metadata['project_id']}  --access-token '{authorization_metadata['jwt_token']}'<br><br>Currently you cannot grab parameter configurations from previous analyses via the CLI<br>You can grab all possible parameter configurations via the API. Click API tab for more info<br>"
    #document.getElementById('step4-cli').appendChild(new_element)
    new_element = document.getElementById('step4-api-content')
    full_steps = '<br>'.join(analysis_metadata['step4-api'])
    #display(full_steps)
    new_element.innerHTML = full_steps
    #document.getElementById('step4-api').appendChild(new_element)
    ### render the howto section
    pydom["section#learn-the-steps"].style["display"] = "block"
    return 0