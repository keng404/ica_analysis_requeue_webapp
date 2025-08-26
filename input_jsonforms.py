import json
import re
import os
import pprint
from pprint import pprint
import asyncio
from pyodide.http import pyfetch
##import requests
##from requests.structures import CaseInsensitiveDict
###############
ICA_BASE_URL = 'https://ica.illumina.com/ica'
analysis_metadata = dict()
analysis_metadata['step4-api'] = []
###############
def string_to_boolean(s):
    if s.lower() == 'true':
        return True
    elif s.lower() == 'false':
        return False
    else:
        return s

def choices_conversion(choices,val):
    choices_dict = dict()
    for idx,choice in enumerate(choices):
        choices_dict[choice['value']] = choice['text']
    if val in list(choices_dict.keys()):
        return choices_dict[val]
    else:
        return val



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
    ##print(f"{curlified_command}")
    return curlified_command

async def get_inputform_values(jwt_token,project_id,analysis_id):
    api_base_url = ICA_BASE_URL + "/rest"
    endpoint = f"/api/projects/{project_id}/analyses/{analysis_id}/inputFormValues"
    full_url = api_base_url + endpoint
    headers = dict()
    headers['accept'] = 'application/vnd.illumina.v4+json'
    #headers['Content-Type'] = 'application/vnd.illumina.v4+json'
    #headers['X-API-Key'] = api_key
    headers['Authorization'] =  'Bearer ' + jwt_token
    #print(f"get_inputform_values_URL: {full_url}")
    try:
        #esponse = requests.get(full_url, headers=headers)
        response = await pyfetch(full_url,method = 'GET',headers=headers)
        input_form_values = await response.json()
        input_form_values = input_form_values['items']
        ###########
        curl_command = await curlify(method="GET",endpoint=full_url,header=headers)
        analysis_metadata['step4-api'].append("<h3>#Grab parameters JSON from previous analysis</h3><br>" + curl_command)
        #############3
        #input_form_values = json.dumps(input_form_values)
        ##print("Found input form values")
        ##pprint(input_form_values,indent=4)
    except:
        pprint(response,indent=4)
        input_form_values = None
    return input_form_values
##

### add to main script
async def submit_jsoninputform(jwt_token,project_id,pipeline_id,api_dict,user_tags,storage_analysis_id,user_pipeline_reference,workflow_language,make_template=False):
    api_base_url = ICA_BASE_URL + "/rest"
    endpoint = f"/api/projects/{project_id}/analysis:{workflow_language}Json"
    full_url = api_base_url + endpoint
    headers = dict()
    headers['accept'] = 'application/vnd.illumina.v4+json'
    ##headers['Content-Type'] = 'application/vnd.illumina.v4+json'
    ##headers['X-API-Key'] = api_key
    headers['Authorization'] =  'Bearer ' + jwt_token
    ######## create body
    collected_parameters = {}
    collected_parameters['userReference'] = user_pipeline_reference
    collected_parameters['analysisStorageId'] = storage_analysis_id
    collected_parameters["tags"] = {}
    collected_parameters["tags"]["technicalTags"] = []
    collected_parameters["tags"]["userTags"] = user_tags
    collected_parameters["tags"]["referenceTags"] = []
    collected_parameters["pipelineId"] = pipeline_id
    collected_parameters["projectId"] = project_id
    collected_parameters['inputFormValues'] = api_dict
    if make_template is True:
        user_pipeline_reference_alias = user_pipeline_reference.replace(" ","_")
        api_template = {}
        api_template['headers'] = dict(headers)
        api_template['data'] = collected_parameters
        curl_command = await curlify(method="POST",endpoint=full_url,header=api_template['headers'],body=api_template['data'])
        ##print(f"Writing out template to {user_pipeline_reference_alias}.api_job_template.txt")
        ##print("Please feel free to edit before submitting")
        with open(f"{user_pipeline_reference_alias}.api_job_template.txt", "w") as outfile:
            outfile.write(f"{curl_command}")
        ##print("Also printing out the API template to screen\n")
        #print(f"{curl_command}")
        return(f"{user_pipeline_reference_alias}.api_job_template.txt")
        
        ##########################################
    else:
        #response = requests.post(full_url, headers = headers, data = json.dumps(collected_parameters))
        response = await pyfetch(url=full_url,method = 'POST',headers=headers,data = json.dumps(collected_parameters))
        launch_details = await response.json()
        pprint(launch_details, indent=4)
    return launch_details

def collect_clidict_jsoninputform(json_response):
    cli_dict = dict()
    cli_dict['field'] = dict() #### strings and booleans to a specific field
    cli_dict['field-data'] = dict()  #### data associated to a specific field
    cli_dict['group'] = dict() #### strings and booleans to groups of field(s) they can be applied broadly to all samples
    cli_dict['group-data'] = dict() #### data associated to groups of field(s) they can be applied broadly to all samples
    for idx,fields in enumerate(json_response):
        ### skip elements that are SECTION type
        if fields['type'].upper() == "SECTION":
            print(f"Skipping {fields['id']}")
        ##### if element is a datatype
        elif fields['type'].upper() == "DATA":
            if fields['hidden'] is not True:
                if 'dataValues' in list(fields.keys()):
                    cli_dict['field-data'][fields['id']] =[ x['dataId'] for x in fields['dataValues'] ]
        elif fields['type'].upper() == "FIELDGROUP":
            group_name = fields['id']
            ### groupValues
            if 'groupValues' in fields.keys() and fields['hidden'] is not True and fields['disabled'] is not True:
                group_values = fields['groupValues']
                for idx,param_g in enumerate(group_values):
                    #index_num = f"index{idx+1}"
                    index_num = f"{idx+1}"
                    for idx1,param in enumerate(param_g['values']):
                        field_name = param['id']
                        name_components = [group_name,index_num,field_name]
                        name_str = ".".join(name_components)
                        if len(param['values']) > 0:
                            data_values = []
                            field_values = []
                            for p in param['values']:
                                my_bool = re.search("^fol.",p) is not None or re.search("^fil.",p) is not None
                                if re.search("^fol.",p) is not None or re.search("^fil.",p) is not None:
                                    data_values.append(p)
                                elif re.search("^fol.",p) is None and re.search("^fil.",p) is None:
                                    field_values.append(p)
                            if len(data_values) > 0:
                                cli_dict['group-data'][name_str] = data_values
                            if len(field_values) > 0:
                                cli_dict['group'][name_str] = field_values
            ### fields
            if 'fields' in fields.keys():
                group_fields = fields['fields']
                for idx,param in enumerate(group_fields):
                    index_num = f"index{idx+1}"
                    if param['hidden'] is not True and param['disabled'] is not True and 'values' in param.keys():
                        field_name = param['id']
                        name_components = [group_name,index_num,field_name]
                        name_str = ".".join(name_components)
                        new_values = None
                        ### checkbox is of boolean type
                        if param['type'].upper() in ["CHECKBOX"]:
                            new_values = [ string_to_boolean(x) for x in param['values'] ]
                        if param['type'].upper() in ["INTEGER"]:
                            new_values = [ int(x) for x in param['values'] ]
                        if new_values is not None:
                            param['values'] = new_values
                        if len(param['values']) > 0:
                            cli_dict['group'][name_str] = param['values']
                    elif param['hidden'] is not True and param['disabled'] is not True and 'dataValues' in param.keys():
                        field_name = param['id']
                        name_components = [group_name,index_num,field_name]
                        name_str = ".".join(name_components)
                        if len(param['dataValuues']) > 0:
                            cli_dict['group-data'][name_str] = param['dataValues']

        else:
        ### otherwise grab values
            if fields['hidden'] is not True and fields['disabled'] is not True:
                if 'values' in list(fields.keys()):
                    new_values = None
                    ### checkbox is of boolean type
                    if fields['type'].upper() in ["CHECKBOX"]:
                        new_values = [ string_to_boolean(x) for x in fields['values'] ]
                    if fields['type'].upper() in ["INTEGER"]:
                        new_values = [ int(x) for x in fields['values'] ]
                    if new_values is not None:
                        fields['values'] = new_values
                    if len(fields['values']) > 0:
                        cli_dict['field'][fields['id']] = fields['values']
    return cli_dict
####x = collect_clidict_jsoninputform(d['items'])
#$pprint(x)
def handle_cli_bool(val):
    if val is True:
        return "true"
    elif val is False:
        return "false"
    else:
        return val

def clidict_to_commandline(cli_dict):
    cli_line = []
    cli_flags = ["field-data","field","group-data","group"]
    for flag in cli_flags:
        for k in cli_dict[flag].keys():
            v = cli_dict[flag][k]
            v = [handle_cli_bool(x) for x in v]
            if len(v) == 1:
                cli_str = f"--{flag} " + k + ":"  + f"{v[0]}"
                cli_line.append(cli_str)
            else:
                cli_str = f"--{flag} " + k + ":"  + ",".join(v)
                cli_line.append(cli_str)
    return cli_line

##y = clidict_to_commandline(x)
##print(y)


def collect_apidict_jsoninputform(json_response):
    api_dict = dict()
    api_dict['fields'] = []
    api_dict['groups'] = []
    for idx,fields in enumerate(json_response):
        ### skip elements that are SECTION type
        if fields['type'].upper() == "SECTION":
            print(f"Skipping {fields['id']}")
        ##### if element is a datatype
        elif fields['type'].upper() == "DATA":
            if fields['hidden'] is not True and fields['disabled'] is not True:
                if 'dataValues' in list(fields.keys()):
                    param_dict = dict()
                    param_dict['id'] = fields['id']
                    param_dict['dataValues'] = [ x['dataId'] for x in fields['dataValues'] ]
                    if len(param_dict['dataValues']) > 0:
                        api_dict['fields'].append(param_dict)
        elif fields['type'].upper() == "FIELDGROUP":
            if fields['hidden'] is not True and fields['disabled'] is not True:
                overall_group_values = dict()
                overall_group_values['values'] = []
                overall_group_values['id'] = fields['id']
                ### groupValues
                if 'groupValues' in fields.keys():
                    group_values = fields['groupValues']
                    for idx,param_g in enumerate(group_values):
                        group_values_dict = dict()
                        group_values_dict['values'] = []
                        for idx1,param in enumerate(param_g['values']):
                            param_dict = dict()
                            param_dict['id'] = param['id']
                            param_dict['dataValues'] = []
                            param_dict['values'] = []
                            if len(param['values']) > 0:
                                for p in param['values']:
                                    if re.match("^fol.",p) is not None or re.match("^fil.",p) is not None:
                                        data_dict = dict()
                                        data_dict['dataId'] = p
                                        param_dict['dataValues'].append(data_dict)
                                    elif re.match("^fol.",p) is None and re.match("^fil.",p) is None:
                                        param_dict['values'].append(p)
                            ## remove 'values' if we don't have any information to send
                            if len(param_dict['values']) == 0:
                                param_dict.pop('values', None)
                            ## remove 'dataValues' if we don't have any information to send
                            if len(param_dict['dataValues']) == 0:
                                param_dict.pop('dataValues', None)
                            if len(param_dict.keys()) > 0:
                                group_values_dict['values'].append(param_dict) 
                        if len(group_values_dict['values']) > 0:
                            overall_group_values['values'].append(group_values_dict)
                ### fields
                if 'fields' in fields.keys():
                    group_fields = fields['fields']
                    group_values_dict = dict()
                    group_values_dict['values'] = []
                    for idx,param in enumerate(group_fields):
                        if param['hidden'] is not True and param['disabled'] is not True and 'values' in param.keys():
                            param_dict = dict()
                            param_dict['id'] = param['id']
                            new_values = None
                            ### checkbox is of boolean type
                            if param['type'].upper() in ["CHECKBOX"]:
                                new_values = [ string_to_boolean(x) for x in param['values'] ]
                            if param['type'].upper() in ["INTEGER"]:
                                new_values = [ int(x) for x in param['values'] ]
                            #if 'choices' in list(param.keys()):
                            #    new_values = [ choices_conversion(param['choices'],x) for x in param['values']]
                            if new_values is not None:
                                param['values'] = new_values
                            if len(param['values']) > 0:
                                param_dict['values'] = param['values']
                            ## remove 'values' if we don't have any information to send
                            if len(param_dict['values']) == 0:
                                param_dict.pop('values', None)
                            ## remove 'dataValues' if we don't have any information to send
                            if len(param_dict['dataValues']) == 0:
                                param_dict.pop('dataValues', None)
                            if len(param_dict.keys()) > 0:
                                group_values_dict['values'].append(param_dict) 
                        elif param['hidden'] is not True and param['disabled'] is not True and 'dataValues' in param.keys():
                            param_dict = dict()
                            param_dict['id'] = param['id']
                            if len(param['dataValues']) > 0:
                                param_dict['dataValues'] = param['dataValues']
                            ## remove 'values' if we don't have any information to send
                            if len(param_dict['values']) == 0:
                                param_dict.pop('values', None)
                            ## remove 'dataValues' if we don't have any information to send
                            if len(param_dict['dataValues']) == 0:
                                param_dict.pop('dataValues', None)
                            if len(param_dict.keys()) > 0:
                                group_values_dict['values'].append(param_dict)  
                        if len(group_values_dict['values']) > 0:
                            overall_group_values['values'].append(group_values_dict)
                ### add nested object back
                if len(overall_group_values['values']) > 0:
                        api_dict['groups'].append(overall_group_values)
        else:
        ### otherwise grab values
            if fields['hidden'] is not True and fields['disabled'] is not True:
                if 'values' in list(fields.keys()):
                    param_dict = dict()
                    param_dict['id'] = fields['id']
                    new_values = None
                    ### checkbox is of boolean type
                    if fields['type'].upper() in ["CHECKBOX"]:
                        new_values = [ string_to_boolean(x) for x in fields['values'] ]
                    if fields['type'].upper() in ["INTEGER"]:
                        new_values = [ int(x) for x in fields['values'] ]
                    #if 'choices' in list(fields.keys()):
                    #    new_values = [ choices_conversion(fields['choices'],x) for x in fields['values']]
                    if new_values is not None:
                        fields['values'] = new_values
                    param_dict['values'] = fields['values']
                    if len(param_dict['values']) > 0:
                        api_dict['fields'].append(param_dict)
    return api_dict
###z = collect_apidict_jsoninputform(d['items'])
####pprint(z,indent = 4)    