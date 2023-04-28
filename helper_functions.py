import copy
import glob
import json
import os
import subprocess as sub
import operator
import sys
import requests
from bs4 import BeautifulSoup
from dateutil.parser import parse

ops = {'+': operator.add, '-': operator.sub}

'''
##################################################################################################################################
###################################################     HELPER FUNCTIONS     #####################################################
##################################################################################################################################
'''

def verbose_print(text):
    print(f"{text}")

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def load_session_config(f_name):
    session_config = None
    file_exists = os.path.exists(f_name)
    if not file_exists: # create the file
        with open(f_name, 'w') as f:
            f.close()
    else: # load the file
        data_flag = True # detects if the file is empty
        with open(f_name, 'r') as json_file:
            lines = json_file.readlines()
            if len(lines) == 0 or len(lines[0].replace(' ', '')) == 0:
                data_flag = False
            json_file.close()

        if data_flag: # data present
            with open(f_name) as json_file:
                data = json.load(json_file)

                temp_config = [dictionary for dictionary in data]
                if len(temp_config) > 0:
                    session_config = data
                else:
                    session_config = {}
                json_file.close()
    return session_config

def grab_pre_selected(settings, all_checkboxes):
    pre_selected_checkboxes = []
    for key in all_checkboxes:
        if settings[key]:
            pre_selected_checkboxes.append(key)
    return pre_selected_checkboxes

def update_JSON(settings, temp_config_name):
    temp = copy.deepcopy(settings)
    for entry in temp:
        verbose_print(f"{entry}:\t{settings[entry]}")

    with open(temp_config_name, "w") as f:
        json.dump(temp, indent=4, fp=f)
    f.close()
    verbose_print("="*42)

def create_dirs(arb_path):
    if not os.path.exists(arb_path):
        os.makedirs(arb_path)

def execute(cmd):
    popen = sub.Popen(cmd, stdout=sub.PIPE, universal_newlines=True)
    for stdout_line in iter(popen.stdout.readline, ""):
        yield stdout_line
    popen.stdout.close()
    return_code = popen.wait()
    if return_code:
        raise sub.CalledProcessError(return_code, cmd)

def get_list(arb_string, delimeter):
    return arb_string.split(delimeter)

def get_string(arb_list, delimeter):
    return delimeter.join(arb_list)

def from_padded(line):
    if len(line) > 1:# check for padded-0
        if int(line[0]) == 0:# remove the 0, cast to int, return
            return int(line[-1])
    return int(line)

def to_padded(num):
    return f"{num:02}"

def is_windows():
    return os.name == 'nt'

def parse_files_all_tags(file_list):
    all_tags_all_files = {}
    temp = '\\' if is_windows() else '/'
    for single_file in file_list:
        all_tags = []
        img_id = single_file.split(temp)[-1].split(".")[0]
        # verbose_print(f"single_file:\t\t{single_file}")
        with open(single_file, 'r', encoding='utf-8') as read_file:
            while True:
                line = read_file.readline()
                if not line:
                    break

                line = line.replace(" ", "")
                length = len(line.split(","))

                if length > 3:  # assume everything on one line
                    tags = line.split(",")
                    for tag in tags:
                        all_tags.append(tag)
                else:  # assume cascaded tags
                    tag = line.split(",")[0]
                    all_tags.append(tag)
            read_file.close()
            all_tags_all_files[img_id] = all_tags
    return all_tags_all_files.copy()


def parse_csv_all_tags(csv_file_path):
    # verbose_print(f"single_file:\t\t{csv_file_path}")
    temp_dict = {}
    counter = 0
    with open(csv_file_path, 'r', encoding='utf-8') as read_file:
        while True:
            line = read_file.readline()
            if not line:
                break
            if counter > 0:
                line = line.replace(" ", "")
                key = line.split(',')[0]
                value = line.split(',')[-1]
                temp_dict[key] = int(value.strip())
            counter += 1
        read_file.close()
    return temp_dict.copy()

def merge_dict(path1, path2, path3):
    png_list = glob.glob(os.path.join(path1, f"*.png"))
    png_list = [x.replace(f".png", f".txt") for x in png_list]

    jpg_list = glob.glob(os.path.join(path2, f"*.jpg"))
    jpg_list = [x.replace(f".jpg", f".txt") for x in jpg_list]

    gif_list = glob.glob(os.path.join(path3, f"*.gif"))
    gif_list = [x.replace(f".gif", f".txt") for x in gif_list]

    temp = {}
    temp["png"] = parse_files_all_tags(png_list)
    temp["jpg"] = parse_files_all_tags(jpg_list)
    temp["gif"] = parse_files_all_tags(gif_list)
    temp["searched"] = {}
    return temp.copy()

def write_tags_to_text_file(input_string, file_path):
    with open(file_path, 'w') as file:
        file.write(input_string)

def dict_to_sorted_list(d):
    return sorted([[k, v] for k, v in d.items()], key=lambda x: x[1], reverse=True)

def write_tags_to_csv(dictionary, file_path):
    temp = '\\' if is_windows() else '/'
    csv_name = (file_path.split(temp)[-1]).split('.csv')[0]
    header_string = f"{csv_name},count"
    if "tags" in header_string:
        header_string = f"tag,count"
    # sort tags descending by frequency
    sort_dictionary_to_list = dict_to_sorted_list(dictionary)

    with open(file_path, 'w') as file:
        file.write(f"{header_string}\n")
        for pair in sort_dictionary_to_list:
            file.write(f"{pair[0]},{pair[1]}\n")
    file.close()

def update_all_csv_dictionaries(artist_csv_dict, character_csv_dict, species_csv_dict, general_csv_dict, meta_csv_dict,
                                rating_csv_dict, tags_csv_dict, string_category, tag, op, count):
    if string_category in "artist":
        if tag in list(artist_csv_dict.keys()):
            artist_csv_dict[tag] = ops[op](artist_csv_dict[tag], count)
        else:
            artist_csv_dict[tag] = ops[op](0, count)
    if string_category in "character":
        if tag in list(character_csv_dict.keys()):
            character_csv_dict[tag] = ops[op](character_csv_dict[tag], count)
        else:
            character_csv_dict[tag] = ops[op](0, count)
    if string_category in "species":
        if tag in list(species_csv_dict.keys()):
            species_csv_dict[tag] = ops[op](species_csv_dict[tag], count)
        else:
            species_csv_dict[tag] = ops[op](0, count)
    if string_category in "general":
        if tag in list(general_csv_dict.keys()):
            general_csv_dict[tag] = ops[op](general_csv_dict[tag], count)
        else:
            general_csv_dict[tag] = ops[op](0, count)
    if string_category in "meta":
        if tag in list(meta_csv_dict.keys()):
            meta_csv_dict[tag] = ops[op](meta_csv_dict[tag], count)
        else:
            meta_csv_dict[tag] = ops[op](0, count)
    if string_category in "rating":
        if tag in list(rating_csv_dict.keys()):
            rating_csv_dict[tag] = ops[op](rating_csv_dict[tag], count)
        else:
            rating_csv_dict[tag] = ops[op](0, count)
    # change the global tag csv
    if tag in list(tags_csv_dict.keys()):
        tags_csv_dict[tag] = ops[op](tags_csv_dict[tag], count)
    else:
        tags_csv_dict[tag] = ops[op](0, count)

    return artist_csv_dict.copy(), character_csv_dict.copy(), species_csv_dict.copy(), general_csv_dict.copy(), \
           meta_csv_dict.copy(), rating_csv_dict.copy(), tags_csv_dict.copy()

# one entry per line
def get_text_file_data(file_path, tag_per_line):
    all_tags = []
    # verbose_print(f"file_path:\t\t{file_path}")
    with open(file_path, 'r', encoding='utf-8') as read_file:
        while True:
            line = read_file.readline()
            if not line:
                break
            line = line.replace(" ", "")
            if tag_per_line == 1:
                tag = line
                if "," in line:
                    tag = line.split(",")[0]
                all_tags.append(tag)
            elif tag_per_line > 1:
                keyword = line.split(",")[0]
                replacements = line.split(",")[1:]
                all_tags.append([keyword, replacements])
        read_file.close()
    return all_tags

def get_href_links(url):
    response = requests.get(url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a')

        href_links = []
        for link in links:
            href = link.get('href')
            if href:
                href_links.append(href)

        return href_links
    else:
        print(f"Request to {url} failed with status code: {response.status_code}")
        return []


def extract_time_and_href(url):
    response = requests.get(url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')

        # Assuming that the list elements are wrapped within a <ul> or <ol> tag.
        list_elements = soup.find_all(['li', 'ol'])

        results = []

        for element in list_elements:
            link = element.find('a')
            time_element = element.find('time')

            if link and time_element:
                href = link.get('href')
                time_value = time_element.get('datetime') or time_element.text
                time_object = parse(time_value)
                results.append([href, time_object])

        # Sort the results based on datetime object, newest to oldest
        sorted_results = sorted(results, key=lambda x: x[-1], reverse=True)

        return sorted_results
    else:
        print(f"Request to {url} failed with status code: {response.status_code}")
        return []

model_download_options = ["Fluffusion", "FluffyRock"]

def get_fluffyrock_models():
    # get all model names
    url = "https://huggingface.co/lodestones/furryrock-model-safetensors/tree/main/"
    href_links = extract_time_and_href(url)
    temp_list = set()
    for href_link in href_links:
        href_link, time_element = href_link
        if "/" in href_link:
            temp_list.add(f'{href_link.split(" / ")[-1]}---{time_element}')
        else:
            temp_list.add(f'{href_link}---{time_element}')
        verbose_print(f"href_link:\t{href_link}\tand\ttime_element:\t{time_element}")
    # filter out non-safetensor files
    temp_list = list(temp_list)
    for i in range(len(temp_list) - 1, -1, -1):
        if not "safetensors" in (temp_list[i]).split(".")[-1]:
            temp_list.remove(temp_list[i])
    sorted_results = sorted(temp_list, key=lambda x: (x.split('---'))[-1], reverse=True)
    return sorted_results

def get_fluffusion_models():
    # get all model names
    url = "https://static.treehaus.dev/"
    href_links = get_href_links(url)
    temp_list = set()
    for href_link in href_links:
        if "/" in href_link:
            temp_list.add(href_link.split("/")[-1])
        else:
            temp_list.add(href_link)
        verbose_print(f"href_link:\t{href_link}")
    # filter out fluffyrock models
    temp_list = list(temp_list)
    for i in range(len(temp_list)-1, -1, -1):
        if (model_download_options[-1]).lower() in temp_list[i] or not "ckpt" in (temp_list[i]).split(".")[-1]:
            temp_list.remove(temp_list[i])
    sorted_results = sorted(temp_list, key=lambda x: x)
    return sorted_results

def get_model_names(name):
    if name == "Fluffusion":
        return get_fluffusion_models()
    elif name == "FluffyRock":
        return get_fluffyrock_models()

def full_model_download_link(name, file_name):
    if name == "Fluffusion":
        url = "https://static.treehaus.dev/"
        return f"{url}{file_name}"
    elif name == "FluffyRock":
        url = "https://huggingface.co/lodestones/furryrock-model-safetensors/resolve/main/"
        return f"{url}{(file_name.split('---')[0])}"

def extract_time_and_href_github(api_url):
    response = requests.get(api_url)
    release_list = []

    if response.status_code == 200:
        releases = response.json()

        for release in releases:
            temp_list = []
            temp_list.append(release['tag_name'])
            print(f"Release: {release['tag_name']} - {release['html_url']}")
            assets_url = release['assets_url']
            assets_response = requests.get(assets_url)

            if assets_response.status_code == 200:
                assets = assets_response.json()
                download_urls = [asset['browser_download_url'] for asset in assets]
                temp_list.append(download_urls)
                for url in download_urls:
                    print(f"Download URL: {url}")
            else:
                print(
                    f"Failed to fetch assets for release {release['tag_name']}. Status code: {assets_response.status_code}")
                print(f"403 error means you've DONE OVER 60 API CALLS to githubs API per 1 hour. Now you have to wait! or do it manually")
                temp_list.append([])
            print()  # Add an empty line for better readability
            release_list.append(temp_list)
    else:
        print("Failed to fetch the releases. Status code:", response.status_code)
        print(f"403 error means you've DONE OVER 60 API CALLS to githubs API per 1 hour. Now you have to wait! or do it manually")
    return copy.deepcopy(release_list)
